#!/usr/bin/env python3
"""Paper trading engine for Polymarket bot.

Fetches LIVE market data from Polymarket APIs, runs signals + game theory,
and simulates trades with a virtual portfolio. No private key needed.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import numpy as np
import requests

import config
from api_client import PolymarketClient, classify_market
from signals import SignalGenerator, Signal


STATE_FILE = "/workspace/group/polymarket-bot/paper_trades.json"

# Paper trading fee structure (matches config)
PAPER_TAKER_FEE = config.TAKER_FEE_RATE       # 2%
PAPER_SLIPPAGE = config.SLIPPAGE_ESTIMATE      # 0.5%
PAPER_GAS = config.GAS_FEE_PER_TRADE           # $0.01


@dataclass
class PaperPosition:
    market_id: str
    market_name: str
    category: str
    strategy: str
    direction: str
    entry_price: float
    position_size: float
    shares: float
    entry_fees: float
    entry_time: str
    signal_edge: float
    signal_confidence: str
    fair_value: float
    gt_score: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "open"  # open, closed
    exit_price: float = 0.0
    exit_time: str = ""
    exit_fees: float = 0.0
    realized_pnl: float = 0.0
    net_pnl: float = 0.0


@dataclass
class PaperPortfolio:
    initial_capital: float = 100.0
    cash: float = 100.0
    open_positions: list = field(default_factory=list)
    closed_positions: list = field(default_factory=list)
    total_fees_paid: float = 0.0
    last_updated: str = ""
    data_source: str = "live"  # "live" or "simulated"

    def portfolio_value(self):
        unrealized = sum(p.get("unrealized_pnl", 0) if isinstance(p, dict) else p.unrealized_pnl
                         for p in self.open_positions)
        return self.cash + sum(
            (p.get("position_size", 0) if isinstance(p, dict) else p.position_size)
            for p in self.open_positions
        ) + unrealized

    def to_dict(self):
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "open_positions": [asdict(p) if hasattr(p, '__dataclass_fields__') else p
                               for p in self.open_positions],
            "closed_positions": [asdict(p) if hasattr(p, '__dataclass_fields__') else p
                                 for p in self.closed_positions],
            "total_fees_paid": self.total_fees_paid,
            "last_updated": self.last_updated,
            "data_source": self.data_source,
        }

    @classmethod
    def from_dict(cls, d):
        portfolio = cls(
            initial_capital=d.get("initial_capital", 100.0),
            cash=d.get("cash", 100.0),
            total_fees_paid=d.get("total_fees_paid", 0.0),
            last_updated=d.get("last_updated", ""),
            data_source=d.get("data_source", "live"),
        )
        portfolio.open_positions = d.get("open_positions", [])
        portfolio.closed_positions = d.get("closed_positions", [])
        return portfolio


def load_portfolio() -> PaperPortfolio:
    """Load portfolio state from disk, or create a fresh one."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            return PaperPortfolio.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Paper] Warning: corrupted state file, starting fresh: {e}")
    return PaperPortfolio()


def save_portfolio(portfolio: PaperPortfolio):
    """Save portfolio state to disk."""
    portfolio.last_updated = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(portfolio.to_dict(), f, indent=2)


def fetch_live_markets() -> tuple[list[dict], str]:
    """Fetch live markets from Polymarket Gamma API.

    Fetches multiple pages to find enough tradeable markets.
    Returns (markets_data, data_source) where data_source is 'live' or 'simulated'.
    """
    print("[Paper] Fetching live markets from Polymarket...")

    try:
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})
        all_raw = []

        # Fetch multiple pages sorted by volume to find active markets
        for offset in range(0, 300, 100):
            resp = session.get(
                f"{config.GAMMA_API_URL}/markets",
                params={
                    "limit": 100,
                    "active": "true",
                    "closed": "false",
                    "order": "volume24hr",
                    "ascending": "false",
                    "offset": offset,
                },
                timeout=15,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            # Filter to allowed categories
            for m in batch:
                title = m.get("question", m.get("title", ""))
                desc = m.get("description", "")
                category = classify_market(title, desc)
                if category is not None:
                    m["_category"] = category
                    all_raw.append(m)

        if all_raw:
            print(f"[Paper] Fetched {len(all_raw)} politics/macro markets from Polymarket")
            client = PolymarketClient()
            transformed = _transform_live_markets(all_raw, client)
            if transformed:
                return transformed, "live"
            print("[Paper] No tradeable markets after filtering (prices too extreme)")
            return [], "live"
    except Exception as e:
        print(f"[Paper] ERROR: Failed to fetch live data from Polymarket API: {e}")
        print("[Paper] No simulated fallback — only real data is used.")
        return [], "error"


def _transform_live_markets(raw_markets: list[dict], client: PolymarketClient) -> list[dict]:
    """Transform raw Gamma API market data into the format signals.py expects."""
    markets_data = []

    for m in raw_markets:
        title = m.get("question", m.get("title", ""))
        category = m.get("_category", classify_market(title, m.get("description", "")))
        if category is None:
            continue

        # Get price from outcomes or best bid/ask
        price = None
        tokens = m.get("clobTokenIds", m.get("clob_token_ids", ""))
        if isinstance(tokens, str) and tokens:
            # Try to parse as JSON array
            try:
                token_list = json.loads(tokens) if tokens.startswith("[") else [tokens]
            except json.JSONDecodeError:
                token_list = [tokens]
        elif isinstance(tokens, list):
            token_list = tokens
        else:
            token_list = []

        # Try outcomePrices first
        outcome_prices = m.get("outcomePrices", m.get("outcome_prices", ""))
        if outcome_prices:
            try:
                if isinstance(outcome_prices, str):
                    prices = json.loads(outcome_prices)
                else:
                    prices = outcome_prices
                if prices and len(prices) > 0:
                    price = float(prices[0])
            except (json.JSONDecodeError, ValueError, IndexError):
                pass

        # Fallback: try midpoint from CLOB
        if price is None and token_list:
            midpoint = client.get_midpoint(token_list[0])
            if midpoint is not None and midpoint > 0:
                price = midpoint

        if price is None or price <= 0.03 or price >= 0.97:
            continue

        # Volume
        volume = float(m.get("volume", m.get("volumeNum", 0)) or 0)

        # Build a synthetic price history from current price (we only have a snapshot)
        # Add small random noise to simulate recent history
        rng = np.random.RandomState(hash(title) % (2**31))
        noise = rng.normal(0, 0.01, 15)
        price_history = [float(np.clip(price + n, 0.02, 0.98)) for n in noise]
        price_history[-1] = price  # Most recent is actual price

        vol_history = [max(100, volume * (0.8 + rng.random() * 0.4)) for _ in range(15)]

        # Estimate spread (wider for lower volume)
        spread = 0.03 if volume > 5000 else 0.05 if volume > 1000 else 0.08

        markets_data.append({
            "market_id": m.get("conditionId", m.get("condition_id", str(hash(title)))),
            "market_name": title,
            "market_price": price,
            "volume_ratio": 1.0,  # No historical baseline for live
            "price_history": price_history,
            "spread": spread,
            "category": category,
            "external_price": None,  # No cross-platform data in paper mode
            "volume_history": vol_history,
            "volume": volume,
        })

    return markets_data



def execute_paper_trade(portfolio: PaperPortfolio, signal: Signal) -> PaperPosition | None:
    """Simulate executing a trade based on a signal."""
    # Check position limits
    if len(portfolio.open_positions) >= config.MAX_CONCURRENT_POSITIONS:
        return None

    # Check cash
    cost = signal.position_size
    entry_fee = cost * PAPER_TAKER_FEE
    slippage_cost = cost * PAPER_SLIPPAGE
    gas = PAPER_GAS
    total_entry_cost = cost + entry_fee + slippage_cost + gas

    if total_entry_cost > portfolio.cash:
        return None

    # Calculate shares
    if signal.direction == "BUY_YES":
        entry_price = signal.market_price + PAPER_SLIPPAGE  # Slippage on entry
        shares = cost / entry_price
    else:
        entry_price = (1.0 - signal.market_price) + PAPER_SLIPPAGE
        shares = cost / entry_price

    position = PaperPosition(
        market_id=signal.market_id,
        market_name=signal.market_name,
        category=signal.category,
        strategy=signal.strategy,
        direction=signal.direction,
        entry_price=entry_price,
        position_size=cost,
        shares=shares,
        entry_fees=entry_fee + slippage_cost + gas,
        entry_time=datetime.now(timezone.utc).isoformat(),
        signal_edge=signal.edge,
        signal_confidence=signal.confidence,
        fair_value=signal.fair_value,
        gt_score=signal.gt_score,
        current_price=signal.market_price,
    )

    portfolio.cash -= total_entry_cost
    portfolio.total_fees_paid += entry_fee + slippage_cost + gas
    portfolio.open_positions.append(asdict(position))

    return position


def run_paper_trading() -> dict:
    """Main paper trading loop. Fetches live data, generates signals, executes paper trades.

    Returns a summary dict with signals found and trades executed.
    """
    print("=" * 65)
    print("Polymarket Paper Trading Engine")
    print("Focus: Politics | Macro/Regulatory")
    print(f"Virtual Capital: $100.00")
    print("=" * 65)

    # Load existing state
    portfolio = load_portfolio()
    print(f"\n[1/4] Loading portfolio state...")
    print(f"  Cash: ${portfolio.cash:.2f}")
    print(f"  Open positions: {len(portfolio.open_positions)}")
    print(f"  Closed positions: {len(portfolio.closed_positions)}")

    # Fetch live market data
    print(f"\n[2/4] Fetching live market data...")
    markets_data, data_source = fetch_live_markets()
    portfolio.data_source = data_source
    print(f"  Data source: {data_source.upper()}")
    print(f"  Markets found: {len(markets_data)}")

    if not markets_data:
        print("  No eligible markets found. Exiting.")
        save_portfolio(portfolio)
        return {"signals": [], "trades": [], "data_source": data_source, "markets_scanned": 0}

    n_pol = sum(1 for m in markets_data if m["category"] == "politics")
    n_mac = sum(1 for m in markets_data if m["category"] == "macro")
    print(f"  Politics: {n_pol} | Macro: {n_mac}")

    # Generate signals
    print(f"\n[3/4] Running signal generation + game theory analysis...")
    signal_gen = SignalGenerator(capital=portfolio.cash)
    signals = signal_gen.scan_markets(markets_data)

    if not signals:
        print("  No actionable signals found in live markets (markets may be efficient at snapshot level)")

    print(f"  Signals found: {len(signals)}")
    if signals:
        for i, sig in enumerate(signals[:10]):
            print(f"  #{i+1}: {sig}")

    # Execute paper trades for top signals
    print(f"\n[4/4] Executing paper trades...")
    trades_executed = []
    for sig in signals:
        if len(trades_executed) >= config.MAX_CONCURRENT_POSITIONS:
            break
        # Skip if we already have a position in this market
        existing_ids = [p.get("market_id", "") if isinstance(p, dict) else p.market_id
                        for p in portfolio.open_positions]
        if sig.market_id in existing_ids:
            continue

        position = execute_paper_trade(portfolio, sig)
        if position:
            trades_executed.append(position)
            print(f"  TRADE: {position.direction} ${position.position_size:.2f} on '{position.market_name}'")
            print(f"         Entry: {position.entry_price:.4f} | Edge: {position.signal_edge:+.3f} | Conf: {position.signal_confidence}")

    if not trades_executed:
        print("  No trades executed (position limits, insufficient cash, or no signals)")

    # Save state
    save_portfolio(portfolio)
    print(f"\n  Portfolio saved to: {STATE_FILE}")
    print(f"  Cash remaining: ${portfolio.cash:.2f}")
    print(f"  Total fees: ${portfolio.total_fees_paid:.2f}")
    print(f"  Portfolio value: ~${portfolio.portfolio_value():.2f}")

    # Build summary
    signals_data = []
    for sig in signals:
        signals_data.append({
            "market_id": sig.market_id,
            "market_name": sig.market_name,
            "category": sig.category,
            "strategy": sig.strategy,
            "direction": sig.direction,
            "market_price": round(sig.market_price, 4),
            "fair_value": round(sig.fair_value, 4),
            "edge": round(sig.edge, 4),
            "position_size": round(sig.position_size, 2),
            "confidence": sig.confidence,
            "combined_score": round(sig.combined_score, 4),
            "gt_score": round(sig.gt_score, 4),
        })

    trades_data = []
    for pos in trades_executed:
        trades_data.append({
            "market_name": pos.market_name,
            "direction": pos.direction,
            "entry_price": round(pos.entry_price, 4),
            "position_size": round(pos.position_size, 2),
            "shares": round(pos.shares, 4),
            "entry_fees": round(pos.entry_fees, 4),
            "signal_edge": round(pos.signal_edge, 4),
            "confidence": pos.signal_confidence,
        })

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": data_source,
        "markets_scanned": len(markets_data),
        "politics_markets": n_pol,
        "macro_markets": n_mac,
        "signals_found": len(signals),
        "trades_executed": len(trades_executed),
        "portfolio_cash": round(portfolio.cash, 2),
        "portfolio_value": round(portfolio.portfolio_value(), 2),
        "total_fees_paid": round(portfolio.total_fees_paid, 4),
        "signals": signals_data,
        "trades": trades_data,
    }

    return summary


if __name__ == "__main__":
    summary = run_paper_trading()
    print(f"\n{'=' * 65}")
    print(f"Paper trading run complete!")
    print(f"Signals: {summary['signals_found']} | Trades: {summary['trades_executed']}")
    print(f"{'=' * 65}")
