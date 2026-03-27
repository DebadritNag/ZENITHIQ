"""
Stock Fetcher
-------------
Fetches OHLCV price history and company fundamentals from Yahoo Finance
via yfinance and returns a clean StockSnapshot dataclass.

Indian stocks (NSE/BSE) require exchange suffixes on Yahoo Finance:
    TCS     → TCS.NS   (NSE)
    RELIANCE→ RELIANCE.NS
The fetcher auto-resolves these by trying common suffixes on failure.
"""

from __future__ import annotations

import logging

import yfinance as yf

from data_pipeline.models import OHLCVBar, StockSnapshot

logger = logging.getLogger(__name__)

# Fundamental fields we care about from yf.Ticker.info
_INFO_FIELDS = {
    "longName":          "company_name",
    "sector":            "sector",
    "industry":          "industry",
    "marketCap":         "market_cap",
    "trailingPE":        "pe_ratio",
    "trailingEps":       "eps",
    "dividendYield":     "dividend_yield",
    "fiftyTwoWeekHigh":  "fifty_two_week_high",
    "fiftyTwoWeekLow":   "fifty_two_week_low",
    "currentPrice":      "latest_close",
}

# Suffixes tried in order when bare ticker returns no data
_EXCHANGE_SUFFIXES = ["", ".NS", ".BO", ".L", ".TO", ".AX"]

# Well-known Indian tickers that always need .NS
_KNOWN_NSE = {
    "TCS", "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "WIPRO",
    "HINDUNILVR", "BAJFINANCE", "SBIN", "KOTAKBANK", "AXISBANK",
    "LT", "ASIANPAINT", "MARUTI", "TITAN", "NESTLEIND", "ULTRACEMCO",
    "SUNPHARMA", "TECHM", "HCLTECH", "POWERGRID", "NTPC", "ONGC",
    "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
}


def _resolve_ticker(symbol: str, period: str) -> tuple[str, object, object]:
    """
    Try the symbol with different exchange suffixes until yfinance
    returns non-empty OHLCV data.

    Args:
        symbol: Raw ticker symbol (already uppercased, no suffix).
        period: yfinance period string.

    Returns:
        Tuple of (resolved_ticker, hist_DataFrame, yf.Ticker instance).

    Raises:
        ValueError: If no suffix produces data.
    """
    # Fast path: known NSE tickers
    base = symbol.split(".")[0]
    if base in _KNOWN_NSE and "." not in symbol:
        suffixes = [".NS", ".BO", ""]
    else:
        suffixes = _EXCHANGE_SUFFIXES

    for suffix in suffixes:
        candidate = base + suffix if suffix else base
        try:
            t = yf.Ticker(candidate)
            hist = t.history(period=period, auto_adjust=True)
            if not hist.empty:
                logger.info(f"Resolved '{symbol}' → '{candidate}'")
                return candidate, hist.dropna(), t
        except Exception:
            continue

    raise ValueError(
        f"No price data found for '{symbol}'. "
        f"Tried: {[base + s for s in suffixes]}. "
        f"For Indian stocks use TCS.NS, RELIANCE.NS etc."
    )


def fetch_stock_snapshot(ticker: str, period: str = "6mo") -> StockSnapshot:
    """
    Fetch OHLCV history and key fundamentals for a ticker.

    Automatically appends exchange suffixes (.NS, .BO, etc.) when the
    bare ticker returns no data — handles Indian NSE/BSE stocks transparently.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL', 'TCS', 'TCS.NS').
        period: yfinance period string — '1mo', '3mo', '6mo', '1y', '2y'.

    Returns:
        StockSnapshot with bars and fundamental fields populated.

    Raises:
        ValueError: If no exchange suffix produces data.
    """
    ticker = ticker.upper().strip()
    resolved, hist, yf_ticker = _resolve_ticker(ticker, period)

    # --- Fundamentals ---
    info   = _safe_info(yf_ticker)
    kwargs = {v: info.get(k) for k, v in _INFO_FIELDS.items()}
    kwargs["ticker"] = resolved
    kwargs.setdefault("company_name", resolved)
    kwargs.setdefault("sector", "")
    kwargs.setdefault("industry", "")

    # --- OHLCV bars ---
    bars = [
        OHLCVBar(
            date=str(idx.date()),
            open=round(float(row["Open"]), 4),
            high=round(float(row["High"]), 4),
            low=round(float(row["Low"]), 4),
            close=round(float(row["Close"]), 4),
            volume=float(row["Volume"]),
        )
        for idx, row in hist.iterrows()
    ]

    if kwargs.get("latest_close") is None and bars:
        kwargs["latest_close"] = bars[-1].close

    return StockSnapshot(bars=bars, **kwargs)


def fetch_stock_info(ticker: str) -> dict:
    """Return raw fundamentals dict from yfinance (legacy helper)."""
    return _safe_info(yf.Ticker(ticker.upper()))


def _safe_info(yf_ticker: yf.Ticker) -> dict:
    try:
        return yf_ticker.info or {}
    except Exception as exc:
        logger.warning(f"Could not fetch ticker info: {exc}")
        return {}
