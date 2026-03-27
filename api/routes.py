"""
Zenith IQ API Routes
-----------------------

Route map
---------
POST /api/v1/alpha/analyse          Full pipeline (all 5 agents + summary)
POST /api/v1/alpha/quant            Quant Agent only
POST /api/v1/alpha/insider          Insider Agent only
POST /api/v1/alpha/news             News Agent only
POST /api/v1/alpha/sentiment        Sentiment Agent only
POST /api/v1/analysis/contradict    Gemini contradiction detection
POST /api/v1/analysis/explain       Gemini investor explanation
POST /api/v1/analysis/ask           Free-form Gemini query
GET  /api/v1/stocks/{ticker}        Quick stock snapshot
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    AnalyseRequest,
    AnalyseResponse,
    AgentRunRequest,
    ReasoningRequest,
    ContradictionResponse,
    InvestorExplanationResponse,
    HealthResponse,
    ZenithResponse,
    NarrativeConflict,
    SentimentDivergence,
    QuantInsight,
)
from agents.coordinator import CoordinatorAgent
from agents.quant_agent import QuantAgent
from agents.insider_agent import InsiderAgent
from agents.news_agent import NewsAgent
from agents.sentiment_agent import SentimentAgent
from services.gemini_reasoning import (
    ReasoningInput,
    contradiction_analysis,
    investor_explanation,
)
from services.gemini_service import query_gemini
from services.supabase_service import (
    get_analysis_history,
    get_latest_analysis,
    get_cached_news,
    get_insider_transactions,
    get_latest_sentiment,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

alpha_router    = APIRouter(prefix="/alpha",    tags=["Zenith IQ"])
stock_router    = APIRouter(prefix="/stocks",   tags=["Stocks"])
analysis_router = APIRouter(prefix="/analysis", tags=["Analysis"])

# ---------------------------------------------------------------------------
# Singletons — instantiated once at startup, reused across requests
# ---------------------------------------------------------------------------

_coordinator = CoordinatorAgent()
_quant       = QuantAgent()
_insider     = InsiderAgent()
_news        = NewsAgent()
_sentiment   = SentimentAgent()


# ===========================================================================
# CORE ENDPOINT — full multi-agent pipeline
# ===========================================================================

@alpha_router.post(
    "/analyse",
    response_model=AnalyseResponse,
    summary="Full Zenith IQ analysis",
    description=(
        "Runs all 5 agents concurrently (Filing, News, Sentiment, Insider, Quant), "
        "computes a weighted Alpha Score, and returns a Gemini-generated investor summary."
    ),
)
async def analyse(request: AnalyseRequest):
    """
    Full pipeline endpoint.

    Flow:
        1. Resolve ticker → company name
        2. Run FilingAgent, NewsAgent, SentimentAgent, InsiderAgent, QuantAgent in parallel
        3. Compute weighted Alpha Score
        4. Generate Gemini investor summary + key risks
        5. Return AnalyseResponse

    Example request:
        POST /api/v1/alpha/analyse
        {
            "ticker": "AAPL",
            "period": "1y",
            "days": 7,
            "start_date": "2023-01-01",
            "end_date": "2025-12-31"
        }

    Example response:
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "alpha_score": 0.6823,
            "signal": "BUY",
            "signal_emoji": "🟩",
            "summary": "Apple continues to show strong fundamentals...",
            "key_risks": [
                "Regulatory pressure in EU could impact App Store revenue.",
                "Slowing iPhone upgrade cycle in key markets.",
                "Insider selling activity elevated over the past 30 days."
            ],
            "agent_results": {
                "FilingAgent":    {"agent": "FilingAgent",    "success": true, "score": 0.72, ...},
                "NewsAgent":      {"agent": "NewsAgent",      "success": true, "score": 0.65, ...},
                "SentimentAgent": {"agent": "SentimentAgent", "success": true, "score": 0.58, ...},
                "InsiderAgent":   {"agent": "InsiderAgent",   "success": true, "score": 0.80, ...},
                "QuantAgent":     {"agent": "QuantAgent",     "success": true, "score": 0.61, ...}
            },
            "weights_used": {
                "FilingAgent": 0.25, "NewsAgent": 0.20,
                "SentimentAgent": 0.15, "InsiderAgent": 0.20, "QuantAgent": 0.20
            },
            "agents_failed": [],
            "duration_ms": 4821
        }
    """
    try:
        report = await _coordinator.analyse(
            ticker     = request.ticker,
            period     = request.period,
            days       = request.days,
            start_date = request.start_date,
            end_date   = request.end_date,
        )
        return report.to_dict()
    except Exception as exc:
        logger.error(f"[/analyse] Unhandled error for {request.ticker}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# INDIVIDUAL AGENT ENDPOINTS — useful for debugging and partial runs
# ===========================================================================

@alpha_router.post(
    "/quant",
    summary="Run Quant Agent only",
    description="Detects H&S and Breakout patterns, computes RSI/MACD/BB, backtests each pattern.",
)
async def run_quant(request: AgentRunRequest):
    """
    Example request:  {"ticker": "TSLA", "period": "1y"}

    Example response:
        {
            "agent": "QuantAgent",
            "success": true,
            "score": 0.6350,
            "data": {
                "patterns": {
                    "head_and_shoulders": {"detected": false, ...},
                    "breakout": {
                        "detected": true,
                        "pattern": "breakout_bullish",
                        "confidence": 0.74,
                        "signal": "bullish",
                        "key_levels": {"resistance": 245.3, "support": 231.1, "latest": 248.7},
                        "backtest": {"occurrences": 12, "wins": 8, "success_rate": 0.6667, ...}
                    }
                },
                "indicators": {
                    "rsi": 58.4, "rsi_signal": "neutral",
                    "macd_bullish": true, "golden_cross": true
                }
            }
        }
    """
    try:
        result = await _quant.run(request.ticker, period=request.period)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@alpha_router.post(
    "/insider",
    summary="Run Insider Agent only",
    description="Scrapes OpenInsider for buy/sell transactions and returns a directional signal.",
)
async def run_insider(request: AgentRunRequest):
    """
    Example response:
        {
            "agent": "InsiderAgent",
            "success": true,
            "score": 0.78,
            "data": {
                "transaction_count": 14,
                "summary": {"buy_count": 9, "sell_count": 5, "buy_value": 4200000, "sell_value": 1100000},
                "recent_transactions": [...]
            }
        }
    """
    try:
        result = await _insider.run(request.ticker)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@alpha_router.post(
    "/news",
    summary="Run News Agent only",
    description="Fetches recent news and uses Gemini to assess tone and extract key claims.",
)
async def run_news(request: AgentRunRequest):
    """
    Example response:
        {
            "agent": "NewsAgent",
            "success": true,
            "score": 0.65,
            "data": {
                "article_count": 18,
                "headlines": ["Apple hits record revenue...", ...],
                "analysis": "Overall tone: bullish. Key claims: ..."
            }
        }
    """
    try:
        result = await _news.run(request.ticker)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@alpha_router.post(
    "/sentiment",
    summary="Run Sentiment Agent only",
    description="Runs RoBERTa FinBERT on Reddit posts and returns a [-1, +1] sentiment score.",
)
async def run_sentiment(request: AgentRunRequest):
    """
    Example response:
        {
            "agent": "SentimentAgent",
            "success": true,
            "score": 0.71,
            "data": {
                "post_count": 35,
                "sentiment_score": 0.42,
                "label": "positive",
                "sample_scores": [
                    {"text": "AAPL to the moon...", "label": "positive", "score": 0.93, "sentiment": 0.88}
                ]
            }
        }
    """
    try:
        result = await _sentiment.run(request.ticker)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# STOCK DATA
# ===========================================================================

@stock_router.get(
    "/{ticker}",
    summary="Fetch stock snapshot",
    description="Returns OHLCV bars and key fundamentals for a ticker.",
)
async def get_stock(
    ticker: str,
    period: str = Query("1mo", description="yfinance period string"),
):
    """
    Example response:
        {
            "agent": "QuantAgent",
            "success": true,
            "score": 0.55,
            "data": {
                "indicators": {"rsi": 52.1, ...},
                "bar_count": 21
            }
        }
    """
    try:
        result = await _quant.run(ticker.upper(), period=period)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# GEMINI REASONING
# ===========================================================================

@analysis_router.post(
    "/contradict",
    response_model=ContradictionResponse,
    summary="Detect contradictions between a filing and news",
)
async def detect_contradictions(request: ReasoningRequest):
    """
    Example request:
        {
            "filing_text": "Revenue grew 15% YoY. Management is confident in sustained growth.",
            "news_text": "Company misses Q3 estimates. Revenue growth slows to 3%.",
            "ticker": "AAPL",
            "extra_context": "CFO sold $2M in shares last month."
        }

    Example response:
        {
            "contradiction_level": "high",
            "contradictions": ["Filing claims 15% growth; news reports 3%."],
            "explanation": "The company's own filing painted a rosier picture...",
            "risk_summary": "Significant gap between guidance and results."
        }
    """
    try:
        inp = ReasoningInput(
            filing_text   = request.filing_text,
            news_text     = request.news_text,
            ticker        = request.ticker,
            extra_context = request.extra_context,
        )
        result = await contradiction_analysis(inp)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@analysis_router.post(
    "/explain",
    response_model=InvestorExplanationResponse,
    summary="Generate an investor-friendly explanation",
)
async def explain_for_investor(request: ReasoningRequest):
    """
    Example request:
        {
            "filing_text": "The company reported $12B in revenue with a 22% operating margin.",
            "news_text": "Analysts upgrade stock to Buy. New product line exceeds expectations.",
            "ticker": "MSFT"
        }

    Example response:
        {
            "summary": "Microsoft had a strong quarter...",
            "key_points": ["$12B revenue with 22% margin.", ...],
            "risk_summary": "No major risks identified.",
            "sentiment": "positive"
        }
    """
    try:
        inp = ReasoningInput(
            filing_text   = request.filing_text,
            news_text     = request.news_text,
            ticker        = request.ticker,
            extra_context = request.extra_context,
        )
        result = await investor_explanation(inp)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@analysis_router.post(
    "/ask",
    summary="Free-form Gemini financial query",
)
async def ask_gemini(payload: dict):
    """
    Example request:  {"prompt": "What are the key risks for semiconductor stocks in 2025?"}
    Example response: {"response": "The key risks include..."}
    """
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        response = await query_gemini(prompt)
        return {"response": response}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# HISTORY — read persisted results from Supabase
# ===========================================================================

@alpha_router.get(
    "/history/{ticker}",
    summary="Get analysis history for a ticker",
    description="Returns the most recent persisted analysis results from Supabase.",
)
async def get_history(
    ticker: str,
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    """
    Example: GET /api/v1/alpha/history/AAPL?limit=5

    Returns list of past analysis runs with alpha_score, signal, summary, created_at.
    """
    try:
        rows = get_analysis_history(ticker.upper(), limit=limit)
        return {"ticker": ticker.upper(), "count": len(rows), "results": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@alpha_router.get(
    "/latest/{ticker}",
    summary="Get the most recent analysis for a ticker",
)
async def get_latest(ticker: str):
    """
    Example: GET /api/v1/alpha/latest/AAPL

    Returns the single most recent full analysis result, or 404 if none exists.
    """
    row = get_latest_analysis(ticker.upper())
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for {ticker.upper()}. Run /alpha/analyse first.",
        )
    return row


@stock_router.get(
    "/{ticker}/news",
    summary="Get cached news for a ticker",
)
async def get_news_cache(
    ticker: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Returns cached news articles from Supabase for a ticker."""
    rows = get_cached_news(ticker.upper(), limit=limit)
    return {"ticker": ticker.upper(), "count": len(rows), "articles": rows}


@stock_router.get(
    "/{ticker}/insider",
    summary="Get cached insider transactions for a ticker",
)
async def get_insider_cache(
    ticker: str,
    limit: int = Query(40, ge=1, le=200),
):
    """Returns cached insider transactions from Supabase for a ticker."""
    rows = get_insider_transactions(ticker.upper(), limit=limit)
    return {"ticker": ticker.upper(), "count": len(rows), "transactions": rows}


@stock_router.get(
    "/{ticker}/sentiment",
    summary="Get latest cached sentiment for a ticker",
)
async def get_sentiment_cache(ticker: str):
    """Returns the most recent sentiment result from Supabase for a ticker."""
    row = get_latest_sentiment(ticker.upper())
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No sentiment data found for {ticker.upper()}.",
        )
    return row


# ===========================================================================
# ZENITH ENDPOINT — unified response for the frontend dashboard
# ===========================================================================

@alpha_router.get(
    "/analyze-stock",
    response_model=ZenithResponse,
    summary="Unified Zenith analysis for a stock symbol",
    description=(
        "Runs Quant, Sentiment (mock), and Insider (mock) agents in parallel "
        "and maps the output to the ZenithResponse shape. Fast — no external "
        "API calls for filing or news scraping."
    ),
)
async def analyze_stock(symbol: str = Query(..., description="Stock ticker symbol, e.g. RELIANCE or AAPL")):
    """
    GET /api/v1/alpha/analyze-stock?symbol=RELIANCE

    Runs three fast agents concurrently:
        - QuantAgent      (yfinance OHLCV + pattern detection)
        - SentimentAgent  (mock social posts + RoBERTa)
        - InsiderAgent    (mock insider activity)

    Skips FilingAgent and NewsAgent to keep response time under ~5s.
    """
    import asyncio

    ticker = symbol.upper().strip()
    try:
        # Run the three fast agents concurrently
        quant_task     = _quant.run(ticker, period="6mo")
        sentiment_task = _sentiment.run(ticker, use_mock=True)
        insider_task   = _insider.run(ticker, use_mock=True)

        quant_res, sentiment_res, insider_res = await asyncio.gather(
            quant_task, sentiment_task, insider_task,
            return_exceptions=True,
        )

        # Replace exceptions with neutral fallback AgentResults
        from agents.base_agent import AgentResult as AR
        if isinstance(quant_res,     Exception):
            logger.error(f"QuantAgent error for {ticker}: {quant_res}")
            quant_res     = AR("QuantAgent",     {}, score=0.5, error=str(quant_res))
        if isinstance(sentiment_res, Exception):
            logger.error(f"SentimentAgent error for {ticker}: {sentiment_res}")
            sentiment_res = AR("SentimentAgent", {}, score=0.5, error=str(sentiment_res))
        if isinstance(insider_res,   Exception):
            logger.error(f"InsiderAgent error for {ticker}: {insider_res}")
            insider_res   = AR("InsiderAgent",   {}, score=0.5, error=str(insider_res))

        # Weighted alpha score: Quant 40%, Sentiment 30%, Insider 30%
        weights = {"QuantAgent": 0.40, "SentimentAgent": 0.30, "InsiderAgent": 0.30}
        agents  = {
            "QuantAgent":     quant_res,
            "SentimentAgent": sentiment_res,
            "InsiderAgent":   insider_res,
        }
        alpha = sum(
            (r.score or 0.5) * weights[n]
            for n, r in agents.items()
        )

        # Build a minimal report dict that _map_to_zenith understands
        report = {
            "ticker":       ticker,
            "alpha_score":  round(alpha, 4),
            "signal":       _classify_signal(alpha),
            "agent_results": {n: r.to_dict() for n, r in agents.items()},
        }

        return _map_to_zenith(report)

    except Exception as exc:
        logger.error(f"[/analyze-stock] {ticker}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


def _classify_signal(score: float) -> str:
    if score >= 0.75: return "STRONG_BUY"
    if score >= 0.60: return "BUY"
    if score >= 0.45: return "NEUTRAL"
    if score >= 0.30: return "SELL"
    return "STRONG_SELL"


def _map_to_zenith(report: dict) -> ZenithResponse:
    """
    Map a coordinator AnalysisReport dict to the ZenithResponse schema.

    Args:
        report: Output of AnalysisReport.to_dict()

    Returns:
        ZenithResponse ready for JSON serialisation.
    """
    agent_results = report.get("agent_results", {})

    # ── Zenith score (0–100) ──────────────────────────────────────────
    zenith_score = int(round(report.get("alpha_score", 0.5) * 100))

    # ── Signal label (human-readable with spaces) ─────────────────────
    signal = report.get("signal", "NEUTRAL").replace("_", " ")

    # ── Narrative conflict (from FilingAgent) ─────────────────────────
    filing = agent_results.get("FilingAgent", {})
    filing_data = filing.get("data", {})
    risk_passages = filing_data.get("risk_passages", [])
    filing_summary = filing_data.get("summary", "")

    # Map alpha score range to conflict level
    alpha = report.get("alpha_score", 0.5)
    if alpha >= 0.75:
        conflict_level = "NONE"
    elif alpha >= 0.60:
        conflict_level = "LOW"
    elif alpha >= 0.45:
        conflict_level = "MEDIUM"
    elif alpha >= 0.30:
        conflict_level = "STRONG"
    else:
        conflict_level = "CRITICAL"

    narrative_conflict = NarrativeConflict(
        level   = conflict_level,
        summary = filing_summary[:200] if filing_summary else "No filing data available.",
        points  = [p[:120] for p in risk_passages[:3]] if risk_passages else [],
    )

    # ── Sentiment divergence ──────────────────────────────────────────
    sentiment_agent = agent_results.get("SentimentAgent", {})
    insider_agent   = agent_results.get("InsiderAgent", {})

    # SentimentAgent score is [0,1] normalised; convert back to [-1,+1]
    retail_raw   = sentiment_agent.get("score") or 0.5
    retail_score = round((retail_raw - 0.5) * 2, 4)   # [0,1] → [-1,+1]

    # InsiderAgent score [0,1]: >0.5 = buying, <0.5 = selling → [-1,+1]
    insider_raw    = insider_agent.get("score") or 0.5
    insider_signal = round((insider_raw - 0.5) * 2, 4)

    divergence = abs(retail_score - insider_signal)
    if divergence > 0.8:
        div_signal = "MANIPULATION RISK"
    elif divergence > 0.4:
        div_signal = "DIVERGING"
    else:
        div_signal = "ALIGNED"

    sentiment_divergence = SentimentDivergence(
        retail_sentiment = retail_score,
        insider_activity = insider_signal,
        signal           = div_signal,
    )

    # ── Quant insight ─────────────────────────────────────────────────
    quant_agent = agent_results.get("QuantAgent", {})
    quant_data  = quant_agent.get("data", {})
    patterns    = quant_data.get("patterns", {})

    detected_pattern = "none"
    success_rate     = 0
    confidence       = 0.0

    for _name, pdata in patterns.items():
        if isinstance(pdata, dict) and pdata.get("detected"):
            detected_pattern = pdata.get("pattern", "none")
            confidence       = float(pdata.get("confidence", 0.0))
            bt = pdata.get("backtest") or {}
            success_rate = int(round(bt.get("success_rate", 0) * 100))
            break

    quant_insight = QuantInsight(
        pattern      = detected_pattern,
        success_rate = success_rate,
        confidence   = confidence,
    )

    return ZenithResponse(
        symbol               = report.get("ticker", "UNKNOWN"),
        zenith_score         = zenith_score,
        signal               = signal,
        narrative_conflict   = narrative_conflict,
        sentiment_divergence = sentiment_divergence,
        quant_insight        = quant_insight,
    )
