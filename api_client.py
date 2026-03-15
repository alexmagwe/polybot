"""Polymarket CLOB API client with category filtering and cross-platform comparison."""

import requests
from typing import Optional
import config


def classify_market(title: str, description: str = "") -> Optional[str]:
    """Classify a market into an allowed category or None if excluded.

    Returns 'politics', 'macro', or None.
    """
    text = (title + " " + description).lower()

    # First check exclusions — reject sports/entertainment
    for kw in config.EXCLUDED_KEYWORDS:
        if kw in text:
            return None

    # Check politics
    for kw in config.POLITICS_KEYWORDS:
        if kw in text:
            return "politics"

    # Check macro/regulatory
    for kw in config.MACRO_REGULATORY_KEYWORDS:
        if kw in text:
            return "macro"

    return None


class PolymarketClient:
    """Client for Polymarket CLOB and Gamma APIs with category filtering."""

    def __init__(self):
        self.clob_base = config.API_BASE_URL
        self.gamma_base = config.GAMMA_API_URL
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_markets(self, limit: int = 100, active: bool = True) -> list[dict]:
        """Fetch available markets from Gamma API, filtered to allowed categories."""
        params = {"limit": limit, "active": str(active).lower(), "closed": "false"}
        try:
            resp = self.session.get(f"{self.gamma_base}/markets", params=params, timeout=10)
            resp.raise_for_status()
            all_markets = resp.json()
        except requests.RequestException as e:
            print(f"[API] Error fetching markets: {e}")
            return []

        # Filter to allowed categories only
        filtered = []
        for m in all_markets:
            title = m.get("question", m.get("title", ""))
            desc = m.get("description", "")
            category = classify_market(title, desc)
            if category is not None:
                m["_category"] = category
                filtered.append(m)

        return filtered

    def get_market(self, condition_id: str) -> Optional[dict]:
        """Fetch a single market by condition ID, returns None if excluded category."""
        try:
            resp = self.session.get(f"{self.gamma_base}/markets/{condition_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            title = data.get("question", data.get("title", ""))
            desc = data.get("description", "")
            category = classify_market(title, desc)
            if category is None:
                return None
            data["_category"] = category
            return data
        except requests.RequestException as e:
            print(f"[API] Error fetching market {condition_id}: {e}")
            return None

    def get_order_book(self, token_id: str) -> Optional[dict]:
        """Fetch order book for a token (YES or NO outcome)."""
        try:
            resp = self.session.get(
                f"{self.clob_base}/book",
                params={"token_id": token_id},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[API] Error fetching order book: {e}")
            return None

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get the midpoint price for a token."""
        try:
            resp = self.session.get(
                f"{self.clob_base}/midpoint",
                params={"token_id": token_id},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("mid", 0))
        except (requests.RequestException, ValueError) as e:
            print(f"[API] Error fetching midpoint: {e}")
            return None


class CrossPlatformClient:
    """Fetches odds from Metaculus and Kalshi for cross-market arbitrage comparison."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_metaculus_prediction(self, question_id: int) -> Optional[float]:
        """Fetch community prediction from Metaculus for a question."""
        try:
            resp = self.session.get(
                f"{config.METACULUS_API_URL}/questions/{question_id}/",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            prediction = data.get("community_prediction", {})
            if isinstance(prediction, dict):
                return prediction.get("full", {}).get("q2")
            return None
        except (requests.RequestException, ValueError) as e:
            print(f"[Metaculus] Error fetching question {question_id}: {e}")
            return None

    def get_kalshi_market(self, ticker: str) -> Optional[dict]:
        """Fetch market data from Kalshi by ticker."""
        try:
            resp = self.session.get(
                f"{config.KALSHI_API_URL}/markets/{ticker}",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            market = data.get("market", {})
            yes_price = market.get("yes_ask")
            no_price = market.get("no_ask")
            if yes_price is not None:
                return {
                    "ticker": ticker,
                    "yes_price": yes_price / 100.0,  # Kalshi uses cents
                    "no_price": no_price / 100.0 if no_price else None,
                    "title": market.get("title", ""),
                }
            return None
        except (requests.RequestException, ValueError) as e:
            print(f"[Kalshi] Error fetching market {ticker}: {e}")
            return None

    def find_cross_market_arb(
        self,
        polymarket_price: float,
        external_price: float,
        source: str = "external",
    ) -> Optional[dict]:
        """Compare Polymarket implied probability vs external platform.

        Returns arbitrage signal if divergence exceeds threshold.
        """
        divergence = external_price - polymarket_price
        abs_div = abs(divergence)

        if abs_div < config.CROSS_MARKET_ARB_THRESHOLD:
            return None

        direction = "BUY_YES" if divergence > 0 else "BUY_NO"

        return {
            "polymarket_price": polymarket_price,
            "external_price": external_price,
            "source": source,
            "divergence": divergence,
            "abs_divergence": abs_div,
            "direction": direction,
        }
