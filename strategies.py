"""Trading strategies for Polymarket signal bot.

Focused on Politics/Elections, Macro/Regulatory, and Cross-Market Arbitrage.
Sports and entertainment markets are excluded.
"""

import numpy as np
import config


class MarketInefficiencyDetector:
    """Detects mispricings in politics and macro/regulatory markets.

    Category-aware adjustments:
    - Politics: higher weight on trend/momentum (polls shift prices predictably)
    - Macro: higher weight on price level (binary events like rate decisions)
    """

    def __init__(self, threshold: float = config.INEFFICIENCY_THRESHOLD):
        self.threshold = threshold

    def estimate_resolution_prob(
        self,
        market_price: float,
        volume_ratio: float,
        price_history: list[float],
        spread: float,
        category: str = "politics",
    ) -> float:
        """Estimate probability of YES resolution using trend and momentum signals.

        Category-aware: politics markets weight trends more heavily (polling data
        drives predictable shifts), while macro markets weight price level
        (binary event outcomes like FDA approval tend to cluster at extremes).
        """
        if len(price_history) < 5:
            return market_price

        # Signal 1: Trend direction
        recent_prices = price_history[-10:]
        trend_slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        trend_signal = np.clip(trend_slope * 5, -0.15, 0.15)

        # Signal 2: Price level — extreme prices are informative
        uncertainty = 1.0 - 2.0 * abs(market_price - 0.5)
        level_weight = 0.5 + 0.5 * uncertainty

        # Signal 3: Volume-weighted momentum
        momentum = 0.0
        if len(price_history) >= 3:
            short_ma = np.mean(price_history[-3:])
            long_ma = np.mean(price_history[-10:])
            momentum = (short_ma - long_ma) * volume_ratio * 0.3
            momentum = np.clip(momentum, -0.10, 0.10)

        # Signal 4: Spread as confidence indicator
        spread_factor = min(spread / 0.05, 2.0)

        # Category-specific weighting
        if category == "politics":
            # Politics: trends are more reliable (poll-driven), weight momentum higher
            trend_weight = 1.3
            momentum_weight = 1.2
        elif category == "macro":
            # Macro/regulatory: binary events, price extremes are very informative
            trend_weight = 0.8
            momentum_weight = 0.9
            level_weight *= 1.3  # Trust extreme prices more for binary events
        else:
            trend_weight = 1.0
            momentum_weight = 1.0

        adjustment = (
            trend_signal * level_weight * trend_weight
            + momentum * momentum_weight
        ) * (0.5 + 0.5 * spread_factor)

        fair_value = np.clip(market_price + adjustment, 0.02, 0.98)
        return float(fair_value)

    def detect(
        self,
        market_price: float,
        volume_ratio: float,
        price_history: list[float],
        spread: float,
        category: str = "politics",
    ) -> dict:
        """Detect if a market is mispriced relative to likely resolution."""
        fair_value = self.estimate_resolution_prob(
            market_price, volume_ratio, price_history, spread, category
        )
        edge = fair_value - market_price
        actionable = abs(edge) >= self.threshold

        direction = "BUY_YES" if edge > 0 else "BUY_NO"

        # Directional filter: require fair value to lean toward predicted side
        if direction == "BUY_YES" and fair_value < 0.45:
            actionable = False
        if direction == "BUY_NO" and fair_value > 0.55:
            actionable = False

        return {
            "market_price": market_price,
            "fair_value": fair_value,
            "edge": edge,
            "abs_edge": abs(edge),
            "direction": direction,
            "actionable": actionable,
            "category": category,
            "strategy": "inefficiency",
        }


class CrossMarketArbitrage:
    """Detects arbitrage opportunities between Polymarket and external platforms.

    Compares implied probabilities across Polymarket, Metaculus, and Kalshi.
    When a significant divergence is found, generates a signal to trade toward
    the external consensus.
    """

    def __init__(self, threshold: float = config.CROSS_MARKET_ARB_THRESHOLD):
        self.threshold = threshold

    def detect(
        self,
        polymarket_price: float,
        external_price: float,
        source: str = "metaculus",
    ) -> dict:
        """Detect cross-platform arbitrage opportunity.

        Args:
            polymarket_price: Polymarket YES implied probability
            external_price: External platform probability (Metaculus/Kalshi)
            source: Name of external source

        Returns:
            Signal dict with arb details
        """
        divergence = external_price - polymarket_price
        abs_div = abs(divergence)
        actionable = abs_div >= self.threshold

        direction = "BUY_YES" if divergence > 0 else "BUY_NO"

        # Use external price as fair value estimate
        fair_value = external_price

        return {
            "market_price": polymarket_price,
            "fair_value": fair_value,
            "edge": divergence,
            "abs_edge": abs_div,
            "direction": direction,
            "actionable": actionable,
            "source": source,
            "strategy": "cross_market_arb",
        }


class KellyCriterion:
    """Kelly Criterion position sizing with fractional Kelly for safety."""

    def __init__(
        self,
        max_fraction: float = config.MAX_KELLY_FRACTION,
        max_position_pct: float = config.MAX_POSITION_SIZE,
        min_position: float = config.MIN_POSITION_SIZE,
    ):
        self.max_fraction = max_fraction
        self.max_position_pct = max_position_pct
        self.min_position = min_position

    def kelly_fraction(self, win_prob: float, odds: float) -> float:
        """Calculate the Kelly fraction (quarter-Kelly applied)."""
        if odds <= 0 or win_prob <= 0 or win_prob >= 1:
            return 0.0

        lose_prob = 1.0 - win_prob
        kelly = (win_prob * odds - lose_prob) / odds
        kelly *= 0.25

        return max(0.0, min(kelly, self.max_fraction))

    def position_size(
        self,
        capital: float,
        market_price: float,
        fair_value: float,
        direction: str,
    ) -> dict:
        """Calculate position size for a trade."""
        if direction == "BUY_YES":
            entry_price = market_price
            win_prob = fair_value
            odds = (1.0 - entry_price) / entry_price if entry_price > 0 else 0
        else:
            entry_price = 1.0 - market_price
            win_prob = 1.0 - fair_value
            odds = (1.0 - entry_price) / entry_price if entry_price > 0 else 0

        effective_odds = odds * (1.0 - config.TAKER_FEE_RATE) - config.SLIPPAGE_ESTIMATE
        kf_after_fees = self.kelly_fraction(win_prob, effective_odds)

        raw_size = capital * kf_after_fees
        max_size = capital * self.max_position_pct
        size = min(raw_size, max_size)

        if size < self.min_position:
            size = 0.0

        ev_per_dollar = win_prob * odds - (1.0 - win_prob)
        ev_after_fees = ev_per_dollar - config.TAKER_FEE_RATE - config.SLIPPAGE_ESTIMATE

        return {
            "kelly_fraction": kf_after_fees,
            "position_size": round(size, 2),
            "entry_price": entry_price,
            "direction": direction,
            "win_prob": win_prob,
            "odds": odds,
            "ev_per_dollar": ev_per_dollar,
            "ev_after_fees": ev_after_fees,
        }
