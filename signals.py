"""Signal generator for Polymarket trading opportunities.

Focused on Politics/Elections, Macro/Regulatory, and Cross-Market Arbitrage.
Sports and entertainment markets are excluded.
Combines base strategy scores with game theory scoring.
"""

from dataclasses import dataclass
import config
from api_client import classify_market
from strategies import MarketInefficiencyDetector, CrossMarketArbitrage, KellyCriterion
from game_theory import GameTheoryEngine, GameTheoryScore


@dataclass
class Signal:
    market_id: str
    market_name: str
    category: str
    strategy: str
    direction: str
    market_price: float
    fair_value: float
    edge: float
    position_size: float
    kelly_fraction: float
    ev_after_fees: float
    confidence: str  # LOW, MEDIUM, HIGH
    combined_score: float = 0.0
    gt_score: float = 0.0
    gt_nash: float = 0.0
    gt_beauty: float = 0.0
    gt_whale: float = 0.0
    gt_liquidity: float = 0.0

    def __str__(self):
        gt_tag = f" GT:{self.gt_score:+.2f}" if abs(self.gt_score) > 0.01 else ""
        return (
            f"[{self.confidence}] [{self.category.upper()}] [{self.strategy}] "
            f"{self.direction} on '{self.market_name}' | "
            f"Price: {self.market_price:.3f} | Fair: {self.fair_value:.3f} | "
            f"Edge: {self.edge:+.3f} | Size: ${self.position_size:.2f} | "
            f"Score: {self.combined_score:.3f}{gt_tag}"
        )


class SignalGenerator:
    """Generates trading signals combining base strategies + game theory."""

    def __init__(self, capital: float = config.INITIAL_CAPITAL):
        self.capital = capital
        self.detector = MarketInefficiencyDetector()
        self.arb_detector = CrossMarketArbitrage()
        self.kelly = KellyCriterion()
        self.gt_engine = GameTheoryEngine()

    def evaluate_market(
        self,
        market_id: str,
        market_name: str,
        market_price: float,
        volume_ratio: float,
        price_history: list[float],
        spread: float,
        category: str = "politics",
        external_price: float = None,
        volume_history: list[float] = None,
        order_book: dict = None,
    ) -> Signal | None:
        """Evaluate a single market for trading signals.

        Runs base strategies + game theory scoring.
        Final signal score = base edge + game theory boost.
        """
        if category not in config.ALLOWED_CATEGORIES:
            return None

        best_signal = None
        strategy_name = ""

        # Strategy 1: Category-aware inefficiency detection
        inefficiency = self.detector.detect(
            market_price, volume_ratio, price_history, spread, category
        )
        if inefficiency["actionable"] and inefficiency["abs_edge"] >= config.MIN_EDGE:
            best_signal = inefficiency
            strategy_name = "inefficiency"

        # Strategy 2: Cross-market arbitrage
        if external_price is not None:
            arb = self.arb_detector.detect(market_price, external_price, "metaculus/kalshi")
            if arb["actionable"] and arb["abs_edge"] >= config.MIN_EDGE:
                if best_signal is None or arb["abs_edge"] > best_signal["abs_edge"]:
                    best_signal = arb
                    strategy_name = "cross_market_arb"

        if best_signal is None:
            return None

        # Game theory scoring
        gt_result = self.gt_engine.evaluate(
            market_price=market_price,
            fair_value=best_signal["fair_value"],
            volume_ratio=volume_ratio,
            spread=spread,
            price_history=price_history,
            volume_history=volume_history,
            order_book=order_book,
        )

        # Combined score: base edge + aligned GT boost
        base_score = best_signal["abs_edge"]
        base_direction_sign = 1.0 if best_signal["direction"] == "BUY_YES" else -1.0
        gt_alignment = gt_result.total_score * base_direction_sign

        # If GT strongly disagrees, skip
        if gt_alignment < -0.3:
            return None

        combined_score = base_score + max(gt_alignment, 0) * 0.1

        # Size the position with Kelly
        sizing = self.kelly.position_size(
            self.capital,
            market_price,
            best_signal["fair_value"],
            best_signal["direction"],
        )

        if sizing["position_size"] <= 0 or sizing["ev_after_fees"] <= 0:
            return None

        # Confidence based on combined score
        if combined_score > 0.14:
            confidence = "HIGH"
        elif combined_score > 0.09:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return Signal(
            market_id=market_id,
            market_name=market_name,
            category=category,
            strategy=strategy_name,
            direction=best_signal["direction"],
            market_price=market_price,
            fair_value=best_signal["fair_value"],
            edge=best_signal["edge"],
            position_size=sizing["position_size"],
            kelly_fraction=sizing["kelly_fraction"],
            ev_after_fees=sizing["ev_after_fees"],
            confidence=confidence,
            combined_score=combined_score,
            gt_score=gt_result.total_score,
            gt_nash=gt_result.nash_score,
            gt_beauty=gt_result.beauty_contest_score,
            gt_whale=gt_result.whale_score,
            gt_liquidity=gt_result.liquidity_score,
        )

    def scan_markets(self, markets_data: list[dict]) -> list[Signal]:
        """Scan multiple markets and return sorted signals.

        Sorted by combined_score (base + game theory), highest first.
        """
        signals = []
        for m in markets_data:
            category = m.get("category")
            if category is None:
                category = classify_market(m.get("market_name", ""))
                if category is None:
                    continue

            signal = self.evaluate_market(
                market_id=m["market_id"],
                market_name=m["market_name"],
                market_price=m["market_price"],
                volume_ratio=m.get("volume_ratio", 1.0),
                price_history=m.get("price_history", []),
                spread=m.get("spread", 0.03),
                category=category,
                external_price=m.get("external_price"),
                volume_history=m.get("volume_history"),
                order_book=m.get("order_book"),
            )
            if signal:
                signals.append(signal)

        signals.sort(key=lambda s: s.combined_score, reverse=True)
        return signals
