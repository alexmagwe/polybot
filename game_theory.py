"""Game theory modules for Polymarket trading signal bot.

Four models that produce scoring signals to augment the base strategies:
1. Nash Equilibrium Detector
2. Keynesian Beauty Contest Model
3. Bayesian Game Theory / Whale Tracker
4. Mechanism Design / Thin Liquidity Exploiter
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class GameTheoryScore:
    """Combined game theory score for a market."""
    nash_score: float = 0.0
    beauty_contest_score: float = 0.0
    whale_score: float = 0.0
    liquidity_score: float = 0.0
    total_score: float = 0.0
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        self.total_score = (
            self.nash_score
            + self.beauty_contest_score
            + self.whale_score
            + self.liquidity_score
        )


class NashEquilibriumDetector:
    """Detects deviations from Nash equilibrium pricing.

    In a prediction market at Nash equilibrium, the price reflects the
    consensus probability and no trader can improve their expected payoff
    by unilaterally changing their position. When price deviates from
    fair value, we have a disequilibrium that informed traders can exploit
    before the market corrects.

    Score: Higher when the market is further from equilibrium (larger
    deviation between price and fair value, confirmed by volume patterns).
    """

    def score(
        self,
        market_price: float,
        fair_value: float,
        volume_ratio: float,
        spread: float,
    ) -> tuple[float, dict]:
        """Score the degree of Nash disequilibrium.

        Returns (score, details) where score is in [-1, 1].
        Positive = market undervalued (buy YES), negative = overvalued (buy NO).
        """
        deviation = fair_value - market_price

        # The equilibrium deviation is more exploitable when:
        # 1. Volume is low (fewer participants = weaker equilibrium)
        # 2. Spread is wide (market maker uncertainty)
        volume_factor = 1.0 / max(volume_ratio, 0.5)  # Higher when volume is low
        spread_factor = min(spread / 0.03, 2.0)  # Higher when spread is wide

        # Disequilibrium strength: deviation weighted by market conditions
        disequilibrium = deviation * (0.6 + 0.2 * volume_factor + 0.2 * spread_factor)

        # Clip to [-1, 1] range
        score = float(np.clip(disequilibrium * 3, -1.0, 1.0))

        details = {
            "deviation": deviation,
            "volume_factor": volume_factor,
            "spread_factor": spread_factor,
            "disequilibrium": disequilibrium,
        }
        return score, details


class KeynesianBeautyContest:
    """Keynesian Beauty Contest model for prediction markets.

    Keynes's insight: rational traders don't just predict outcomes, they predict
    what other traders will predict. In prediction markets, this means the price
    sometimes reflects crowd *perception* rather than *reality*.

    This model tracks how crowd sentiment shifts over time and identifies
    convergence/divergence between perception (price trend) and likely reality
    (fair value trend). Signals entries when perception is about to converge
    to reality.

    Score: Higher when perception diverges from reality and momentum suggests
    upcoming convergence.
    """

    def score(
        self,
        price_history: list[float],
        fair_value: float,
        volume_history: list[float] = None,
    ) -> tuple[float, dict]:
        """Score the beauty contest signal.

        Returns (score, details) where score is in [-1, 1].
        """
        if len(price_history) < 5:
            return 0.0, {"reason": "insufficient_history"}

        recent = price_history[-5:]
        older = price_history[-10:-5] if len(price_history) >= 10 else price_history[:5]

        # Perception = recent price trend
        perception = np.mean(recent)
        # Past perception = older price trend
        past_perception = np.mean(older)

        # Perception momentum: is the crowd moving toward or away from fair value?
        perception_shift = perception - past_perception
        reality_gap = fair_value - perception

        # Convergence signal: perception is moving toward reality
        # (perception_shift and reality_gap have the same sign)
        converging = (perception_shift * reality_gap) > 0

        # Divergence signal: crowd is moving away from reality
        diverging = (perception_shift * reality_gap) < 0

        # The best signal is when perception has diverged from reality
        # but is about to converge (mean reversion into fair value).
        # We want to trade *before* the convergence.

        # Gap magnitude
        gap_magnitude = abs(reality_gap)

        # Trend acceleration: is the shift accelerating or decelerating?
        if len(price_history) >= 8:
            very_recent = price_history[-3:]
            slightly_older = price_history[-6:-3]
            recent_momentum = np.mean(very_recent) - np.mean(slightly_older)
            # Deceleration of divergence = upcoming reversal
            if diverging and abs(recent_momentum) < abs(perception_shift):
                # Divergence is slowing — reversal likely
                gap_magnitude *= 1.3

        # Volume confirmation: rising volume during gap = stronger signal
        vol_boost = 1.0
        if volume_history and len(volume_history) >= 5:
            recent_vol = np.mean(volume_history[-3:])
            avg_vol = np.mean(volume_history[-10:])
            if avg_vol > 0 and recent_vol > avg_vol:
                vol_boost = min(recent_vol / avg_vol, 1.5)

        score = float(np.clip(
            np.sign(reality_gap) * gap_magnitude * vol_boost * 3,
            -1.0, 1.0
        ))

        details = {
            "perception": perception,
            "past_perception": past_perception,
            "perception_shift": perception_shift,
            "reality_gap": reality_gap,
            "converging": converging,
            "diverging": diverging,
            "vol_boost": vol_boost,
        }
        return score, details


class BayesianWhaleTracker:
    """Bayesian Game Theory / Whale Tracker.

    Analyzes order book for large orders (whales) and uses order flow
    imbalance as a signal that informed traders are moving. Updates
    probability estimates based on the Bayesian inference:

    P(outcome | whale_action) ~ P(whale_action | outcome) * P(outcome)

    In simulation, we model whale activity via volume spikes and
    price jumps that indicate large order fills.

    Score: Higher when whale activity is detected and aligned with
    a directional signal.
    """

    def __init__(self, whale_volume_threshold: float = 2.0):
        self.whale_threshold = whale_volume_threshold

    def score(
        self,
        price_history: list[float],
        volume_history: list[float],
        order_book: dict = None,
    ) -> tuple[float, dict]:
        """Score whale activity signal.

        Args:
            price_history: Recent price series
            volume_history: Recent volume series
            order_book: Optional order book data (bids/asks with sizes)

        Returns (score, details) where score is in [-1, 1].
        """
        if len(price_history) < 3 or len(volume_history) < 3:
            return 0.0, {"reason": "insufficient_data"}

        # Detect whale activity via volume spikes
        recent_vol = volume_history[-1]
        avg_vol = np.mean(volume_history[-10:]) if len(volume_history) >= 10 else np.mean(volume_history)
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        whale_detected = vol_ratio >= self.whale_threshold

        # Detect price impact: large price move concurrent with volume spike
        price_change = price_history[-1] - price_history[-2]
        avg_price_change = np.mean(np.abs(np.diff(price_history[-10:]))) if len(price_history) >= 10 else abs(price_change)
        price_impact = abs(price_change) / max(avg_price_change, 0.001)

        # Order flow imbalance from order book (if available)
        imbalance = 0.0
        if order_book:
            bids = order_book.get("bids", [])
            asks = order_book.get("asks", [])
            bid_depth = sum(float(b.get("size", 0)) for b in bids[:5])
            ask_depth = sum(float(a.get("size", 0)) for a in asks[:5])
            total_depth = bid_depth + ask_depth
            if total_depth > 0:
                imbalance = (bid_depth - ask_depth) / total_depth  # [-1, 1]

        # Bayesian update: if whale is detected, the direction of their
        # trade is informative. We infer direction from price movement.
        if whale_detected:
            # Direction of whale trade: positive price_change = whale buying YES
            whale_direction = np.sign(price_change)
            # Confidence scales with volume ratio and price impact
            confidence = min((vol_ratio - self.whale_threshold) * 0.5, 1.0)
            confidence *= min(price_impact, 2.0) / 2.0

            score = float(np.clip(whale_direction * confidence, -1.0, 1.0))
        else:
            # No whale detected; use mild order book imbalance if available
            score = float(np.clip(imbalance * 0.3, -1.0, 1.0))

        details = {
            "vol_ratio": vol_ratio,
            "whale_detected": whale_detected,
            "price_change": price_change,
            "price_impact": price_impact,
            "order_book_imbalance": imbalance,
        }
        return score, details


class ThinLiquidityExploiter:
    """Mechanism Design / Thin Liquidity Exploiter.

    Flags markets with thin liquidity where prices may be set by few
    traders. In these markets, informed research can exploit prices more
    easily because:
    - Fewer participants = weaker price discovery
    - Wide spreads = higher profit per trade (if correct)
    - Low volume = prices respond slowly to new information

    Score: Higher for thin-liquidity markets where research-based
    edge is more likely to persist.
    """

    def __init__(
        self,
        thin_volume_threshold: float = 0.5,
        wide_spread_threshold: float = 0.04,
    ):
        self.thin_vol_threshold = thin_volume_threshold
        self.wide_spread_threshold = wide_spread_threshold

    def score(
        self,
        volume_ratio: float,
        spread: float,
        order_book: dict = None,
        price_history: list[float] = None,
    ) -> tuple[float, dict]:
        """Score thin liquidity exploitation opportunity.

        Returns (score, details) where score is in [0, 1].
        Higher = thinner liquidity = more exploitable.
        Note: this score is always non-negative (it amplifies edge, not direction).
        """
        # Volume thinness: lower volume = more exploitable
        vol_score = 0.0
        if volume_ratio < self.thin_vol_threshold:
            vol_score = (self.thin_vol_threshold - volume_ratio) / self.thin_vol_threshold
        vol_score = min(vol_score, 1.0)

        # Spread width: wider spread = prices less efficient
        spread_score = 0.0
        if spread > self.wide_spread_threshold:
            spread_score = min((spread - self.wide_spread_threshold) / 0.06, 1.0)

        # Order book depth (if available): shallow = more exploitable
        depth_score = 0.0
        if order_book:
            bids = order_book.get("bids", [])
            asks = order_book.get("asks", [])
            total_depth = sum(float(b.get("size", 0)) for b in bids[:5])
            total_depth += sum(float(a.get("size", 0)) for a in asks[:5])
            # Shallow book = high score
            if total_depth < 1000:
                depth_score = (1000 - total_depth) / 1000
            depth_score = min(depth_score, 1.0)

        # Price autocorrelation: high autocorrelation in thin markets means
        # prices are sticky and slow to update
        autocorr_score = 0.0
        if price_history and len(price_history) >= 5:
            prices = np.array(price_history[-10:])
            if len(prices) >= 4:
                returns = np.diff(prices)
                if len(returns) >= 3 and np.std(returns) > 0:
                    # Lag-1 autocorrelation
                    autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
                    if not np.isnan(autocorr) and autocorr > 0.2:
                        autocorr_score = min(autocorr, 1.0)

        # Combined score (non-directional amplifier)
        combined = (
            0.35 * vol_score
            + 0.30 * spread_score
            + 0.20 * depth_score
            + 0.15 * autocorr_score
        )

        is_thin = combined > 0.3

        details = {
            "vol_score": vol_score,
            "spread_score": spread_score,
            "depth_score": depth_score,
            "autocorr_score": autocorr_score,
            "is_thin_liquidity": is_thin,
        }
        return float(np.clip(combined, 0.0, 1.0)), details


class GameTheoryEngine:
    """Combines all four game theory models into a single scoring engine."""

    def __init__(self):
        self.nash = NashEquilibriumDetector()
        self.beauty_contest = KeynesianBeautyContest()
        self.whale_tracker = BayesianWhaleTracker()
        self.liquidity_exploiter = ThinLiquidityExploiter()

    def evaluate(
        self,
        market_price: float,
        fair_value: float,
        volume_ratio: float,
        spread: float,
        price_history: list[float],
        volume_history: list[float] = None,
        order_book: dict = None,
    ) -> GameTheoryScore:
        """Run all game theory models and return combined score.

        Args:
            market_price: Current market price
            fair_value: Estimated fair value from base strategy
            volume_ratio: Current/avg volume ratio
            spread: Current bid-ask spread
            price_history: Recent price series
            volume_history: Recent volume series (optional)
            order_book: Order book data (optional)

        Returns:
            GameTheoryScore with individual and combined scores
        """
        if volume_history is None:
            volume_history = []

        # 1. Nash Equilibrium
        nash_score, nash_details = self.nash.score(
            market_price, fair_value, volume_ratio, spread
        )

        # 2. Keynesian Beauty Contest
        beauty_score, beauty_details = self.beauty_contest.score(
            price_history, fair_value, volume_history or None
        )

        # 3. Whale Tracker
        whale_score, whale_details = self.whale_tracker.score(
            price_history, volume_history if volume_history else [1.0] * 3, order_book
        )

        # 4. Thin Liquidity
        liq_score, liq_details = self.liquidity_exploiter.score(
            volume_ratio, spread, order_book, price_history
        )

        # Weight the directional scores and the amplifier
        # Nash, Beauty Contest, and Whale are directional ([-1, 1])
        # Liquidity is a non-directional amplifier ([0, 1])
        directional_score = (
            0.35 * nash_score
            + 0.40 * beauty_score
            + 0.25 * whale_score
        )

        # Liquidity amplifies the directional signal
        amplified_score = directional_score * (1.0 + 0.5 * liq_score)

        return GameTheoryScore(
            nash_score=nash_score,
            beauty_contest_score=beauty_score,
            whale_score=whale_score,
            liquidity_score=liq_score,
            total_score=amplified_score,
            details={
                "nash": nash_details,
                "beauty_contest": beauty_details,
                "whale": whale_details,
                "liquidity": liq_details,
            },
        )
