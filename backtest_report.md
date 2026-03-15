# Polymarket Trading Signal Bot - Backtest Report

*Focus: Politics/Elections, Macro/Regulatory, Cross-Market Arbitrage*
*Excluded: Sports, Entertainment*

## Summary

| Metric | Value |
|--------|-------|
| Initial Capital | $100.00 |
| Final Capital | $125.28 |
| Net P&L | $+25.28 |
| ROI | +25.28% |
| Total Trades | 71 |
| Win Rate | 69.0% |
| Profit Factor | 2.62 |
| Sharpe Ratio (annualized) | 5.25 |
| Max Drawdown | 5.50% |
| Total Fees Paid | $15.23 |

## Category Breakdown

| Category | Trades | Wins | Win Rate | Net P&L |
|----------|--------|------|----------|---------|
| Politics/Elections | 30 | 20 | 66.7% | $+8.42 |
| Macro/Regulatory | 41 | 29 | 70.7% | $+16.86 |

## Strategy Breakdown

| Strategy | Trades | Wins | Win Rate | Net P&L |
|----------|--------|------|----------|---------|
| Inefficiency Detection | 38 | 28 | 73.7% | $+10.51 |
| Cross-Market Arbitrage | 33 | 21 | 63.6% | $+14.77 |

## Game Theory Metrics

| Model | Avg Score (All) | Avg Score (Winners) | Avg Score (Losers) |
|-------|----------------|--------------------|--------------------|
| Nash Equilibrium | -0.015 | -0.045 | +0.051 |
| Beauty Contest | -0.023 | -0.061 | +0.062 |
| Whale Tracker | -0.001 | -0.002 | +0.000 |
| Liquidity Score | 0.056 | 0.058 | 0.054 |
| *GT Total* | *+0.017* | *-0.050* | *+0.167* |
| *Combined Score* | *0.178* | *0.179* | *0.174* |

## Direction Breakdown

| Direction | Trades | Wins | Win Rate |
|-----------|--------|------|----------|
| BUY YES | 34 | 21 | 61.8% |
| BUY NO | 37 | 28 | 75.7% |

## Risk Metrics

| Metric | Value |
|--------|-------|
| Avg Winning Trade | $+0.83 |
| Avg Losing Trade | $-0.71 |
| Best Trade | $+5.39 (macro, cross_market_arb, Day 47) |
| Worst Trade | $-3.55 (macro, cross_market_arb, Day 56) |
| Avg Edge (Winners) | 0.108 |
| Avg Edge (Losers) | 0.104 |

## Fee Impact

| Fee Type | Estimated Total |
|----------|----------------|
| Taker Fees (2%) | $10.20 |
| Slippage (0.5%) | $2.55 |
| Gas Fees | $1.42 |
| *Total Fees* | *$15.23* |
| Gross P&L (before fees) | $+40.51 |
| Net P&L (after fees) | $+25.28 |

## Strategy Notes

- *Market Focus*: Only Politics/Elections and Macro/Regulatory markets.
  Sports, entertainment, and pop culture markets are excluded.
- *Inefficiency Detection*: Category-aware fair value estimation.
  Politics markets weight polling trends more heavily;
  Macro markets weight price extremes (binary event outcomes).
- *Cross-Market Arbitrage*: Compares Polymarket prices against
  Metaculus/Kalshi consensus. Trades when divergence exceeds 10%.
- *Kelly Criterion*: Quarter-Kelly sizing, max 10% per trade, 25% Kelly cap.
- *Fee-Aware*: All signals require positive EV after 2% taker + 0.5% slippage + gas.
- *Game Theory Scoring*: Four models augment base signals:
  - Nash Equilibrium: Flags disequilibrium (price vs fair value, weighted by volume/spread)
  - Keynesian Beauty Contest: Tracks perception vs reality convergence
  - Bayesian Whale Tracker: Detects large order flow and informed trading
  - Thin Liquidity Exploiter: Amplifies edge in low-liquidity markets
  - Final score = base edge + aligned GT boost. GT veto if strongly misaligned.

## Equity Curve (sampled)

| Day | Equity |
|-----|--------|
| 0 | $100.00 |
| 5 | $100.00 |
| 10 | $105.52 |
| 15 | $108.20 |
| 20 | $113.86 |
| 25 | $114.63 |
| 30 | $117.67 |
| 35 | $119.90 |
| 40 | $121.58 |
| 45 | $129.17 |
| 50 | $125.28 |