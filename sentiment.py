"""
sentiment.py — News sentiment analysis
========================================
Pulls latest news headlines for each ticker and scores
them as bullish, bearish or neutral using AI.

Usage:
    python3 sentiment.py
    from sentiment import get_sentiment, score_all_tickers

Install:
    pip install requests
"""

import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

NEWS_API_KEY = "c4dc1a637e464acfbc67d33bbe03ac5d"
NEWS_URL     = "https://newsapi.org/v2/everything"


# ── Keyword scoring ───────────────────────────────────────────────────────────

BULLISH_WORDS = [
    "beat", "beats", "record", "growth", "profit", "surge", "soars",
    "upgraded", "outperform", "buy", "strong", "bullish", "rally",
    "breakthrough", "partnership", "deal", "acquisition", "dividend",
    "raised", "raises", "exceeds", "positive", "optimistic", "boom",
    "launch", "expands", "wins", "awarded", "innovation", "milestone",
]

BEARISH_WORDS = [
    "miss", "misses", "loss", "losses", "decline", "falls", "drops",
    "downgraded", "underperform", "sell", "weak", "bearish", "crash",
    "lawsuit", "investigation", "fraud", "recall", "layoffs", "cuts",
    "lowered", "lowers", "below", "negative", "pessimistic", "bust",
    "warning", "risk", "debt", "bankrupt", "scandal", "fine", "penalty",
]


def score_headline(headline: str) -> float:
    """
    Score a single headline from -1.0 (very bearish) to +1.0 (very bullish).
    Uses keyword matching — simple but effective for financial news.
    """
    headline_lower = headline.lower()

    bullish_hits = sum(1 for word in BULLISH_WORDS if word in headline_lower)
    bearish_hits = sum(1 for word in BEARISH_WORDS if word in headline_lower)

    total = bullish_hits + bearish_hits
    if total == 0:
        return 0.0

    score = (bullish_hits - bearish_hits) / total
    return round(score, 3)


def label(score: float) -> str:
    """Convert a numeric score to a label."""
    if score >= 0.2:
        return "BULLISH"
    elif score <= -0.2:
        return "BEARISH"
    return "NEUTRAL"


# ── News fetcher ──────────────────────────────────────────────────────────────

def fetch_headlines(ticker: str, company_name: str = None, days: int = 3) -> list:
    """
    Fetch recent news headlines for a ticker.
    Returns a list of headline strings.
    """
    query = company_name if company_name else ticker
    from_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    params = {
        "q":        query,
        "from":     from_date,
        "sortBy":   "relevancy",
        "language": "en",
        "pageSize": 10,
        "apiKey":   NEWS_API_KEY,
    }

    try:
        response = requests.get(NEWS_URL, params=params, timeout=10)
        data     = response.json()

        if data.get("status") != "ok":
            log.warning("News API error for %s: %s", ticker, data.get("message"))
            return []

        headlines = [
            article["title"]
            for article in data.get("articles", [])
            if article.get("title")
        ]
        return headlines

    except Exception as e:
        log.warning("Failed to fetch news for %s: %s", ticker, e)
        return []


# ── Ticker name map ───────────────────────────────────────────────────────────

COMPANY_NAMES = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "GOOGL": "Google Alphabet",
    "NVDA":  "Nvidia",
    "AMZN":  "Amazon",
    "META":  "Meta Facebook",
    "TSLA":  "Tesla",
    "JPM":   "JPMorgan",
    "V":     "Visa",
    "XOM":   "ExxonMobil",
    "JNJ":   "Johnson Johnson",
    "WMT":   "Walmart",
    "PG":    "Procter Gamble",
    "HD":    "Home Depot",
    "CVX":   "Chevron",
    "MRK":   "Merck",
    "PEP":   "PepsiCo",
    "COST":  "Costco",
    "AVGO":  "Broadcom",
    "ADBE":  "Adobe",
    "CSCO":  "Cisco",
    "MCD":   "McDonald's",
    "NKE":   "Nike",
    "AMD":   "Advanced Micro Devices",
    "QCOM":  "Qualcomm",
    "ORCL":  "Oracle",
    "GS":    "Goldman Sachs",
    "CAT":   "Caterpillar",
    "CRM":   "Salesforce",
    "SPY":   "S&P 500",
    "QQQ":   "Nasdaq",
}


# ── Main sentiment function ───────────────────────────────────────────────────

def get_sentiment(ticker: str) -> dict:
    """
    Get sentiment score for a single ticker.

    Returns dict with:
        ticker      — stock symbol
        score       — float from -1.0 to +1.0
        label       — BULLISH / NEUTRAL / BEARISH
        headlines   — list of headlines used
        headline_scores — individual score per headline
    """
    company = COMPANY_NAMES.get(ticker.upper(), ticker)
    headlines = fetch_headlines(ticker, company)

    if not headlines:
        return {
            "ticker":           ticker.upper(),
            "score":            0.0,
            "label":            "NEUTRAL",
            "headlines":        [],
            "headline_scores":  [],
            "reason":           "No news found",
        }

    scores = [score_headline(h) for h in headlines]
    avg    = round(sum(scores) / len(scores), 3)

    return {
        "ticker":          ticker.upper(),
        "score":           avg,
        "label":           label(avg),
        "headlines":       headlines,
        "headline_scores": list(zip(headlines, scores)),
        "reason":          f"{len(headlines)} headlines analysed",
    }


def score_all_tickers(tickers: list) -> dict:
    """
    Get sentiment for a list of tickers.
    Returns dict keyed by ticker.
    """
    results = {}
    for ticker in tickers:
        results[ticker] = get_sentiment(ticker)
        log.info(
            "%-6s sentiment: %-8s (%.2f)",
            ticker,
            results[ticker]["label"],
            results[ticker]["score"],
        )
    return results


def combined_signal(technical: str, sentiment: dict) -> str:
    """
    Combine technical signal with sentiment to produce a final signal.

    Rules:
    - BUY  + BULLISH  = STRONG BUY
    - BUY  + NEUTRAL  = BUY
    - BUY  + BEARISH  = HOLD (news contradicts signal — be cautious)
    - HOLD + BULLISH  = WATCH (good news, wait for technical confirmation)
    - SELL + BEARISH  = STRONG SELL
    - SELL + NEUTRAL  = SELL
    - SELL + BULLISH  = HOLD (news contradicts signal — be cautious)
    """
    sent = sentiment["label"]

    if technical == "BUY":
        if sent == "BULLISH":  return "STRONG BUY"
        if sent == "NEUTRAL":  return "BUY"
        if sent == "BEARISH":  return "HOLD"

    if technical == "SELL":
        if sent == "BEARISH":  return "STRONG SELL"
        if sent == "NEUTRAL":  return "SELL"
        if sent == "BULLISH":  return "HOLD"

    if technical == "HOLD":
        if sent == "BULLISH":  return "WATCH"
        return "HOLD"

    return "HOLD"


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "MRK", "GS"]

    print("\n" + "="*60)
    print("  SENTIMENT ANALYSIS")
    print("="*60)

    for ticker in tickers:
        result = get_sentiment(ticker)
        print(f"\n  {ticker} — {result['label']} (score: {result['score']})")
        print(f"  {result['reason']}")
        for headline, score in result["headline_scores"][:3]:
            bar = "🟢" if score > 0 else "🔴" if score < 0 else "⚪"
            print(f"  {bar} {headline[:80]}")

    print(f"\n{'='*60}\n")