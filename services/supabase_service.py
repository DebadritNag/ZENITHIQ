"""
Supabase Service
----------------
Two clients:
  - _anon_client   — anon key, used for reads (safe to expose)
  - _write_client  — service role key, used for all writes

Tables
------
  filing_chunks        vector store for SEC filing text chunks
  analysis_results     persisted coordinator AnalysisReport outputs
  insider_transactions cached insider trade rows from OpenInsider
  news_cache           deduplicated scraped news articles
  sentiment_cache      FinBERT sentiment results per ticker
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client singletons
# ---------------------------------------------------------------------------

_anon_client:  Client | None = None
_write_client: Client | None = None


def get_anon_client() -> Client:
    """Return singleton anon (read) client."""
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.supabase_url, settings.supabase_key)
    return _anon_client


def get_write_client() -> Client:
    """
    Return singleton service-role (write) client.
    Falls back to anon client if service key is not configured.
    """
    global _write_client
    if _write_client is None:
        key = settings.supabase_service_key or settings.supabase_key
        _write_client = create_client(settings.supabase_url, key)
    return _write_client


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def insert_record(table: str, data: dict) -> dict:
    """Insert a single record into `table` using the write client."""
    return get_write_client().table(table).insert(data).execute().data


def fetch_records(table: str, filters: dict | None = None) -> list:
    """Fetch records from `table` with optional equality filters."""
    query = get_anon_client().table(table).select("*")
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    return query.execute().data


# ---------------------------------------------------------------------------
# Analysis results — persist every coordinator run
# ---------------------------------------------------------------------------

def save_analysis_result(report: dict) -> dict | None:
    """
    Persist a coordinator AnalysisReport dict to analysis_results.

    Args:
        report: Output of AnalysisReport.to_dict().

    Returns:
        Inserted row data, or None on failure.
    """
    try:
        row = {
            "ticker":        report["ticker"],
            "company_name":  report.get("company_name", ""),
            "alpha_score":   report["alpha_score"],
            "signal":        report["signal"],
            "summary":       report.get("summary", ""),
            "key_risks":     report.get("key_risks", []),
            "agent_results": report.get("agent_results", {}),
            "weights_used":  report.get("weights_used", {}),
            "agents_failed": report.get("agents_failed", []),
            "duration_ms":   report.get("duration_ms", 0),
        }
        result = get_write_client().table("analysis_results").insert(row).execute()
        logger.info(f"Saved analysis result for {report['ticker']}")
        return result.data
    except Exception as exc:
        logger.error(f"Failed to save analysis result: {exc}")
        return None


def get_analysis_history(ticker: str, limit: int = 10) -> list[dict]:
    """
    Fetch the most recent analysis results for a ticker.

    Args:
        ticker: Ticker symbol.
        limit:  Max rows to return.

    Returns:
        List of analysis_results rows ordered by created_at desc.
    """
    try:
        result = (
            get_anon_client()
            .table("analysis_results")
            .select("id, ticker, company_name, alpha_score, signal, summary, key_risks, created_at")
            .eq("ticker", ticker.upper())
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error(f"Failed to fetch analysis history for {ticker}: {exc}")
        return []


def get_latest_analysis(ticker: str) -> dict | None:
    """
    Return the single most recent analysis result for a ticker.

    Args:
        ticker: Ticker symbol.

    Returns:
        Full analysis_results row dict, or None if not found.
    """
    rows = get_analysis_history(ticker, limit=1)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Insider transactions cache
# ---------------------------------------------------------------------------

def save_insider_transactions(ticker: str, transactions: list[dict]) -> None:
    """
    Persist insider transaction rows for a ticker.

    Skips rows that would violate uniqueness on (ticker, filing_date, insider_name, trade_type).

    Args:
        ticker:       Ticker symbol.
        transactions: List of transaction dicts from InsiderAgent.
    """
    if not transactions:
        return
    try:
        rows = [
            {
                "ticker":       ticker.upper(),
                "filing_date":  t.get("filing_date", ""),
                "trade_date":   t.get("trade_date", ""),
                "insider_name": t.get("insider_name", ""),
                "title":        t.get("title", ""),
                "trade_type":   t.get("trade_type", ""),
                "price":        t.get("price", ""),
                "qty":          t.get("qty", ""),
                "owned":        t.get("owned", ""),
                "value":        t.get("value", ""),
            }
            for t in transactions
        ]
        get_write_client().table("insider_transactions").upsert(
            rows, on_conflict="ticker,filing_date,insider_name,trade_type"
        ).execute()
        logger.info(f"Saved {len(rows)} insider transactions for {ticker}")
    except Exception as exc:
        logger.error(f"Failed to save insider transactions for {ticker}: {exc}")


def get_insider_transactions(ticker: str, limit: int = 40) -> list[dict]:
    """
    Fetch cached insider transactions for a ticker.

    Args:
        ticker: Ticker symbol.
        limit:  Max rows to return.

    Returns:
        List of insider_transactions rows ordered by trade_date desc.
    """
    try:
        result = (
            get_anon_client()
            .table("insider_transactions")
            .select("*")
            .eq("ticker", ticker.upper())
            .order("trade_date", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error(f"Failed to fetch insider transactions for {ticker}: {exc}")
        return []


# ---------------------------------------------------------------------------
# News cache
# ---------------------------------------------------------------------------

def save_news_articles(ticker: str, articles: list[dict]) -> None:
    """
    Upsert news articles into the news_cache table.

    Deduplicates on URL so re-scraping the same articles is safe.

    Args:
        ticker:   Ticker symbol.
        articles: List of article dicts (title, url, source, published, summary).
    """
    if not articles:
        return
    try:
        rows = [
            {
                "ticker":    ticker.upper(),
                "title":     a.get("title", ""),
                "url":       a.get("url", ""),
                "source":    a.get("source", ""),
                "published": a.get("published", ""),
                "summary":   a.get("summary", "")[:500],
            }
            for a in articles
            if a.get("url")
        ]
        get_write_client().table("news_cache").upsert(
            rows, on_conflict="url"
        ).execute()
        logger.info(f"Saved {len(rows)} news articles for {ticker}")
    except Exception as exc:
        logger.error(f"Failed to save news articles for {ticker}: {exc}")


def get_cached_news(ticker: str, limit: int = 20) -> list[dict]:
    """
    Fetch cached news articles for a ticker.

    Args:
        ticker: Ticker symbol.
        limit:  Max rows to return.

    Returns:
        List of news_cache rows ordered by scraped_at desc.
    """
    try:
        result = (
            get_anon_client()
            .table("news_cache")
            .select("title, url, source, published, summary, scraped_at")
            .eq("ticker", ticker.upper())
            .order("scraped_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error(f"Failed to fetch news cache for {ticker}: {exc}")
        return []


# ---------------------------------------------------------------------------
# Sentiment cache
# ---------------------------------------------------------------------------

def save_sentiment_result(ticker: str, sentiment_data: dict) -> None:
    """
    Persist a SentimentAgent result to sentiment_cache.

    Args:
        ticker:         Ticker symbol.
        sentiment_data: The `data` dict from SentimentAgent's AgentResult.
    """
    try:
        row = {
            "ticker":          ticker.upper(),
            "sentiment_score": sentiment_data.get("sentiment_score", 0.0),
            "label":           sentiment_data.get("label", "neutral"),
            "post_count":      sentiment_data.get("post_count", 0),
            "sample_scores":   sentiment_data.get("sample_scores", []),
        }
        get_write_client().table("sentiment_cache").insert(row).execute()
        logger.info(f"Saved sentiment result for {ticker}")
    except Exception as exc:
        logger.error(f"Failed to save sentiment result for {ticker}: {exc}")


def get_latest_sentiment(ticker: str) -> dict | None:
    """
    Return the most recent sentiment result for a ticker.

    Args:
        ticker: Ticker symbol.

    Returns:
        sentiment_cache row dict, or None if not found.
    """
    try:
        result = (
            get_anon_client()
            .table("sentiment_cache")
            .select("*")
            .eq("ticker", ticker.upper())
            .order("analysed_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error(f"Failed to fetch sentiment for {ticker}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Filing vector store
# ---------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    """
    Generate a 768-dim embedding using sentence-transformers.

    Lazy-loads the model on first call.

    Args:
        text: Input string to embed.

    Returns:
        List of floats representing the embedding vector.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-mpnet-base-v2")
    return model.encode(text).tolist()


def upsert_filing_chunks(
    ticker: str,
    chunks: list[str],
    form_type: str,
    filing_date: str,
) -> None:
    """
    Embed and insert filing text chunks into the Supabase vector store.

    Args:
        ticker:      Stock ticker symbol.
        chunks:      List of text chunks from the filing.
        form_type:   Filing form type (e.g. '10-K').
        filing_date: Filing date string.
    """
    client = get_write_client()
    rows = [
        {
            "ticker":       ticker.upper(),
            "form_type":    form_type,
            "filing_date":  filing_date,
            "chunk_text":   chunk,
            "embedding":    _embed(chunk),
        }
        for chunk in chunks
    ]
    for i in range(0, len(rows), 50):
        client.table("filing_chunks").insert(rows[i:i + 50]).execute()
    logger.info(f"Upserted {len(rows)} filing chunks for {ticker}")


def search_filing_chunks(ticker: str, query: str, top_k: int = 5) -> list[str]:
    """
    Perform a cosine-similarity vector search over stored filing chunks.

    Calls the `match_filing_chunks` Postgres RPC function.

    Args:
        ticker: Filter results to this ticker.
        query:  Natural language query string.
        top_k:  Number of top results to return.

    Returns:
        List of the most relevant chunk text strings.
    """
    query_embedding = _embed(query)
    response = get_anon_client().rpc(
        "match_filing_chunks",
        {
            "query_embedding": query_embedding,
            "match_ticker":    ticker.upper(),
            "match_count":     top_k,
        },
    ).execute()
    return [row["chunk_text"] for row in (response.data or [])]
