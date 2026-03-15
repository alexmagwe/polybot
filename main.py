#!/usr/bin/env python3
"""Main entry point for Polymarket trading signal bot.

Focus: Politics/Elections, Macro/Regulatory, Cross-Market Arbitrage.
Excludes: Sports, Entertainment.
"""

import argparse
import json

import numpy as np

import config
from backtester import Backtester, generate_simulated_markets
from signals import SignalGenerator
from report import generate_report


def run_backtest():
    """Run the full backtesting pipeline."""
    print("=" * 65)
    print("Polymarket Trading Signal Bot - Backtest Pipeline")
    print("Focus: Politics | Macro/Regulatory | Cross-Market Arb")
    print("=" * 65)

    # Step 1: Generate category-specific simulated market data
    print("\n[1/4] Generating simulated politics & macro market data...")
    markets = generate_simulated_markets(
        num_markets=config.NUM_SIMULATED_MARKETS,
        num_days=config.NUM_SIMULATED_DAYS,
        seed=42,
    )
    n_pol = sum(1 for m in markets if m["category"] == "politics")
    n_mac = sum(1 for m in markets if m["category"] == "macro")
    print(f"  Generated {len(markets)} markets ({n_pol} politics, {n_mac} macro)")
    print(f"  Simulation period: {config.NUM_SIMULATED_DAYS} days")

    # Step 2: Run backtest with both strategies
    print("\n[2/4] Running backtest (inefficiency + cross-market arb)...")
    backtester = Backtester(capital=config.INITIAL_CAPITAL)
    result = backtester.run(markets, num_days=config.NUM_SIMULATED_DAYS)

    n_ineff = sum(1 for t in result.trades if t.strategy == "inefficiency")
    n_arb = sum(1 for t in result.trades if t.strategy == "cross_market_arb")

    print(f"  Completed {result.total_trades} trades ({n_ineff} inefficiency, {n_arb} cross-market arb)")
    print(f"  Win rate: {result.win_rate * 100:.1f}%")
    print(f"  Net P&L: ${result.net_pnl:+.2f}")
    print(f"  ROI: {result.roi * 100:+.2f}%")

    # Step 3: Generate live signals (demo)
    print("\n[3/4] Generating current signals (demo with simulated data)...")
    signal_gen = SignalGenerator(capital=result.final_capital)

    demo_markets = []
    for m in markets:
        last_day = config.NUM_SIMULATED_DAYS - 1
        avg_vol = np.mean(m["volumes"][-10:])
        demo_markets.append({
            "market_id": str(m["id"]),
            "market_name": m["name"],
            "market_price": m["market_prices"][last_day],
            "volume_ratio": m["volumes"][last_day] / avg_vol if avg_vol > 0 else 1.0,
            "price_history": m["market_prices"][-15:],
            "spread": m["spreads"][last_day],
            "category": m["category"],
            "external_price": m["external_prices"][last_day],
            "volume_history": m["volumes"][-15:],
        })

    signals = signal_gen.scan_markets(demo_markets)
    if signals:
        print(f"  Found {len(signals)} actionable signals:")
        for sig in signals[:5]:
            print(f"    {sig}")
    else:
        print("  No actionable signals at current prices")

    # Step 4: Generate report
    print("\n[4/4] Generating performance report...")
    report_path = "/workspace/group/polymarket-bot/backtest_report.md"
    report = generate_report(result, filepath=report_path)
    print(f"  Report saved to: {report_path}")

    print("\n" + "=" * 65)
    print("Pipeline complete!")
    print("=" * 65)

    return result, signals


def run_paper():
    """Run paper trading mode with live data."""
    from paper_trader import run_paper_trading
    from live_report import generate_live_report

    summary = run_paper_trading()

    # Save initial signals
    signals_path = "/workspace/group/polymarket-bot/initial_signals.json"
    with open(signals_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSignals saved to: {signals_path}")

    # Generate and display live report
    print("\n")
    report = generate_live_report()
    print(report)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Trading Signal Bot")
    parser.add_argument("--paper", action="store_true", help="Run in paper trading mode with live data")
    parser.add_argument("--report", action="store_true", help="Show live paper trading report only")
    args = parser.parse_args()

    if args.report:
        from live_report import generate_live_report
        report = generate_live_report()
        print(report)
    elif args.paper:
        run_paper()
    else:
        result, signals = run_backtest()
