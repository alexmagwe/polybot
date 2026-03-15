"""Configuration for Polymarket trading signal bot."""

# Polymarket CLOB API
API_BASE_URL = "https://clob.polymarket.com"
GAMMA_API_URL = "https://gamma-api.polymarket.com"

# Cross-platform comparison APIs (read-only, public endpoints)
METACULUS_API_URL = "https://www.metaculus.com/api2"
KALSHI_API_URL = "https://trading-api.kalshi.com/trade-api/v2"

# Fee structure
TAKER_FEE_RATE = 0.02       # 2% taker fee
MAKER_FEE_RATE = 0.0        # 0% maker fee (rebate possible)
GAS_FEE_PER_TRADE = 0.01    # ~$0.01 on Polygon

# Risk settings (moderate risk, $100 capital)
INITIAL_CAPITAL = 100.0
MAX_POSITION_SIZE = 0.10     # Max 10% of capital per trade
MIN_POSITION_SIZE = 1.0      # Minimum $1 per trade
MAX_KELLY_FRACTION = 0.25    # Cap Kelly at 25% (quarter-Kelly for safety)
MIN_EDGE = 0.07              # Minimum 7% edge to consider a trade
MAX_CONCURRENT_POSITIONS = 3
SLIPPAGE_ESTIMATE = 0.005    # 0.5% estimated slippage

# Strategy parameters
INEFFICIENCY_THRESHOLD = 0.05  # 5% mispricing threshold
VOLUME_MIN_THRESHOLD = 1000    # Minimum $1000 daily volume
LOOKBACK_DAYS = 30             # Days of history for backtesting
CROSS_MARKET_ARB_THRESHOLD = 0.10  # 10% divergence between platforms to trigger arb

# --- Market Category Filtering ---
# ONLY trade in these categories. Sports are excluded entirely.
ALLOWED_CATEGORIES = ["politics", "macro", "regulatory"]

# Keywords to identify allowed market categories
POLITICS_KEYWORDS = [
    "election", "president", "senate", "congress", "governor", "vote",
    "democrat", "republican", "gop", "primary", "nominee", "poll",
    "trump", "biden", "electoral", "ballot", "caucus", "swing state",
    "house of representatives", "parliament", "minister", "political",
    "party", "inauguration", "impeach", "legislation", "bill pass",
]

MACRO_REGULATORY_KEYWORDS = [
    "fed", "federal reserve", "interest rate", "inflation", "cpi", "gdp",
    "fomc", "rate cut", "rate hike", "recession", "unemployment",
    "fda", "approval", "drug", "sec", "regulation", "tariff", "trade war",
    "central bank", "ecb", "boe", "treasury", "debt ceiling", "shutdown",
    "sanctions", "policy", "executive order", "supreme court", "ruling",
    "antitrust", "merger", "ipo", "crypto regulation", "ban",
]

# Keywords to EXCLUDE (sports, entertainment, pop culture)
EXCLUDED_KEYWORDS = [
    "nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball",
    "baseball", "hockey", "tennis", "golf", "ufc", "mma", "boxing",
    "championship", "playoff", "super bowl", "world series", "world cup",
    "olympics", "formula 1", "f1", "nascar", "cricket", "rugby",
    "esports", "league of legends", "dota", "csgo",
    "oscar", "grammy", "emmy", "bachelor", "survivor", "reality tv",
    "tiktok", "youtube", "streamer", "influencer",
]

# Backtesting
NUM_SIMULATED_MARKETS = 20
NUM_SIMULATED_DAYS = 60
