"""Performance report generator for backtesting results.

Includes category and strategy breakdowns for politics/macro markets.
"""

from backtester import BacktestResult
import numpy as np
import config


def generate_report(result: BacktestResult, filepath: str = None) -> str:
    """Generate a performance report from backtest results."""

    # Trade breakdown by direction
    yes_trades = [t for t in result.trades if t.direction == "BUY_YES"]
    no_trades = [t for t in result.trades if t.direction == "BUY_NO"]
    yes_wins = sum(1 for t in yes_trades if t.net_pnl > 0)
    no_wins = sum(1 for t in no_trades if t.net_pnl > 0)

    # Category breakdown
    politics_trades = [t for t in result.trades if t.category == "politics"]
    macro_trades = [t for t in result.trades if t.category == "macro"]
    politics_wins = sum(1 for t in politics_trades if t.net_pnl > 0)
    macro_wins = sum(1 for t in macro_trades if t.net_pnl > 0)
    politics_pnl = sum(t.net_pnl for t in politics_trades)
    macro_pnl = sum(t.net_pnl for t in macro_trades)

    # Strategy breakdown
    ineff_trades = [t for t in result.trades if t.strategy == "inefficiency"]
    arb_trades = [t for t in result.trades if t.strategy == "cross_market_arb"]
    ineff_wins = sum(1 for t in ineff_trades if t.net_pnl > 0)
    arb_wins = sum(1 for t in arb_trades if t.net_pnl > 0)
    ineff_pnl = sum(t.net_pnl for t in ineff_trades)
    arb_pnl = sum(t.net_pnl for t in arb_trades)

    # Average trade stats
    avg_win = 0.0
    avg_loss = 0.0
    if result.winning_trades > 0:
        avg_win = sum(t.net_pnl for t in result.trades if t.net_pnl > 0) / result.winning_trades
    if result.losing_trades > 0:
        avg_loss = sum(t.net_pnl for t in result.trades if t.net_pnl < 0) / result.losing_trades

    # Profit factor
    gross_profit = sum(t.net_pnl for t in result.trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in result.trades if t.net_pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    best_trade = max(result.trades, key=lambda t: t.net_pnl) if result.trades else None
    worst_trade = min(result.trades, key=lambda t: t.net_pnl) if result.trades else None

    avg_edge_win = np.mean([abs(t.edge) for t in result.trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0
    avg_edge_loss = np.mean([abs(t.edge) for t in result.trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0

    def _wr(wins, total):
        return f"{wins / total * 100:.1f}%" if total > 0 else "N/A"

    lines = []
    lines.append("# Polymarket Trading Signal Bot - Backtest Report")
    lines.append("")
    lines.append("*Focus: Politics/Elections, Macro/Regulatory, Cross-Market Arbitrage*")
    lines.append("*Excluded: Sports, Entertainment*")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Initial Capital | ${result.initial_capital:.2f} |")
    lines.append(f"| Final Capital | ${result.final_capital:.2f} |")
    lines.append(f"| Net P&L | ${result.net_pnl:+.2f} |")
    lines.append(f"| ROI | {result.roi * 100:+.2f}% |")
    lines.append(f"| Total Trades | {result.total_trades} |")
    lines.append(f"| Win Rate | {result.win_rate * 100:.1f}% |")
    lines.append(f"| Profit Factor | {profit_factor:.2f} |")
    lines.append(f"| Sharpe Ratio (annualized) | {result.sharpe_ratio:.2f} |")
    lines.append(f"| Max Drawdown | {result.max_drawdown * 100:.2f}% |")
    lines.append(f"| Total Fees Paid | ${result.total_fees:.2f} |")
    lines.append("")

    lines.append("## Category Breakdown")
    lines.append("")
    lines.append("| Category | Trades | Wins | Win Rate | Net P&L |")
    lines.append("|----------|--------|------|----------|---------|")
    lines.append(f"| Politics/Elections | {len(politics_trades)} | {politics_wins} | {_wr(politics_wins, len(politics_trades))} | ${politics_pnl:+.2f} |")
    lines.append(f"| Macro/Regulatory | {len(macro_trades)} | {macro_wins} | {_wr(macro_wins, len(macro_trades))} | ${macro_pnl:+.2f} |")
    lines.append("")

    lines.append("## Strategy Breakdown")
    lines.append("")
    lines.append("| Strategy | Trades | Wins | Win Rate | Net P&L |")
    lines.append("|----------|--------|------|----------|---------|")
    lines.append(f"| Inefficiency Detection | {len(ineff_trades)} | {ineff_wins} | {_wr(ineff_wins, len(ineff_trades))} | ${ineff_pnl:+.2f} |")
    lines.append(f"| Cross-Market Arbitrage | {len(arb_trades)} | {arb_wins} | {_wr(arb_wins, len(arb_trades))} | ${arb_pnl:+.2f} |")
    lines.append("")

    lines.append("## Game Theory Metrics")
    lines.append("")
    # GT score stats
    gt_trades = [t for t in result.trades if hasattr(t, "gt_score")]
    if gt_trades:
        avg_gt = np.mean([t.gt_score for t in gt_trades])
        avg_gt_win = np.mean([t.gt_score for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0
        avg_gt_loss = np.mean([t.gt_score for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0
        avg_nash = np.mean([t.gt_nash for t in gt_trades])
        avg_beauty = np.mean([t.gt_beauty for t in gt_trades])
        avg_whale = np.mean([t.gt_whale for t in gt_trades])
        avg_liq = np.mean([t.gt_liquidity for t in gt_trades])
        avg_combined = np.mean([t.combined_score for t in gt_trades])
        avg_combined_win = np.mean([t.combined_score for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0
        avg_combined_loss = np.mean([t.combined_score for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0

        lines.append("| Model | Avg Score (All) | Avg Score (Winners) | Avg Score (Losers) |")
        lines.append("|-------|----------------|--------------------|--------------------|")
        lines.append(f"| Nash Equilibrium | {avg_nash:+.3f} | {np.mean([t.gt_nash for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0:+.3f} | {np.mean([t.gt_nash for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0:+.3f} |")
        lines.append(f"| Beauty Contest | {avg_beauty:+.3f} | {np.mean([t.gt_beauty for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0:+.3f} | {np.mean([t.gt_beauty for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0:+.3f} |")
        lines.append(f"| Whale Tracker | {avg_whale:+.3f} | {np.mean([t.gt_whale for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0:+.3f} | {np.mean([t.gt_whale for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0:+.3f} |")
        lines.append(f"| Liquidity Score | {avg_liq:.3f} | {np.mean([t.gt_liquidity for t in gt_trades if t.net_pnl > 0]) if result.winning_trades > 0 else 0:.3f} | {np.mean([t.gt_liquidity for t in gt_trades if t.net_pnl < 0]) if result.losing_trades > 0 else 0:.3f} |")
        lines.append(f"| *GT Total* | *{avg_gt:+.3f}* | *{avg_gt_win:+.3f}* | *{avg_gt_loss:+.3f}* |")
        lines.append(f"| *Combined Score* | *{avg_combined:.3f}* | *{avg_combined_win:.3f}* | *{avg_combined_loss:.3f}* |")
    else:
        lines.append("No game theory data available.")
    lines.append("")

    lines.append("## Direction Breakdown")
    lines.append("")
    lines.append("| Direction | Trades | Wins | Win Rate |")
    lines.append("|-----------|--------|------|----------|")
    lines.append(f"| BUY YES | {len(yes_trades)} | {yes_wins} | {_wr(yes_wins, len(yes_trades))} |")
    lines.append(f"| BUY NO | {len(no_trades)} | {no_wins} | {_wr(no_wins, len(no_trades))} |")
    lines.append("")

    lines.append("## Risk Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Avg Winning Trade | ${avg_win:+.2f} |")
    lines.append(f"| Avg Losing Trade | ${avg_loss:+.2f} |")
    if best_trade:
        lines.append(f"| Best Trade | ${best_trade.net_pnl:+.2f} ({best_trade.category}, {best_trade.strategy}, Day {best_trade.entry_day}) |")
    if worst_trade:
        lines.append(f"| Worst Trade | ${worst_trade.net_pnl:+.2f} ({worst_trade.category}, {worst_trade.strategy}, Day {worst_trade.entry_day}) |")
    lines.append(f"| Avg Edge (Winners) | {avg_edge_win:.3f} |")
    lines.append(f"| Avg Edge (Losers) | {avg_edge_loss:.3f} |")
    lines.append("")

    lines.append("## Fee Impact")
    lines.append("")
    lines.append("| Fee Type | Estimated Total |")
    lines.append("|----------|----------------|")
    taker_fees = sum(t.position_size * 0.02 for t in result.trades)
    slippage_fees = sum(t.position_size * 0.005 for t in result.trades)
    gas_fees = len(result.trades) * 0.02  # Entry + exit gas
    lines.append(f"| Taker Fees (2%) | ${taker_fees:.2f} |")
    lines.append(f"| Slippage (0.5%) | ${slippage_fees:.2f} |")
    lines.append(f"| Gas Fees | ${gas_fees:.2f} |")
    lines.append(f"| *Total Fees* | *${result.total_fees:.2f}* |")
    lines.append(f"| Gross P&L (before fees) | ${result.total_pnl:+.2f} |")
    lines.append(f"| Net P&L (after fees) | ${result.net_pnl:+.2f} |")
    lines.append("")

    lines.append("## Strategy Notes")
    lines.append("")
    lines.append("- *Market Focus*: Only Politics/Elections and Macro/Regulatory markets.")
    lines.append("  Sports, entertainment, and pop culture markets are excluded.")
    lines.append("- *Inefficiency Detection*: Category-aware fair value estimation.")
    lines.append("  Politics markets weight polling trends more heavily;")
    lines.append("  Macro markets weight price extremes (binary event outcomes).")
    lines.append(f"- *Cross-Market Arbitrage*: Compares Polymarket prices against")
    lines.append(f"  Metaculus/Kalshi consensus. Trades when divergence exceeds {config.CROSS_MARKET_ARB_THRESHOLD * 100:.0f}%.")
    lines.append(f"- *Kelly Criterion*: Quarter-Kelly sizing, max {config.MAX_POSITION_SIZE * 100:.0f}% per trade, {config.MAX_KELLY_FRACTION * 100:.0f}% Kelly cap.")
    lines.append(f"- *Fee-Aware*: All signals require positive EV after {config.TAKER_FEE_RATE * 100:.0f}% taker + {config.SLIPPAGE_ESTIMATE * 100:.1f}% slippage + gas.")
    lines.append("- *Game Theory Scoring*: Four models augment base signals:")
    lines.append("  - Nash Equilibrium: Flags disequilibrium (price vs fair value, weighted by volume/spread)")
    lines.append("  - Keynesian Beauty Contest: Tracks perception vs reality convergence")
    lines.append("  - Bayesian Whale Tracker: Detects large order flow and informed trading")
    lines.append("  - Thin Liquidity Exploiter: Amplifies edge in low-liquidity markets")
    lines.append("  - Final score = base edge + aligned GT boost. GT veto if strongly misaligned.")
    lines.append("")

    lines.append("## Equity Curve (sampled)")
    lines.append("")
    curve = result.equity_curve
    step = max(1, len(curve) // 10)
    lines.append("| Day | Equity |")
    lines.append("|-----|--------|")
    for i in range(0, len(curve), step):
        lines.append(f"| {i} | ${curve[i]:.2f} |")
    if (len(curve) - 1) % step != 0:
        lines.append(f"| {len(curve) - 1} | ${curve[-1]:.2f} |")

    report = "\n".join(lines)

    if filepath:
        with open(filepath, "w") as f:
            f.write(report)

    return report
