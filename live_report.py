#!/usr/bin/env python3
"""Live performance report generator for paper trading.

Shows current portfolio value, open/closed positions, running stats,
and comparison vs backtest expectations.
"""

import json
import os
from datetime import datetime, timezone

from paper_trader import STATE_FILE, PaperPortfolio, PAPER_TAKER_FEE, PAPER_SLIPPAGE, PAPER_GAS


def load_portfolio_data() -> dict | None:
    """Load raw portfolio data from state file."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def generate_live_report(output_path: str = None) -> str:
    """Generate a live performance report from paper trading state."""
    data = load_portfolio_data()
    if data is None:
        return "No paper trading data found. Run paper trading first with: python main.py --paper"

    portfolio = PaperPortfolio.from_dict(data)
    open_pos = portfolio.open_positions
    closed_pos = portfolio.closed_positions

    # Calculate metrics
    total_invested = sum(p.get("position_size", 0) for p in open_pos)
    portfolio_value = portfolio.cash + total_invested + sum(
        p.get("unrealized_pnl", 0) for p in open_pos
    )
    total_realized_pnl = sum(p.get("net_pnl", 0) for p in closed_pos)
    total_unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in open_pos)
    roi = (portfolio_value - portfolio.initial_capital) / portfolio.initial_capital

    # Win rate from closed positions
    winners = [p for p in closed_pos if p.get("net_pnl", 0) > 0]
    losers = [p for p in closed_pos if p.get("net_pnl", 0) <= 0]
    win_rate = len(winners) / len(closed_pos) if closed_pos else 0

    lines = []
    lines.append("=" * 65)
    lines.append("POLYMARKET PAPER TRADING - LIVE PERFORMANCE REPORT")
    lines.append("=" * 65)
    lines.append(f"Report generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Data source: {portfolio.data_source.upper()}")
    lines.append(f"Last updated: {portfolio.last_updated}")
    lines.append("")

    # Portfolio summary
    lines.append("-" * 40)
    lines.append("PORTFOLIO SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Initial Capital:    ${portfolio.initial_capital:.2f}")
    lines.append(f"  Current Cash:       ${portfolio.cash:.2f}")
    lines.append(f"  Invested (open):    ${total_invested:.2f}")
    lines.append(f"  Portfolio Value:    ${portfolio_value:.2f}")
    lines.append(f"  Total ROI:          {roi * 100:+.2f}%")
    lines.append(f"  Realized P&L:       ${total_realized_pnl:+.2f}")
    lines.append(f"  Unrealized P&L:     ${total_unrealized_pnl:+.2f}")
    lines.append(f"  Total Fees Paid:    ${portfolio.total_fees_paid:.4f}")
    lines.append("")

    # Open positions
    lines.append("-" * 40)
    lines.append(f"OPEN POSITIONS ({len(open_pos)})")
    lines.append("-" * 40)
    if open_pos:
        for i, pos in enumerate(open_pos, 1):
            name = pos.get("market_name", "Unknown")
            direction = pos.get("direction", "?")
            size = pos.get("position_size", 0)
            entry = pos.get("entry_price", 0)
            current = pos.get("current_price", entry)
            edge = pos.get("signal_edge", 0)
            conf = pos.get("signal_confidence", "?")
            cat = pos.get("category", "?")
            entry_time = pos.get("entry_time", "?")

            lines.append(f"  #{i}: {direction} on '{name}'")
            lines.append(f"      Category: {cat} | Strategy: {pos.get('strategy', '?')}")
            lines.append(f"      Size: ${size:.2f} | Entry: {entry:.4f} | Current: {current:.4f}")
            lines.append(f"      Edge: {edge:+.3f} | Confidence: {conf} | GT: {pos.get('gt_score', 0):+.3f}")
            lines.append(f"      Entry fees: ${pos.get('entry_fees', 0):.4f}")
            lines.append(f"      Opened: {entry_time}")
            lines.append("")
    else:
        lines.append("  No open positions")
        lines.append("")

    # Closed positions
    lines.append("-" * 40)
    lines.append(f"CLOSED POSITIONS ({len(closed_pos)})")
    lines.append("-" * 40)
    if closed_pos:
        for i, pos in enumerate(closed_pos, 1):
            name = pos.get("market_name", "Unknown")
            direction = pos.get("direction", "?")
            size = pos.get("position_size", 0)
            net = pos.get("net_pnl", 0)
            result_tag = "WIN" if net > 0 else "LOSS"

            lines.append(f"  #{i}: [{result_tag}] {direction} on '{name}'")
            lines.append(f"      Size: ${size:.2f} | Net P&L: ${net:+.4f}")
            lines.append(f"      Entry: {pos.get('entry_price', 0):.4f} -> Exit: {pos.get('exit_price', 0):.4f}")
            lines.append("")
    else:
        lines.append("  No closed positions yet")
        lines.append("")

    # Running statistics
    lines.append("-" * 40)
    lines.append("RUNNING STATISTICS")
    lines.append("-" * 40)
    lines.append(f"  Total trades:       {len(open_pos) + len(closed_pos)}")
    lines.append(f"  Open:               {len(open_pos)}")
    lines.append(f"  Closed:             {len(closed_pos)}")
    lines.append(f"  Winners:            {len(winners)}")
    lines.append(f"  Losers:             {len(losers)}")
    lines.append(f"  Win Rate:           {win_rate * 100:.1f}%")
    lines.append(f"  ROI:                {roi * 100:+.2f}%")
    lines.append(f"  Fees Paid:          ${portfolio.total_fees_paid:.4f}")
    lines.append("")

    # Fee breakdown
    lines.append("-" * 40)
    lines.append("FEE BREAKDOWN")
    lines.append("-" * 40)
    lines.append(f"  Taker fee rate:     {PAPER_TAKER_FEE * 100:.1f}%")
    lines.append(f"  Slippage estimate:  {PAPER_SLIPPAGE * 100:.1f}%")
    lines.append(f"  Gas per trade:      ${PAPER_GAS:.2f}")
    lines.append(f"  Total fees paid:    ${portfolio.total_fees_paid:.4f}")
    lines.append("")

    # Comparison vs backtest expectations
    lines.append("-" * 40)
    lines.append("VS BACKTEST EXPECTATIONS")
    lines.append("-" * 40)
    # Backtest reference values (from the existing backtest)
    bt_win_rate = 0.571  # ~57.1% from typical backtest
    bt_roi = 0.0544      # ~5.44% ROI from typical backtest
    lines.append(f"  Backtest win rate:  {bt_win_rate * 100:.1f}%")
    lines.append(f"  Live win rate:      {win_rate * 100:.1f}%")
    if closed_pos:
        wr_diff = win_rate - bt_win_rate
        lines.append(f"  Difference:         {wr_diff * 100:+.1f}pp")
    else:
        lines.append(f"  Difference:         N/A (no closed trades yet)")
    lines.append(f"  Backtest ROI:       {bt_roi * 100:+.2f}%")
    lines.append(f"  Live ROI:           {roi * 100:+.2f}%")
    roi_diff = roi - bt_roi
    lines.append(f"  ROI difference:     {roi_diff * 100:+.2f}pp")
    lines.append("")

    # Category breakdown
    if open_pos or closed_pos:
        all_pos = open_pos + closed_pos
        politics = [p for p in all_pos if p.get("category") == "politics"]
        macro = [p for p in all_pos if p.get("category") == "macro"]
        lines.append("-" * 40)
        lines.append("CATEGORY BREAKDOWN")
        lines.append("-" * 40)
        lines.append(f"  Politics trades:    {len(politics)}")
        lines.append(f"  Macro trades:       {len(macro)}")
        if politics:
            pol_pnl = sum(p.get("net_pnl", 0) for p in politics if p.get("status") == "closed")
            lines.append(f"  Politics P&L:       ${pol_pnl:+.4f}")
        if macro:
            mac_pnl = sum(p.get("net_pnl", 0) for p in macro if p.get("status") == "closed")
            lines.append(f"  Macro P&L:          ${mac_pnl:+.4f}")
        lines.append("")

    lines.append("=" * 65)

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w") as f:
            f.write(report)
        print(f"Report saved to: {output_path}")

    return report


if __name__ == "__main__":
    report = generate_live_report()
    print(report)
