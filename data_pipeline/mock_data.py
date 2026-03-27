"""
Mock Data Generator
-------------------
Generates realistic mock social media posts for stock sentiment analysis.
Used as a fallback when Reddit scraping is unavailable or rate-limited.

Usage:
    from data_pipeline.mock_data import get_mock_posts

    posts = get_mock_posts("AAPL")   # returns list[str]
    posts = get_mock_posts("RELIANCE.NS")
"""

from __future__ import annotations

import random
import hashlib


# ---------------------------------------------------------------------------
# Tone buckets — each list is weighted during sampling
# ---------------------------------------------------------------------------

_BULLISH = [
    "{sym} is going to the moon 🚀 loaded up at the dip",
    "Been holding {sym} for 6 months, not selling anytime soon. Fundamentals are rock solid.",
    "{sym} breakout incoming. Chart looks beautiful right now 📈",
    "Just doubled my position in {sym}. Management is delivering on every promise.",
    "Analysts keep underestimating {sym}. This thing is a 3x from here easy.",
    "{sym} Q3 numbers were insane. Revenue up 18% and they still beat estimates.",
    "Every dip in {sym} is a gift. Adding more below ₹2800.",
    "Institutions are quietly accumulating {sym}. Retail will FOMO in at the top lol",
    "{sym} has the best moat in the sector. Not touching my shares.",
    "Technical setup on {sym} is perfect — golden cross forming on the weekly.",
    "If you're not in {sym} yet you're going to regret it in 12 months.",
    "{sym} just signed a massive deal. This is the catalyst everyone was waiting for 🔥",
    "Bought {sym} at IPO and still holding. Best decision of my investing life.",
    "{sym} margins expanding every quarter. This is a compounding machine.",
    "Strong buy on {sym}. Price target ₹3500 by year end.",
]

_BEARISH = [
    "Promoters are dumping {sym} shares. Be very careful here 🚨",
    "{sym} valuation makes zero sense at these levels. Pure hype.",
    "Sold all my {sym} today. The growth story is over, move on.",
    "Debt levels at {sym} are concerning. Nobody is talking about this.",
    "{sym} insiders sold ₹40Cr worth of shares last month. That tells you everything.",
    "Avoid {sym} until the next earnings. Guidance was terrible.",
    "{sym} is a value trap. Has been for 2 years. Stop catching falling knives.",
    "Competition is eating {sym}'s lunch. Market share down 3 quarters in a row.",
    "The {sym} rally is purely liquidity driven. No real earnings support.",
    "Short {sym}. Overvalued by at least 40% on any reasonable DCF.",
    "{sym} management keeps missing their own targets. Zero credibility left.",
    "Red flags everywhere in {sym} annual report. Read the footnotes people.",
    "{sym} is the most overhyped stock on NSE right now. Stay away.",
    "Margin compression at {sym} is structural, not temporary. Sell.",
    "FIIs have been net sellers of {sym} for 5 straight weeks. Follow the smart money.",
]

_NEUTRAL = [
    "Looks stable, holding {sym} for the long term. Not adding, not selling.",
    "{sym} is fairly valued here. Neither a screaming buy nor a sell.",
    "Watching {sym} from the sidelines. Will enter if it drops another 8-10%.",
    "Mixed signals on {sym}. RSI is neutral, volume is average. Wait and watch.",
    "Anyone else tracking {sym}? Curious what the consensus is.",
    "{sym} is in a consolidation phase. Could break either way.",
    "Holding a small position in {sym}. Not convinced enough to add more yet.",
    "The {sym} thesis is intact but execution has been slow. Patience required.",
    "Did anyone read the {sym} concall transcript? Management sounded cautious.",
    "{sym} chart is at a key support level. Make or break zone.",
    "Not sure about {sym} right now. Sector headwinds are real but company is solid.",
    "Trimmed 30% of my {sym} position to book some profits. Still holding the rest.",
    "{sym} is a good business but the stock needs to cool off before I add.",
    "Neutral on {sym} short term. Long term story still intact.",
    "Waiting for {sym} to show a clear trend before taking a position.",
]

# ---------------------------------------------------------------------------
# Symbol-specific context injections
# ---------------------------------------------------------------------------

_SYMBOL_CONTEXT: dict[str, dict[str, list[str]]] = {
    "RELIANCE": {
        "bullish": [
            "Reliance Jio subscriber growth is insane. {sym} is a no-brainer.",
            "Retail + Jio + Green Energy = {sym} is a decade-long compounder.",
        ],
        "bearish": [
            "{sym} conglomerate discount is real. Too many businesses, no focus.",
            "Reliance Retail margins are under pressure. {sym} needs a re-rating.",
        ],
    },
    "TCS": {
        "bullish": [
            "{sym} deal wins this quarter were massive. AI services pipeline is huge.",
            "TCS dividend yield + buyback = {sym} is the safest large cap bet.",
        ],
        "bearish": [
            "IT sector slowdown is real. {sym} guidance was disappointing.",
            "Attrition at {sym} is still elevated. Margin pressure incoming.",
        ],
    },
    "AAPL": {
        "bullish": [
            "Apple Intelligence is going to drive the biggest iPhone upgrade cycle ever. {sym} 🚀",
            "{sym} services revenue is a money printer. 40% margins on pure software.",
        ],
        "bearish": [
            "China risk for {sym} is massively underpriced by the market.",
            "{sym} hardware growth is stalling. Services can't carry the whole valuation.",
        ],
    },
    "TSLA": {
        "bullish": [
            "FSD v13 is a game changer. {sym} is not just a car company.",
            "Robotaxi launch will re-rate {sym} completely. Massive optionality.",
        ],
        "bearish": [
            "{sym} margins are collapsing due to price cuts. This is not sustainable.",
            "Competition from BYD is destroying {sym} market share in China.",
        ],
    },
    "MSFT": {
        "bullish": [
            "Azure + Copilot = {sym} is the best AI infrastructure play out there.",
            "{sym} enterprise moat is unbreakable. Every company runs on Microsoft.",
        ],
        "bearish": [
            "{sym} valuation is pricing in perfection. Any miss will hurt badly.",
            "OpenAI dependency is a risk for {sym}. What if the partnership breaks?",
        ],
    },
    "INFY": {
        "bullish": [
            "{sym} large deal wins are accelerating. Cobalt platform is gaining traction.",
            "Infosys digital revenue mix is improving. {sym} deserves a premium.",
        ],
        "bearish": [
            "{sym} keeps cutting guidance. Management credibility is at an all-time low.",
            "US banking sector slowdown will hit {sym} hard. 30% revenue exposure.",
        ],
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_mock_posts(symbol: str, count: int = 18) -> list[str]:
    """
    Generate a list of realistic mock social media posts for a stock symbol.

    Posts are a mix of bullish, bearish, and neutral retail investor opinions.
    Output is deterministic for the same symbol (seeded by symbol hash) but
    varied enough to feel organic.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'RELIANCE.NS', 'TCS').
                Case-insensitive. '.NS' / '.BO' suffixes are stripped.
        count:  Number of posts to return (default 18, clamped to 15–25).

    Returns:
        List of post strings with the symbol name interpolated.
    """
    count = max(15, min(25, count))

    # Normalise symbol — strip exchange suffix, uppercase
    clean = symbol.upper().split(".")[0]

    # Seed random with a hash of the symbol so output is stable per symbol
    seed = int(hashlib.md5(clean.encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # Build the full pool: generic + symbol-specific
    bullish_pool = _BULLISH.copy()
    bearish_pool = _BEARISH.copy()
    neutral_pool = _NEUTRAL.copy()

    ctx = _SYMBOL_CONTEXT.get(clean, {})
    bullish_pool.extend(ctx.get("bullish", []))
    bearish_pool.extend(ctx.get("bearish", []))

    # Weighted distribution: ~40% bullish, ~35% bearish, ~25% neutral
    weights = (
        [("bullish", bullish_pool)] * 40 +
        [("bearish", bearish_pool)] * 35 +
        [("neutral", neutral_pool)] * 25
    )

    selected: list[str] = []
    used: set[str] = set()

    attempts = 0
    while len(selected) < count and attempts < count * 5:
        attempts += 1
        _, pool = rng.choice(weights)
        template = rng.choice(pool)
        if template in used:
            continue
        used.add(template)
        post = template.format(sym=clean)
        selected.append(post)

    # Shuffle so tones aren't grouped together
    rng.shuffle(selected)
    return selected


# ---------------------------------------------------------------------------
# Insider activity simulation
# ---------------------------------------------------------------------------

# Per-symbol bias: positive = net buying tendency, negative = net selling
_INSIDER_BIAS: dict[str, float] = {
    "RELIANCE": 0.3,
    "TCS":      0.4,
    "INFY":    -0.2,
    "AAPL":     0.1,
    "TSLA":    -0.4,
    "MSFT":     0.5,
    "NVDA":     0.2,
    "HDFCBANK": 0.3,
    "WIPRO":   -0.1,
}


def get_mock_insider_activity(symbol: str) -> dict:
    """
    Simulate insider trading activity for a stock symbol.

    The intensity is deterministic per symbol (seeded by hash) so the
    same symbol always returns the same result within a session, but
    a small random jitter keeps it from feeling static across calls.

    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'RELIANCE.NS').
                Case-insensitive. '.NS' / '.BO' suffixes are stripped.

    Returns:
        Dict with:
            activity  (str):   'buy' or 'sell'
            intensity (float): -1.0 (heavy selling) to +1.0 (heavy buying)
                               Positive = net buying, negative = net selling.
    """
    clean = symbol.upper().split(".")[0]

    # Deterministic seed per symbol
    seed = int(hashlib.md5(f"insider_{clean}".encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)

    # Base bias from known symbols, default slight sell pressure for unknowns
    base = _INSIDER_BIAS.get(clean, rng.uniform(-0.3, 0.3))

    # Add small jitter so it doesn't feel hardcoded
    jitter = rng.uniform(-0.15, 0.15)
    intensity = round(max(-1.0, min(1.0, base + jitter)), 4)

    activity = "buy" if intensity >= 0 else "sell"

    return {
        "activity":  activity,
        "intensity": intensity,
    }
