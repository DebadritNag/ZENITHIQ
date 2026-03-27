"""
News Scraper
------------
Scrapes financial news from multiple sources without requiring an API key.

Sources (tried in order, results merged):
    1. Yahoo Finance news RSS feed  — reliable, no auth
    2. Finviz news table            — fast HTML scrape
    3. MarketWatch search           — fallback

Returns a clean NewsBundle dataclass ready for agents.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from data_pipeline.models import NewsArticle, NewsBundle

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 12


def scrape_news(ticker: str, max_articles: int = 20) -> NewsBundle:
    """
    Scrape recent financial news for a ticker from multiple sources.

    Args:
        ticker:       Stock ticker symbol (e.g. 'AAPL').
        max_articles: Maximum total articles to return across all sources.

    Returns:
        NewsBundle with deduplicated NewsArticle objects.
    """
    ticker = ticker.upper().strip()
    articles: list[NewsArticle] = []

    for scraper in (_scrape_yahoo_rss, _scrape_finviz, _scrape_marketwatch):
        try:
            batch = scraper(ticker)
            articles.extend(batch)
            logger.debug(f"[{scraper.__name__}] fetched {len(batch)} articles for {ticker}")
        except Exception as exc:
            logger.warning(f"[{scraper.__name__}] failed for {ticker}: {exc}")

        if len(articles) >= max_articles:
            break

    deduped = _deduplicate(articles)[:max_articles]
    return NewsBundle(ticker=ticker, query=ticker, articles=deduped)


def scrape_article_text(url: str) -> str:
    """
    Fetch and extract the body text of a single article URL.

    Strips navigation, ads, and boilerplate — returns only paragraph text.

    Args:
        url: Full article URL.

    Returns:
        Cleaned body text string, or empty string on failure.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "form", "iframe", "noscript"]):
            tag.decompose()

        paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 40)
        return re.sub(r"\s+", " ", text).strip()
    except Exception as exc:
        logger.warning(f"Could not scrape article text from {url}: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Source-specific scrapers
# ---------------------------------------------------------------------------

def _scrape_yahoo_rss(ticker: str) -> list[NewsArticle]:
    """
    Parse Yahoo Finance's public RSS feed for a ticker.

    Args:
        ticker: Ticker symbol.

    Returns:
        List of NewsArticle objects.
    """
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "xml")
    articles = []

    for item in soup.find_all("item"):
        title     = _text(item, "title")
        link      = _text(item, "link")
        pub_date  = _text(item, "pubDate")
        summary   = _clean_html(_text(item, "description"))

        if not title or not link:
            continue

        articles.append(NewsArticle(
            title     = title,
            url       = link,
            source    = "Yahoo Finance",
            published = pub_date,
            summary   = summary[:300],
        ))

    return articles


def _scrape_finviz(ticker: str) -> list[NewsArticle]:
    """
    Scrape the news table from Finviz's ticker page.

    Args:
        ticker: Ticker symbol.

    Returns:
        List of NewsArticle objects.
    """
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    news_table = soup.find("table", id="news-table")
    if not news_table:
        return []

    articles = []
    last_date = ""

    for row in news_table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        date_cell = cells[0].get_text(strip=True)
        link_tag  = cells[1].find("a")
        if not link_tag:
            continue

        # Finviz date cell alternates between "MMM-DD-YY" and "HH:MM AM/PM"
        if re.match(r"[A-Z][a-z]+-\d{2}-\d{2}", date_cell):
            last_date = date_cell
        published = f"{last_date} {date_cell}" if last_date else date_cell

        articles.append(NewsArticle(
            title     = link_tag.get_text(strip=True),
            url       = link_tag.get("href", ""),
            source    = "Finviz",
            published = published,
        ))

    return articles


def _scrape_marketwatch(ticker: str) -> list[NewsArticle]:
    """
    Scrape MarketWatch search results for a ticker.

    Args:
        ticker: Ticker symbol.

    Returns:
        List of NewsArticle objects.
    """
    url = f"https://www.marketwatch.com/investing/stock/{ticker.lower()}"
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    for item in soup.select("div.article__content"):
        link_tag = item.find("a", class_="link")
        if not link_tag:
            continue

        title    = link_tag.get_text(strip=True)
        href     = link_tag.get("href", "")
        time_tag = item.find("span", class_="article__timestamp")
        pub      = time_tag.get_text(strip=True) if time_tag else ""
        desc_tag = item.find("p", class_="article__summary")
        summary  = desc_tag.get_text(strip=True) if desc_tag else ""

        if title and href:
            articles.append(NewsArticle(
                title     = title,
                url       = href if href.startswith("http") else f"https://www.marketwatch.com{href}",
                source    = "MarketWatch",
                published = pub,
                summary   = summary[:300],
            ))

    return articles


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _text(tag, name: str) -> str:
    """Extract text from a BeautifulSoup child tag safely."""
    child = tag.find(name)
    return child.get_text(strip=True) if child else ""


def _clean_html(raw: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", raw).strip()


def _deduplicate(articles: list[NewsArticle]) -> list[NewsArticle]:
    """
    Remove duplicate articles by normalised title.

    Args:
        articles: Raw merged article list.

    Returns:
        Deduplicated list preserving original order.
    """
    seen: set[str] = set()
    unique = []
    for a in articles:
        key = re.sub(r"\W+", "", a.title.lower())[:60]
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
    return unique
