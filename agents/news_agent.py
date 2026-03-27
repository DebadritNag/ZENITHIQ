"""
News Agent
----------
Fetches recent financial news for a ticker via NewsAPI.
Scores headlines with a rule-based engine — no Gemini required.
Falls back to the data_pipeline scraper when NewsAPI is unavailable.
"""

import re
import requests
from datetime import datetime, timedelta
from typing import Any

from agents.base_agent import BaseAgent, AgentResult
from data_pipeline import scrape_news, NewsBundle
from config import settings

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Keyword lists for rule-based sentiment scoring
_BULLISH_KW = [
    "beat", "surge", "rally", "upgrade", "buy", "strong", "growth",
    "profit", "record", "outperform", "positive", "gain", "deal",
    "expansion", "dividend", "buyback", "exceed", "raise guidance",
    "momentum", "breakout", "partnership", "win", "award",
]
_BEARISH_KW = [
    "miss", "fall", "drop", "downgrade", "sell", "weak", "loss",
    "decline", "warning", "risk", "concern", "cut", "reduce",
    "investigation", "probe", "lawsuit", "fraud", "debt", "layoff",
    "restructur", "impairment", "write-off", "guidance cut",
    "margin pressure", "headwind", "disappointing", "default",
]


class NewsAgent(BaseAgent):
    """
    Fetches and scores financial news headlines for a ticker.

    Data source priority:
        1. NewsAPI  (when NEWS_API_KEY is set in .env)
        2. Pipeline scraper  (Yahoo RSS + Finviz + MarketWatch)

    Scoring: rule-based keyword analysis — no external AI calls.
    """

    def __init__(self):
        super().__init__("NewsAgent")

    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Fetch and score recent news for `ticker`.

        Args:
            ticker:       Stock ticker symbol.
            days:         Lookback window in days (default 7).
            max_articles: Max articles to process (default 20).

        Returns:
            AgentResult with headlines, rule-based analysis, and 0–1 score.
        """
        days         = kwargs.get("days", 7)
        max_articles = kwargs.get("max_articles", 20)

        try:
            headlines, article_count = self._fetch_headlines(ticker, days, max_articles)

            if not headlines:
                return AgentResult(
                    self.name,
                    {"message": "No news found", "article_count": 0},
                    score=0.5,
                )

            score, analysis = self._score_headlines(ticker, headlines)

            return AgentResult(
                self.name,
                {
                    "article_count": article_count,
                    "headlines":     headlines[:5],
                    "analysis":      analysis,
                },
                score=score,
            )

        except Exception as exc:
            self.logger.error(f"NewsAgent failed for {ticker}: {exc}")
            return AgentResult(self.name, {}, score=0.5, error=str(exc))

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def _fetch_headlines(
        self, ticker: str, days: int, max_articles: int
    ) -> tuple[list[str], int]:
        """
        Fetch headlines from NewsAPI or the pipeline scraper.

        Returns:
            Tuple of (headlines list, total article count).
        """
        if settings.news_api_key:
            try:
                articles = self._fetch_newsapi(ticker, days, max_articles)
                if articles:
                    headlines = [a["title"] for a in articles if a.get("title")]
                    return headlines, len(articles)
                self.logger.info(f"NewsAPI returned 0 articles for {ticker}, trying scraper")
            except Exception as exc:
                self.logger.warning(f"NewsAPI failed for {ticker}: {exc}, falling back to scraper")

        # Fallback: pipeline scraper (no API key needed)
        bundle: NewsBundle = scrape_news(ticker, max_articles=max_articles)
        return bundle.headlines, len(bundle.articles)

    def _fetch_newsapi(self, ticker: str, days: int, max_articles: int) -> list[dict]:
        """
        Fetch articles from NewsAPI.

        Uses the company name as query when ticker looks like an Indian symbol
        (e.g. TCS.NS → TCS) for better results.
        """
        query    = ticker.split(".")[0]   # strip .NS / .BO suffix
        from_dt  = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        params   = {
            "q":        query,
            "from":     from_dt,
            "sortBy":   "relevancy",
            "language": "en",
            "pageSize": max_articles,
            "apiKey":   settings.news_api_key,
        }
        resp = requests.get(NEWSAPI_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # NewsAPI returns status:"error" with 200 on some plan limits
        if data.get("status") == "error":
            raise RuntimeError(data.get("message", "NewsAPI error"))

        return data.get("articles", [])

    # ------------------------------------------------------------------
    # Rule-based scoring (no Gemini)
    # ------------------------------------------------------------------

    def _score_headlines(
        self, ticker: str, headlines: list[str]
    ) -> tuple[float, str]:
        """
        Score headlines using keyword counting.

        Returns:
            Tuple of (score 0–1, human-readable analysis string).
        """
        combined = " ".join(headlines).lower()

        bullish = sum(1 for kw in _BULLISH_KW if kw in combined)
        bearish = sum(1 for kw in _BEARISH_KW if kw in combined)
        total   = bullish + bearish or 1

        # Weighted score: 0 = all bearish, 1 = all bullish
        raw_score = bullish / total
        # Blend toward 0.5 so extreme scores need strong evidence
        score = round(0.5 * 0.3 + raw_score * 0.7, 4)
        score = max(0.0, min(1.0, score))

        if score >= 0.65:
            tone = "bullish"
        elif score <= 0.40:
            tone = "bearish"
        else:
            tone = "neutral"

        # Pick top 3 most relevant headlines for the summary
        top = headlines[:3]
        analysis = (
            f"Overall tone: {tone}. "
            f"Detected {bullish} positive and {bearish} negative signals "
            f"across {len(headlines)} headlines for {ticker.split('.')[0]}.\n"
            f"Key headlines:\n" +
            "\n".join(f"  • {h}" for h in top) +
            f"\nSCORE: {score}"
        )

        return score, analysis
