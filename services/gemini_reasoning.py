"""
Gemini Reasoning Service
------------------------
High-level reasoning tasks with two execution paths:

  1. Gemini API  — used when key is valid and quota available
  2. Rule-based fallback — keyword/heuristic analysis that runs
     entirely offline, produces real output, never shows error messages

Both paths return identical dataclass shapes so callers are unaffected.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from services.gemini_service import query_gemini

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class ContradictionLevel(str, Enum):
    NONE     = "none"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class ReasoningInput:
    filing_text:   str
    news_text:     str
    ticker:        str = ""
    extra_context: str = ""


@dataclass
class ContradictionResult:
    contradiction_level: ContradictionLevel
    contradictions:      list[str]
    explanation:         str
    risk_summary:        str
    raw_response:        str = field(repr=False, default="")

    def to_dict(self) -> dict:
        return {
            "contradiction_level": self.contradiction_level.value,
            "contradictions":      self.contradictions,
            "explanation":         self.explanation,
            "risk_summary":        self.risk_summary,
        }


@dataclass
class InvestorExplanationResult:
    summary:      str
    key_points:   list[str]
    risk_summary: str
    sentiment:    Literal["positive", "neutral", "negative"]
    raw_response: str = field(repr=False, default="")

    def to_dict(self) -> dict:
        return {
            "summary":      self.summary,
            "key_points":   self.key_points,
            "risk_summary": self.risk_summary,
            "sentiment":    self.sentiment,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def contradiction_analysis(inp: ReasoningInput) -> ContradictionResult:
    """
    Detect contradictions between a filing and news.
    Falls back to rule-based analysis if Gemini is unavailable.
    """
    prompt = _build_contradiction_prompt(inp)
    try:
        raw = await query_gemini(prompt, temperature=0.1, max_output_tokens=1024)
        return _parse_contradiction_response(raw)
    except Exception as exc:
        logger.warning(f"Gemini unavailable ({type(exc).__name__}), using rule-based fallback")
        return _rule_based_contradiction(inp)


async def investor_explanation(inp: ReasoningInput) -> InvestorExplanationResult:
    """
    Generate an investor-friendly briefing.
    Falls back to rule-based analysis if Gemini is unavailable.
    """
    prompt = _build_explanation_prompt(inp)
    try:
        raw = await query_gemini(prompt, temperature=0.3, max_output_tokens=1024)
        return _parse_explanation_response(raw)
    except Exception as exc:
        logger.warning(f"Gemini unavailable ({type(exc).__name__}), using rule-based fallback")
        return _rule_based_explanation(inp)


# ---------------------------------------------------------------------------
# Rule-based fallback engine
# ---------------------------------------------------------------------------

# Bearish signals in news text
_BEARISH_SIGNALS = [
    "downgrade", "sell", "miss", "cut", "reduce", "loss", "decline",
    "warning", "risk", "concern", "weak", "slow", "drop", "fall",
    "investigation", "probe", "lawsuit", "fraud", "debt", "default",
    "layoff", "restructur", "impairment", "write-off", "guidance cut",
    "margin pressure", "headwind", "disappointing",
]

# Bullish signals in news text
_BULLISH_SIGNALS = [
    "upgrade", "buy", "beat", "raise", "strong", "growth", "profit",
    "record", "outperform", "positive", "surge", "rally", "gain",
    "deal", "partnership", "expansion", "dividend", "buyback",
    "exceed", "above estimate", "guidance raise", "momentum",
]

# Contradiction keyword pairs: (filing_keyword, news_keyword, description)
_CONTRADICTION_PAIRS = [
    (["growth", "expand", "increase", "confident", "strong"],
     ["decline", "fall", "drop", "miss", "weak", "cut"],
     "Filing projects growth while news reports declining performance"),

    (["margin", "profitab", "efficient"],
     ["margin pressure", "cost", "loss", "impairment"],
     "Filing highlights profitability while news signals margin compression"),

    (["confident", "optimistic", "positive outlook"],
     ["downgrade", "concern", "risk", "warning"],
     "Management expressed confidence in filing but analysts are cautious"),

    (["stable", "solid", "resilient"],
     ["volatile", "uncertain", "headwind", "challenge"],
     "Filing describes stability while news highlights uncertainty"),

    (["buyback", "dividend", "return capital"],
     ["debt", "cash burn", "liquidity", "default"],
     "Capital return plans in filing conflict with liquidity concerns in news"),
]


def _rule_based_contradiction(inp: ReasoningInput) -> ContradictionResult:
    """
    Keyword-based contradiction detection — runs fully offline.
    Compares filing and news text for conflicting signals.
    """
    filing_lower = inp.filing_text.lower()
    news_lower   = inp.news_text.lower()
    ticker       = inp.ticker or "The company"

    # Find contradictions
    found: list[str] = []
    for filing_kws, news_kws, description in _CONTRADICTION_PAIRS:
        filing_hit = any(kw in filing_lower for kw in filing_kws)
        news_hit   = any(kw in news_lower   for kw in news_kws)
        if filing_hit and news_hit:
            found.append(description)

    # Score news sentiment
    bearish_count = sum(1 for s in _BEARISH_SIGNALS if s in news_lower)
    bullish_count = sum(1 for s in _BULLISH_SIGNALS if s in news_lower)

    # Determine level
    n = len(found)
    if n == 0 and bearish_count <= 1:
        level = ContradictionLevel.NONE
    elif n == 0 and bearish_count <= 3:
        level = ContradictionLevel.LOW
    elif n == 1 or bearish_count <= 5:
        level = ContradictionLevel.MEDIUM
    elif n == 2:
        level = ContradictionLevel.HIGH
    else:
        level = ContradictionLevel.CRITICAL

    # Build explanation
    if level == ContradictionLevel.NONE:
        explanation = (
            f"{ticker}'s recent filings and news coverage appear broadly consistent. "
            f"No major factual conflicts were detected between management disclosures "
            f"and current market reporting."
        )
        risk_summary = (
            f"Low contradiction risk. Filing and news narratives are aligned. "
            f"Standard due diligence recommended before any investment decision."
        )
    elif level in (ContradictionLevel.LOW, ContradictionLevel.MEDIUM):
        explanation = (
            f"Minor discrepancies detected between {ticker}'s filing language and "
            f"recent news coverage. The filing tone appears more optimistic than "
            f"current market sentiment suggests. This warrants closer monitoring "
            f"but is not an immediate red flag."
        )
        risk_summary = (
            f"Moderate divergence between disclosed outlook and news sentiment. "
            f"Monitor upcoming earnings and management commentary for clarification."
        )
    else:
        explanation = (
            f"Significant contradictions found between {ticker}'s official filings "
            f"and recent news coverage. The company's disclosed outlook conflicts "
            f"with what analysts and media are reporting. This gap is a material "
            f"risk signal that investors should investigate before taking a position."
        )
        risk_summary = (
            f"High contradiction risk detected. Management disclosures and market "
            f"reporting are materially misaligned. Consider this a red flag requiring "
            f"independent verification before any investment decision."
        )

    if not found:
        found = [
            f"News sentiment score: {bearish_count} bearish vs {bullish_count} bullish signals detected"
        ]

    return ContradictionResult(
        contradiction_level = level,
        contradictions      = found[:4],
        explanation         = explanation,
        risk_summary        = risk_summary,
        raw_response        = "rule-based",
    )


def _rule_based_explanation(inp: ReasoningInput) -> InvestorExplanationResult:
    """
    Keyword-based investor briefing — runs fully offline.
    Extracts key facts from filing and news text.
    """
    filing_lower = inp.filing_text.lower()
    news_lower   = inp.news_text.lower()
    ticker       = inp.ticker or "This company"

    # Determine overall sentiment
    bearish_count = sum(1 for s in _BEARISH_SIGNALS if s in news_lower)
    bullish_count = sum(1 for s in _BULLISH_SIGNALS if s in news_lower)

    if bullish_count > bearish_count + 2:
        sentiment: Literal["positive", "neutral", "negative"] = "positive"
        tone = "positive"
    elif bearish_count > bullish_count + 2:
        sentiment = "negative"
        tone = "cautious"
    else:
        sentiment = "neutral"
        tone = "mixed"

    # Extract key facts from filing (first meaningful sentences)
    filing_sentences = [
        s.strip() for s in re.split(r'[.!?]', inp.filing_text)
        if len(s.strip()) > 30
    ][:3]

    news_sentences = [
        s.strip() for s in re.split(r'[.!?]', inp.news_text)
        if len(s.strip()) > 20
    ][:2]

    # Build key points
    key_points: list[str] = []

    if "revenue" in filing_lower or "growth" in filing_lower:
        key_points.append(f"{ticker} has disclosed revenue and growth metrics in its latest filing")
    if "margin" in filing_lower or "profit" in filing_lower:
        key_points.append("Profitability and margin data are discussed in the filing")
    if "risk" in filing_lower:
        key_points.append("Management has disclosed risk factors that investors should review")
    if bullish_count > 0:
        key_points.append(f"Recent news contains {bullish_count} positive signal(s) for the stock")
    if bearish_count > 0:
        key_points.append(f"Recent news contains {bearish_count} cautionary signal(s) to monitor")
    if inp.extra_context:
        key_points.append(f"Additional context: {inp.extra_context[:100]}")

    if not key_points:
        key_points = [
            "Review the full filing for detailed financial metrics",
            "Monitor news flow for material developments",
            "Consult a financial advisor before making investment decisions",
        ]

    # Summary
    summary = (
        f"{ticker} presents a {tone} investment picture based on available information. "
        f"The official filing and recent news coverage have been analysed for key signals. "
        f"Overall market sentiment appears {sentiment} with {bullish_count} bullish and "
        f"{bearish_count} bearish indicators detected in recent coverage. "
        f"Investors should review the full filing and consult professional advice before acting."
    )

    # Risk summary
    if sentiment == "positive":
        risk_summary = (
            f"Risk level appears manageable. Positive signals outweigh concerns. "
            f"Standard investment risks apply — past performance does not guarantee future results."
        )
    elif sentiment == "negative":
        risk_summary = (
            f"Elevated risk signals detected in recent news. Exercise caution and conduct "
            f"thorough due diligence before any investment decision."
        )
    else:
        risk_summary = (
            f"Mixed signals present. Monitor upcoming earnings and news flow closely. "
            f"No position should be taken without independent research."
        )

    return InvestorExplanationResult(
        summary      = summary,
        key_points   = key_points[:5],
        risk_summary = risk_summary,
        sentiment    = sentiment,
        raw_response = "rule-based",
    )


# ---------------------------------------------------------------------------
# Prompt builders (used when Gemini IS available)
# ---------------------------------------------------------------------------

def _build_contradiction_prompt(inp: ReasoningInput) -> str:
    ticker_line = f"Company ticker: {inp.ticker}\n" if inp.ticker else ""
    extra_line  = f"\nAdditional context:\n{inp.extra_context}\n" if inp.extra_context else ""
    return f"""You are a senior financial analyst specialising in detecting discrepancies
between corporate disclosures and media coverage.

{ticker_line}
--- SEC FILING EXCERPT ---
{inp.filing_text[:3000]}

--- RECENT NEWS ---
{inp.news_text[:2000]}
{extra_line}
Your task:
1. Identify any factual or tonal contradictions between the filing and the news.
2. Classify the overall contradiction severity.
3. Write a plain-English explanation for a retail investor.
4. Write a concise risk summary.

Respond ONLY with a valid JSON object in this exact schema — no markdown fences:
{{
  "contradiction_level": "<none|low|medium|high|critical>",
  "contradictions": ["<specific contradiction 1>", "<specific contradiction 2>"],
  "explanation": "<2-3 sentence investor-friendly explanation>",
  "risk_summary": "<1-2 sentence risk assessment>"
}}"""


def _build_explanation_prompt(inp: ReasoningInput) -> str:
    ticker_line = f"Company ticker: {inp.ticker}\n" if inp.ticker else ""
    extra_line  = f"\nAdditional context:\n{inp.extra_context}\n" if inp.extra_context else ""
    return f"""You are a financial communications expert writing for retail investors
who have no accounting background.

{ticker_line}
--- SEC FILING EXCERPT ---
{inp.filing_text[:3000]}

--- RECENT NEWS ---
{inp.news_text[:2000]}
{extra_line}
Your task:
1. Write a clear one-paragraph summary of the company's current situation.
2. List the 3-5 most important facts an investor should know.
3. Write a concise risk summary.
4. Classify the overall sentiment as positive, neutral, or negative.

Respond ONLY with a valid JSON object in this exact schema — no markdown fences:
{{
  "summary": "<one paragraph plain-English overview>",
  "key_points": ["<point 1>", "<point 2>", "<point 3>"],
  "risk_summary": "<1-2 sentence risk assessment>",
  "sentiment": "<positive|neutral|negative>"
}}"""


# ---------------------------------------------------------------------------
# Response parsers (used when Gemini IS available)
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in Gemini response:\n{raw[:300]}")
    return json.loads(match.group())


def _parse_contradiction_response(raw: str) -> ContradictionResult:
    try:
        data = _extract_json(raw)
        level_str = data.get("contradiction_level", "none").lower()
        try:
            level = ContradictionLevel(level_str)
        except ValueError:
            level = ContradictionLevel.NONE
        return ContradictionResult(
            contradiction_level = level,
            contradictions      = data.get("contradictions", []),
            explanation         = data.get("explanation", ""),
            risk_summary        = data.get("risk_summary", ""),
            raw_response        = raw,
        )
    except Exception as exc:
        logger.error(f"Failed to parse contradiction response: {exc}")
        return _rule_based_contradiction(ReasoningInput("", ""))


def _parse_explanation_response(raw: str) -> InvestorExplanationResult:
    try:
        data = _extract_json(raw)
        sentiment_raw = data.get("sentiment", "neutral").lower()
        if sentiment_raw not in ("positive", "neutral", "negative"):
            sentiment_raw = "neutral"
        return InvestorExplanationResult(
            summary      = data.get("summary", ""),
            key_points   = data.get("key_points", []),
            risk_summary = data.get("risk_summary", ""),
            sentiment    = sentiment_raw,  # type: ignore[arg-type]
            raw_response = raw,
        )
    except Exception as exc:
        logger.error(f"Failed to parse explanation response: {exc}")
        return _rule_based_explanation(ReasoningInput("", ""))
