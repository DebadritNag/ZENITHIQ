"""
Pydantic schemas for Zenith IQ API request/response validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class AgentResultSchema(BaseModel):
    agent:   str
    success: bool
    score:   float | None
    data:    dict[str, Any]
    error:   str | None


# ---------------------------------------------------------------------------
# /alpha/analyse  — full pipeline
# ---------------------------------------------------------------------------

class AnalyseRequest(BaseModel):
    ticker:     str = Field(...,          description="Stock ticker symbol or company name", example="AAPL")
    period:     str = Field("1y",         description="yfinance period for quant/stock data", example="1y")
    days:       int = Field(7,            description="News lookback window in days", example=7)
    start_date: str = Field("2023-01-01", description="SEC filing search start date (YYYY-MM-DD)")
    end_date:   str = Field("2025-12-31", description="SEC filing search end date (YYYY-MM-DD)")

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()


class AnalyseResponse(BaseModel):
    ticker:        str
    company_name:  str   = Field(..., description="Resolved company name")
    alpha_score:   float = Field(..., description="Weighted composite score 0.0–1.0")
    signal:        str   = Field(..., description="STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL")
    signal_emoji:  str   = Field(..., description="Visual indicator for the signal")
    summary:       str   = Field(..., description="Gemini-generated investor summary")
    key_risks:     list[str] = Field(..., description="Top 3 risk bullets from Gemini")
    agent_results: dict[str, AgentResultSchema]
    weights_used:  dict[str, float]
    agents_failed: list[str] = Field(..., description="Names of agents that returned errors")
    duration_ms:   int       = Field(..., description="Total analysis wall-clock time in ms")


# ---------------------------------------------------------------------------
# /alpha/{agent}  — individual agent runs
# ---------------------------------------------------------------------------

class AgentRunRequest(BaseModel):
    ticker: str = Field(..., example="TSLA")
    period: str = Field("1y", example="1y")

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()


# ---------------------------------------------------------------------------
# /analysis/contradict  and  /analysis/explain
# ---------------------------------------------------------------------------

class ReasoningRequest(BaseModel):
    filing_text: str = Field(
        ...,
        min_length=20,
        description="Excerpt from an SEC filing (10-K / 10-Q)",
        example="Revenue increased 12% YoY. Management expects continued growth.",
    )
    news_text: str = Field(
        ...,
        min_length=10,
        description="Recent news article text or concatenated headlines",
        example="Company faces antitrust probe. Cloud division growth slows.",
    )
    ticker: str = Field("", description="Optional ticker symbol for context", example="AAPL")
    extra_context: str = Field(
        "",
        description="Optional extra context (e.g. insider activity summary)",
        example="3 executives sold shares worth $4M in the past 30 days.",
    )


class ContradictionResponse(BaseModel):
    contradiction_level: str      = Field(..., description="none | low | medium | high | critical")
    contradictions:      list[str]= Field(..., description="Specific contradictions identified")
    explanation:         str      = Field(..., description="Investor-friendly explanation")
    risk_summary:        str      = Field(..., description="Concise 1-2 sentence risk assessment")


class InvestorExplanationResponse(BaseModel):
    summary:      str       = Field(..., description="Plain-English one-paragraph overview")
    key_points:   list[str] = Field(..., description="3-5 most important facts")
    risk_summary: str       = Field(..., description="Concise risk assessment")
    sentiment:    str       = Field(..., description="positive | neutral | negative")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status:  str
    version: str


# ---------------------------------------------------------------------------
# /analyze-stock  — unified Zenith response shape
# ---------------------------------------------------------------------------

class NarrativeConflict(BaseModel):
    level:   str        = Field(..., description="NONE | LOW | MEDIUM | STRONG | CRITICAL")
    summary: str        = Field(..., description="One-sentence conflict summary")
    points:  list[str]  = Field(..., description="Specific conflict bullet points")


class SentimentDivergence(BaseModel):
    retail_sentiment: float = Field(..., description="Retail sentiment score -1 to +1")
    insider_activity: float = Field(..., description="Insider signal -1 to +1 (negative = selling)")
    signal:           str   = Field(..., description="ALIGNED | DIVERGING | MANIPULATION RISK")


class QuantInsight(BaseModel):
    pattern:      str   = Field(..., description="Detected pattern name or 'none'")
    success_rate: int   = Field(..., description="Backtest success rate 0–100")
    confidence:   float = Field(..., description="Pattern confidence 0.0–1.0")


class ZenithResponse(BaseModel):
    symbol:                 str
    zenith_score:           int               = Field(..., description="Composite score 0–100")
    signal:                 str               = Field(..., description="STRONG BUY | BUY | NEUTRAL | SELL | STRONG SELL")
    narrative_conflict:     NarrativeConflict
    sentiment_divergence:   SentimentDivergence
    quant_insight:          QuantInsight
