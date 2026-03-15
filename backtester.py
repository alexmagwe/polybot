"""Backtesting engine with category-aware simulated market data.

Simulates only Politics/Elections and Macro/Regulatory markets,
plus cross-market arbitrage opportunities where external platforms diverge.
"""

import numpy as np
from dataclasses import dataclass, field
import config
from strategies import MarketInefficiencyDetector, CrossMarketArbitrage, KellyCriterion
from game_theory import GameTheoryEngine


@dataclass
class Trade:
    market_id: int
    entry_day: int
    exit_day: int
    direction: str
    entry_price: float
    exit_price: float
    position_size: float
    fair_value: float
    edge: float
    category: str = ""
    strategy: str = ""
    gt_score: float = 0.0
    gt_nash: float = 0.0
    gt_beauty: float = 0.0
    gt_whale: float = 0.0
    gt_liquidity: float = 0.0
    combined_score: float = 0.0
    pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    initial_capital: float = config.INITIAL_CAPITAL
    final_capital: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_fees: float = 0.0
    total_pnl: float = 0.0
    net_pnl: float = 0.0
    win_rate: float = 0.0
    roi: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


# Realistic market names for simulation
POLITICS_MARKETS = [
    "Will the incumbent win the 2026 Senate election?",
    "Will the nominee win the presidential primary?",
    "Will Congress pass the infrastructure bill by Q2?",
    "Will the governor sign the ballot measure?",
    "Will the Republican candidate win the swing state?",
    "Will the Democrat nominee lead in polls by March?",
    "Will the electoral college vote match popular vote?",
    "Will impeachment proceedings begin before June?",
]

MACRO_MARKETS = [
    "Will the Fed cut interest rates at the next FOMC meeting?",
    "Will CPI inflation drop below 3% by Q2 2026?",
    "Will FDA approve the new Alzheimer's drug?",
    "Will GDP growth exceed 2.5% this quarter?",
    "Will the SEC approve the Bitcoin ETF application?",
    "Will unemployment stay below 4% through 2026?",
    "Will the debt ceiling be raised before the deadline?",
    "Will the central bank announce new tariff policy?",
    "Will the antitrust merger ruling block the deal?",
    "Will recession probability exceed 50% per NBER?",
    "Will the executive order on crypto regulation pass?",
    "Will the trade war escalate with new sanctions?",
]


def generate_simulated_markets(
    num_markets: int = config.NUM_SIMULATED_MARKETS,
    num_days: int = config.NUM_SIMULATED_DAYS,
    seed: int = 42,
) -> list[dict]:
    """Generate simulated market data for politics and macro categories.

    Each market includes:
    - Category (politics or macro)
    - A simulated external platform price (Metaculus/Kalshi equivalent)
    - True probability path, market prices, volume, spreads
    """
    rng = np.random.RandomState(seed)
    markets = []

    all_names = []
    all_categories = []
    n_politics = max(1, int(num_markets * 0.4))
    n_macro = num_markets - n_politics

    for i in range(n_politics):
        all_names.append(POLITICS_MARKETS[i % len(POLITICS_MARKETS)])
        all_categories.append("politics")
    for i in range(n_macro):
        all_names.append(MACRO_MARKETS[i % len(MACRO_MARKETS)])
        all_categories.append("macro")

    for i in range(num_markets):
        category = all_categories[i]
        true_prob_start = rng.uniform(0.2, 0.8)

        resolves_yes = rng.random() < true_prob_start
        resolution_target = 1.0 if resolves_yes else 0.0

        if category == "politics":
            daily_vol = 0.012
            drift_strength = 0.025
        else:
            daily_vol = 0.018
            drift_strength = 0.035

        true_probs = [true_prob_start]
        for d in range(1, num_days):
            time_factor = (d / num_days) ** 2
            drift = (resolution_target - true_probs[-1]) * drift_strength * (1 + 2 * time_factor)
            noise = rng.normal(0, daily_vol * (1 - time_factor * 0.5))
            new_prob = np.clip(true_probs[-1] + drift + noise, 0.02, 0.98)
            true_probs.append(new_prob)

        market_prices = []
        for d in range(num_days):
            base_noise = rng.normal(0, 0.02)
            # Rare larger mispricings (10% chance, smaller magnitude)
            if rng.random() < 0.10:
                base_noise += rng.choice([-1, 1]) * rng.uniform(0.04, 0.09)
            price = np.clip(true_probs[d] + base_noise, 0.02, 0.98)
            market_prices.append(price)

        # External platform prices (Metaculus/Kalshi equivalent)
        # These are noisy estimates — not perfect oracles. They have their own
        # biases and only partially overlap with Polymarket inefficiencies.
        external_prices = []
        for d in range(num_days):
            # External platforms have their own noise (less than Polymarket but not zero)
            ext_noise = rng.normal(0, 0.04)
            # Occasional external mispricing too (platforms disagree legitimately)
            if rng.random() < 0.15:
                ext_noise += rng.choice([-1, 1]) * rng.uniform(0.04, 0.10)
            ext_price = np.clip(true_probs[d] + ext_noise, 0.02, 0.98)
            external_prices.append(ext_price)

        volumes = []
        for d in range(num_days):
            base_vol = rng.uniform(800, 5000)
            if d > num_days * 0.7:
                base_vol *= 2
            if abs(market_prices[d] - true_probs[d]) > 0.05:
                base_vol *= 1.5
            volumes.append(base_vol)

        spreads = []
        avg_vol = np.mean(volumes)
        for d in range(num_days):
            vol_ratio = volumes[d] / avg_vol if avg_vol > 0 else 1
            spread = 0.03 / max(vol_ratio, 0.5)
            spreads.append(float(np.clip(spread, 0.01, 0.10)))

        markets.append({
            "id": i,
            "name": all_names[i],
            "category": category,
            "true_probs": true_probs,
            "market_prices": market_prices,
            "external_prices": external_prices,
            "volumes": volumes,
            "spreads": spreads,
            "resolved_yes": 1.0 if resolves_yes else 0.0,
        })

    return markets


HOLD_PERIOD = 5
# Only hold to binary resolution in the final 5 days
HOLD_TO_RESOLUTION_AFTER_DAY = 55


class Backtester:
    """Backtesting engine for politics/macro markets with cross-market arbitrage."""

    def __init__(self, capital: float = config.INITIAL_CAPITAL):
        self.initial_capital = capital
        self.detector = MarketInefficiencyDetector()
        self.arb_detector = CrossMarketArbitrage()
        self.kelly = KellyCriterion()
        self.gt_engine = GameTheoryEngine()

    def _close_trade(self, trade, mkt, day, num_days, hold_to_res):
        """Calculate P&L for a closing trade."""
        if hold_to_res:
            resolved = mkt["resolved_yes"]
            if trade.direction == "BUY_YES":
                won = resolved == 1.0
            else:
                won = resolved == 0.0
            if won:
                exit_price = 1.0
            else:
                exit_price = 0.0
        else:
            exit_price = mkt["market_prices"][min(day, num_days - 1)]

        if trade.direction == "BUY_YES":
            shares = trade.position_size / trade.entry_price
            gross_pnl = shares * (exit_price - trade.entry_price)
        else:
            no_entry = trade.entry_price
            if hold_to_res:
                no_exit = 1.0 if exit_price == 0.0 else 0.0
            else:
                no_exit = 1.0 - exit_price
            shares = trade.position_size / no_entry
            gross_pnl = shares * (no_exit - no_entry)

        exit_fee = max(gross_pnl, 0) * config.TAKER_FEE_RATE
        entry_fee = trade.position_size * config.TAKER_FEE_RATE
        slippage = trade.position_size * config.SLIPPAGE_ESTIMATE
        gas = config.GAS_FEE_PER_TRADE * 2
        total_fees = entry_fee + exit_fee + slippage + gas

        trade.exit_price = exit_price
        trade.exit_day = day
        trade.pnl = gross_pnl
        trade.fees = total_fees
        trade.net_pnl = gross_pnl - total_fees

    def run(
        self,
        markets: list[dict],
        num_days: int = config.NUM_SIMULATED_DAYS,
    ) -> BacktestResult:
        """Run backtest across category-filtered simulated markets."""
        result = BacktestResult(initial_capital=self.initial_capital)
        capital = self.initial_capital
        result.equity_curve.append(capital)

        traded = set()
        pending_trades = []

        for day in range(10, num_days - 1):
            # Close pending trades
            still_pending = []
            for trade, exit_day, mkt, hold_to_res in pending_trades:
                if day >= exit_day:
                    self._close_trade(trade, mkt, day, num_days, hold_to_res)
                    result.trades.append(trade)
                    capital += trade.net_pnl
                else:
                    still_pending.append((trade, exit_day, mkt, hold_to_res))
            pending_trades = still_pending

            daily_entries = 0
            for market in markets:
                if daily_entries >= config.MAX_CONCURRENT_POSITIONS:
                    break

                trade_key = (market["id"], day // HOLD_PERIOD)
                if trade_key in traded:
                    continue

                price = market["market_prices"][day]
                price_history = market["market_prices"][max(0, day - 15): day]
                vol_history = market["volumes"][max(0, day - 10): day + 1]
                avg_vol = np.mean(market["volumes"][max(0, day - 10): day])
                vol_ratio = market["volumes"][day] / avg_vol if avg_vol > 0 else 1.0
                spread = market["spreads"][day]
                category = market["category"]
                ext_price = market["external_prices"][day]

                # Strategy 1: Category-aware inefficiency detection
                signal = self.detector.detect(
                    price, vol_ratio, price_history, spread, category
                )

                # Strategy 2: Cross-market arbitrage
                arb_signal = self.arb_detector.detect(price, ext_price, "metaculus/kalshi")

                # Pick the stronger base signal
                best_signal = None
                strategy_name = ""
                if signal["actionable"] and signal["abs_edge"] >= config.MIN_EDGE:
                    best_signal = signal
                    strategy_name = "inefficiency"
                if arb_signal["actionable"] and arb_signal["abs_edge"] >= config.MIN_EDGE:
                    if best_signal is None or arb_signal["abs_edge"] > best_signal["abs_edge"]:
                        best_signal = arb_signal
                        strategy_name = "cross_market_arb"

                if best_signal is None:
                    continue

                # Game theory scoring
                gt_result = self.gt_engine.evaluate(
                    market_price=price,
                    fair_value=best_signal["fair_value"],
                    volume_ratio=vol_ratio,
                    spread=spread,
                    price_history=price_history,
                    volume_history=vol_history,
                )

                # Combined score: base edge + game theory boost
                base_score = best_signal["abs_edge"]
                gt_boost = gt_result.total_score
                # GT score is directional — check alignment with base signal direction
                base_direction_sign = 1.0 if best_signal["direction"] == "BUY_YES" else -1.0
                gt_alignment = gt_boost * base_direction_sign
                # If GT disagrees with base signal, reduce confidence
                if gt_alignment < -0.3:
                    continue  # GT strongly disagrees, skip trade
                combined_score = base_score + max(gt_alignment, 0) * 0.1

                # Use initial capital for sizing to prevent unrealistic compounding
                sizing_capital = self.initial_capital
                sizing = self.kelly.position_size(
                    sizing_capital, price, best_signal["fair_value"], best_signal["direction"]
                )

                if sizing["position_size"] <= 0 or sizing["ev_after_fees"] <= 0:
                    continue

                hold_to_res = day >= HOLD_TO_RESOLUTION_AFTER_DAY
                exit_day = num_days - 1 if hold_to_res else min(day + HOLD_PERIOD, num_days - 1)

                trade = Trade(
                    market_id=market["id"],
                    entry_day=day,
                    exit_day=exit_day,
                    direction=best_signal["direction"],
                    entry_price=sizing["entry_price"],
                    exit_price=0.0,
                    position_size=sizing["position_size"],
                    fair_value=best_signal["fair_value"],
                    edge=best_signal["edge"],
                    category=category,
                    strategy=strategy_name,
                    gt_score=gt_result.total_score,
                    gt_nash=gt_result.nash_score,
                    gt_beauty=gt_result.beauty_contest_score,
                    gt_whale=gt_result.whale_score,
                    gt_liquidity=gt_result.liquidity_score,
                    combined_score=combined_score,
                )

                pending_trades.append((trade, exit_day, market, hold_to_res))
                traded.add(trade_key)
                daily_entries += 1

            result.equity_curve.append(capital)

        # Force-close remaining positions
        for trade, exit_day, mkt, hold_to_res in pending_trades:
            # Only resolve to binary if the trade was entered late enough
            self._close_trade(trade, mkt, num_days - 1, num_days, hold_to_res)
            result.trades.append(trade)
            capital += trade.net_pnl

        result.equity_curve.append(capital)

        # Summary stats
        result.final_capital = capital
        result.total_trades = len(result.trades)
        result.winning_trades = sum(1 for t in result.trades if t.net_pnl > 0)
        result.losing_trades = result.total_trades - result.winning_trades
        result.total_fees = sum(t.fees for t in result.trades)
        result.total_pnl = sum(t.pnl for t in result.trades)
        result.net_pnl = sum(t.net_pnl for t in result.trades)
        result.win_rate = (
            result.winning_trades / result.total_trades
            if result.total_trades > 0
            else 0
        )
        result.roi = (result.final_capital - result.initial_capital) / result.initial_capital

        peak = result.equity_curve[0]
        max_dd = 0.0
        for eq in result.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown = max_dd

        if len(result.equity_curve) > 1:
            returns = []
            for i in range(1, len(result.equity_curve)):
                prev = result.equity_curve[i - 1]
                if prev > 0:
                    returns.append((result.equity_curve[i] - prev) / prev)
            if len(returns) > 1 and np.std(returns) > 0:
                result.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)

        return result
