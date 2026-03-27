"""
Coordinator Agent
-----------------
Orchestrates the full Zenith IQ pipeline:

    1. Resolve ticker → company name via the data pipeline
    2. Run all 5 agents concurrently (Filing, News, Sentiment, Insider, Quant)
    3. Compute a weighted Alpha Score from agent scores
    4. Generate a Gemini-powered investor summary from combined outputs
    5. Return a fully structured AnalysisReport

The coordinator is the only entry point the API layer calls.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import AgentResult
from agents.filing_agent import FilingAgent
from agents.news_agent import NewsAgent
from agents.sentiment_agent import SentimentAgent
from agents.insider_agent import InsiderAgent
from agents.quant_agent import QuantAgent
from data_pipeline import fetch_stock_snapshot
from services.gemini_service import query_gemini
from services.supabase_service import save_analysis_result

logger = logging.getLogger("coordinator")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Weights must sum to 1.0
AGENT_WEIGHTS: dict[str, float] = {
    "FilingAgent":    0.25,
    "NewsAgent":      0.20,
    "SentimentAgent": 0.15,
    "InsiderAgent":   0.20,
    "QuantAgent":     0.20,
}

SIGNAL_THRESHOLDS = {
    "STRONG_BUY":  0.75,
    "BUY":         0.60,
    "NEUTRAL":     0.45,
    "SELL":        0.30,
    # below 0.30 → STRONG_SELL
}

SIGNAL_EMOJI = {
    "STRONG_BUY":  "🟢",
    "BUY":         "🟩",
    "NEUTRAL":     "🟡",
    "SELL":        "🟧",
    "STRONG_SELL": "🔴",
}


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class AnalysisReport:
    """
    Complete output of a coordinator analysis run.

    Attributes:
        ticker:         Normalised ticker symbol.
        company_name:   Resolved company name (from yfinance).
        alpha_score:    Weighted composite score 0.0–1.0.
        signal:         Human-readable signal label.
        summary:        Gemini-generated investor summary paragraph.
        key_risks:      Top risk bullets extracted by Gemini.
        agent_results:  Per-agent result dicts.
        weights_used:   Weight map used for scoring.
        agents_failed:  Names of agents that returned errors.
        duration_ms:    Total wall-clock time in milliseconds.
    """
    ticker:        str
    company_name:  str
    alpha_score:   float
    signal:        str
    summary:       str
    key_risks:     list[str]
    agent_results: dict[str, dict]
    weights_used:  dict[str, float]
    agents_failed: list[str]
    duration_ms:   int

    def to_dict(self) -> dict:
        return {
            "ticker":        self.ticker,
            "company_name":  self.company_name,
            "alpha_score":   self.alpha_score,
            "signal":        self.signal,
            "signal_emoji":  SIGNAL_EMOJI.get(self.signal, ""),
            "summary":       self.summary,
            "key_risks":     self.key_risks,
            "agent_results": self.agent_results,
            "weights_used":  self.weights_used,
            "agents_failed": self.agents_failed,
            "duration_ms":   self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class CoordinatorAgent:
    """
    Orchestrates all Zenith IQ sub-agents and produces a final AnalysisReport.

    Usage:
        coordinator = CoordinatorAgent()
        report = await coordinator.analyse("AAPL")
        print(report.signal, report.alpha_score)
    """

    def __init__(self):
        self._agents: dict[str, Any] = {
            "FilingAgent":    FilingAgent(),
            "NewsAgent":      NewsAgent(),
            "SentimentAgent": SentimentAgent(),
            "InsiderAgent":   InsiderAgent(),
            "QuantAgent":     QuantAgent(),
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def analyse(self, ticker: str, **kwargs: Any) -> AnalysisReport:
        """
        Run the full Zenith IQ pipeline for a ticker.

        Args:
            ticker:     Stock ticker symbol (e.g. 'AAPL' or 'apple').
            period:     yfinance period for quant/stock data (default '1y').
            days:       News lookback window in days (default 7).
            start_date: SEC filing search start date (default '2023-01-01').
            end_date:   SEC filing search end date   (default '2025-12-31').

        Returns:
            AnalysisReport with alpha_score, signal, summary, and all agent data.
        """
        t_start = time.monotonic()
        ticker = ticker.upper().strip()
        logger.info(f"[Coordinator] Starting analysis for {ticker}")

        # Step 1 — resolve company name (non-blocking, best-effort)
        company_name = await self._resolve_company_name(ticker)

        # Step 2 — run all agents concurrently
        raw_results = await self._run_agents(ticker, **kwargs)

        # Step 3 — compute weighted Alpha Score
        alpha_score = self._compute_alpha(raw_results)
        signal      = self._classify_signal(alpha_score)

        # Step 4 — generate Gemini summary from combined agent outputs
        summary, key_risks = await self._generate_summary(
            ticker, company_name, signal, alpha_score, raw_results
        )

        # Step 5 — collect failed agents
        agents_failed = [
            name for name, res in raw_results.items() if not res.success
        ]

        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            f"[Coordinator] {ticker} done in {duration_ms}ms | "
            f"score={alpha_score:.4f} | signal={signal}"
        )

        report = AnalysisReport(
            ticker        = ticker,
            company_name  = company_name,
            alpha_score   = round(alpha_score, 4),
            signal        = signal,
            summary       = summary,
            key_risks     = key_risks,
            agent_results = {n: r.to_dict() for n, r in raw_results.items()},
            weights_used  = AGENT_WEIGHTS,
            agents_failed = agents_failed,
            duration_ms   = duration_ms,
        )

        # Persist to Supabase (non-blocking best-effort)
        try:
            save_analysis_result(report.to_dict())
        except Exception as exc:
            logger.warning(f"[Coordinator] Supabase persist failed (non-fatal): {exc}")

        return report

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    async def _resolve_company_name(self, ticker: str) -> str:
        """
        Resolve a ticker symbol to a company name via the data pipeline.

        Falls back to the ticker symbol itself on any error.

        Args:
            ticker: Normalised ticker symbol.

        Returns:
            Company name string.
        """
        try:
            loop = asyncio.get_event_loop()
            snapshot = await loop.run_in_executor(
                None, fetch_stock_snapshot, ticker, "5d"
            )
            return snapshot.company_name or ticker
        except Exception as exc:
            logger.warning(f"[Coordinator] Could not resolve company name for {ticker}: {exc}")
            return ticker

    async def _run_agents(
        self, ticker: str, **kwargs: Any
    ) -> dict[str, AgentResult]:
        """
        Launch all agents concurrently via asyncio.gather.

        Failed agents are caught and replaced with a neutral AgentResult
        so one broken integration never kills the whole pipeline.

        Args:
            ticker:  Ticker symbol.
            **kwargs: Forwarded to every agent's run() method.

        Returns:
            Dict mapping agent name → AgentResult.
        """
        tasks = {
            name: agent.run(ticker, **kwargs)
            for name, agent in self._agents.items()
        }

        outputs = await asyncio.gather(*tasks.values(), return_exceptions=True)

        results: dict[str, AgentResult] = {}
        for name, output in zip(tasks.keys(), outputs):
            if isinstance(output, Exception):
                logger.error(f"[Coordinator] {name} raised: {output}")
                results[name] = AgentResult(
                    name, {}, score=0.5, error=str(output)
                )
            else:
                results[name] = output
                logger.info(
                    f"[Coordinator] {name} → score={output.score:.4f} "
                    f"success={output.success}"
                )

        return results

    async def _generate_summary(
        self,
        ticker: str,
        company_name: str,
        signal: str,
        alpha_score: float,
        results: dict[str, AgentResult],
    ) -> tuple[str, list[str]]:
        """
        Ask Gemini to synthesise all agent outputs into an investor summary.

        Builds a structured context block from each agent's data and asks
        Gemini for a plain-English paragraph + top risk bullets.

        Args:
            ticker:       Ticker symbol.
            company_name: Resolved company name.
            signal:       Classified signal label.
            alpha_score:  Computed alpha score.
            results:      All agent results.

        Returns:
            Tuple of (summary_paragraph: str, key_risks: list[str]).
        """
        context = self._build_summary_context(ticker, company_name, signal, alpha_score, results)
        prompt = f"""You are a senior financial analyst writing a briefing for a retail investor.

Based on the following multi-source analysis of {company_name} ({ticker}):

{context}

Write:
1. SUMMARY: A single clear paragraph (4-6 sentences) explaining the overall investment picture.
   Use plain English. No jargon. State the signal ({signal}) and what's driving it.

2. KEY_RISKS: Exactly 3 bullet points of the most important risks, each under 20 words.
   Format each bullet as: - <risk text>

Respond in this exact format — nothing else:
SUMMARY: <paragraph>
KEY_RISKS:
- <risk 1>
- <risk 2>
- <risk 3>"""

        try:
            raw = await query_gemini(prompt, temperature=0.3, max_output_tokens=512)
            return self._parse_summary_response(raw)
        except Exception as exc:
            logger.warning(f"[Coordinator] Gemini summary failed ({type(exc).__name__}), using rule-based fallback")
            return self._rule_based_summary(ticker, company_name, signal, alpha_score, results)

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _compute_alpha(self, results: dict[str, AgentResult]) -> float:
        """
        Compute the weighted average Alpha Score.

        Agents with score=None are skipped and their weight is
        redistributed proportionally among successful agents.

        Args:
            results: Dict mapping agent name → AgentResult.

        Returns:
            Float between 0.0 and 1.0.
        """
        valid = {
            name: res for name, res in results.items()
            if res.score is not None
        }
        if not valid:
            return 0.5

        total_weight = sum(AGENT_WEIGHTS.get(n, 0) for n in valid)
        if total_weight == 0:
            return 0.5

        weighted_sum = sum(
            res.score * AGENT_WEIGHTS.get(name, 0)
            for name, res in valid.items()
        )
        return weighted_sum / total_weight

    def _classify_signal(self, score: float) -> str:
        """
        Map a numeric Alpha Score to a signal label.

        Args:
            score: Float between 0.0 and 1.0.

        Returns:
            One of: STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL.
        """
        if score >= SIGNAL_THRESHOLDS["STRONG_BUY"]:
            return "STRONG_BUY"
        if score >= SIGNAL_THRESHOLDS["BUY"]:
            return "BUY"
        if score >= SIGNAL_THRESHOLDS["NEUTRAL"]:
            return "NEUTRAL"
        if score >= SIGNAL_THRESHOLDS["SELL"]:
            return "SELL"
        return "STRONG_SELL"

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def _build_summary_context(
        self,
        ticker: str,
        company_name: str,
        signal: str,
        alpha_score: float,
        results: dict[str, AgentResult],
    ) -> str:
        """
        Build a structured text block from all agent outputs for the Gemini prompt.

        Args:
            ticker, company_name, signal, alpha_score: Metadata.
            results: All agent results.

        Returns:
            Multi-line context string.
        """
        lines = [
            f"Ticker: {ticker} | Company: {company_name}",
            f"Alpha Score: {alpha_score:.4f} | Signal: {signal}",
            f"Agent Weights: {AGENT_WEIGHTS}",
            "",
        ]

        for name, res in results.items():
            weight = AGENT_WEIGHTS.get(name, 0)
            status = "✓" if res.success else "✗ FAILED"
            lines.append(f"[{name}] score={res.score:.4f} weight={weight} {status}")

            data = res.data
            if not data:
                continue

            # Extract the most useful field per agent
            if name == "FilingAgent":
                if data.get("summary"):
                    lines.append(f"  Filing summary: {str(data['summary'])[:300]}")
                if data.get("form_type"):
                    lines.append(f"  Form: {data['form_type']} filed {data.get('filing_date','')}")

            elif name == "NewsAgent":
                if data.get("headlines"):
                    lines.append(f"  Top headlines: {'; '.join(data['headlines'][:3])}")
                if data.get("analysis"):
                    lines.append(f"  News analysis: {str(data['analysis'])[:300]}")

            elif name == "SentimentAgent":
                lines.append(
                    f"  Sentiment: {data.get('label','?')} "
                    f"score={data.get('sentiment_score', '?')} "
                    f"posts={data.get('post_count', 0)}"
                )

            elif name == "InsiderAgent":
                s = data.get("summary", {})
                lines.append(
                    f"  Insider: {s.get('buy_count',0)} buys (${s.get('buy_value',0):,.0f}) "
                    f"vs {s.get('sell_count',0)} sells (${s.get('sell_value',0):,.0f})"
                )

            elif name == "QuantAgent":
                ind = data.get("indicators", {})
                patterns = data.get("patterns", {})
                lines.append(
                    f"  Indicators: RSI={ind.get('rsi','?')} ({ind.get('rsi_signal','?')}) "
                    f"MACD={'bullish' if ind.get('macd_bullish') else 'bearish'} "
                    f"GoldenCross={ind.get('golden_cross','?')}"
                )
                for pname, pdata in patterns.items():
                    if pdata.get("detected"):
                        bt = pdata.get("backtest") or {}
                        lines.append(
                            f"  Pattern: {pdata['pattern']} detected "
                            f"confidence={pdata.get('confidence','?')} "
                            f"backtest_success={bt.get('success_rate','?')}"
                        )

            lines.append("")

        return "\n".join(lines)

    def _parse_summary_response(self, raw: str) -> tuple[str, list[str]]:
        """
        Parse Gemini's structured SUMMARY / KEY_RISKS response.

        Args:
            raw: Raw Gemini response text.

        Returns:
            Tuple of (summary: str, key_risks: list[str]).
        """
        import re

        summary = ""
        key_risks: list[str] = []

        # Extract SUMMARY block
        summary_match = re.search(r"SUMMARY:\s*(.+?)(?=KEY_RISKS:|$)", raw, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()

        # Extract KEY_RISKS bullets
        risks_match = re.search(r"KEY_RISKS:\s*(.+)", raw, re.DOTALL)
        if risks_match:
            bullets = re.findall(r"-\s*(.+)", risks_match.group(1))
            key_risks = [b.strip() for b in bullets if b.strip()]

        if not summary:
            summary = raw.strip()[:500]

        return summary, key_risks

    def _rule_based_summary(
        self,
        ticker: str,
        company_name: str,
        signal: str,
        alpha_score: float,
        results: dict[str, AgentResult],
    ) -> tuple[str, list[str]]:
        """
        Generate a summary and key risks from agent data without Gemini.
        Extracts real signals from each agent's output.

        Returns:
            Tuple of (summary: str, key_risks: list[str]).
        """
        pct   = int(round(alpha_score * 100))
        risks: list[str] = []

        # ── Pull signals from each agent ──────────────────────────────

        # News headlines → risk signals
        news_data = results.get("NewsAgent", AgentResult("", {})).data or {}
        headlines = news_data.get("headlines", [])
        if headlines:
            # Pick the most bearish-sounding headline as a risk
            bearish_kw = ["cut", "miss", "fall", "risk", "concern", "probe",
                          "downgrade", "loss", "decline", "warning", "weak"]
            for h in headlines:
                if any(kw in h.lower() for kw in bearish_kw):
                    risks.append(f"News risk: {h[:90]}")
                    break
            if not risks and headlines:
                risks.append(f"Monitor news flow: {headlines[0][:80]}")

        # Sentiment → retail vs insider divergence risk
        sent_data    = results.get("SentimentAgent", AgentResult("", {})).data or {}
        insider_data = results.get("InsiderAgent",   AgentResult("", {})).data or {}
        sent_label   = sent_data.get("label", "neutral")
        mock_activity = insider_data.get("mock_activity", "")
        if sent_label == "positive" and mock_activity == "sell":
            risks.append("Retail sentiment is bullish but insiders are selling — potential divergence risk")
        elif sent_label == "negative":
            risks.append(f"Retail social sentiment is negative for {ticker.split('.')[0]}")

        # Quant → technical risks
        quant_data = results.get("QuantAgent", AgentResult("", {})).data or {}
        indicators = quant_data.get("indicators", {})
        rsi_signal = indicators.get("rsi_signal", "")
        golden     = indicators.get("golden_cross")
        if rsi_signal == "overbought":
            risks.append(f"RSI is overbought ({indicators.get('rsi', '?')}) — pullback risk in the short term")
        elif golden is False:
            risks.append("Death cross on moving averages signals bearish medium-term momentum")
        patterns = quant_data.get("patterns", {})
        for pname, pdata in patterns.items():
            if isinstance(pdata, dict) and pdata.get("detected") and pdata.get("signal") == "bearish":
                risks.append(f"Bearish {pdata.get('pattern','pattern')} detected with {int((pdata.get('confidence',0))*100)}% confidence")
                break

        # Filing → risk passages
        filing_data = results.get("FilingAgent", AgentResult("", {})).data or {}
        passages    = filing_data.get("risk_passages", [])
        if passages:
            snippet = passages[0][:100].strip()
            risks.append(f"Filing risk factor: {snippet}...")

        # Insider → heavy selling
        insider_summary = insider_data.get("summary", {})
        if isinstance(insider_summary, dict):
            sell_val = insider_summary.get("sell_value", 0)
            buy_val  = insider_summary.get("buy_value", 0)
            if sell_val > buy_val and sell_val > 0:
                risks.append(f"Insider selling (${sell_val:,.0f}) exceeds buying — monitor closely")

        # Ensure we always have exactly 3 risks
        generic_risks = [
            f"Market volatility may impact {ticker.split('.')[0]} in the near term",
            "Sector-wide headwinds could affect performance regardless of company fundamentals",
            "Regulatory changes in the operating environment remain a watch item",
            "Currency and macro risks apply given current global conditions",
            "Liquidity and valuation risk at current price levels warrants monitoring",
        ]
        while len(risks) < 3:
            for gr in generic_risks:
                if gr not in risks:
                    risks.append(gr)
                    break

        # ── Build summary paragraph ───────────────────────────────────
        signal_readable = signal.replace("_", " ")
        news_tone = news_data.get("analysis", "")
        tone_word = "positive" if "bullish" in news_tone.lower() else \
                    "negative" if "bearish" in news_tone.lower() else "mixed"

        summary = (
            f"{company_name} ({ticker.split('.')[0]}) has received a Zenith IQ Alpha Score "
            f"of {pct}/100, generating a {signal_readable} signal. "
            f"News sentiment is {tone_word} with {len(headlines)} recent headlines tracked. "
            f"Social sentiment from retail investors is {sent_label}. "
        )
        if rsi_signal:
            summary += f"Technical indicators show RSI is {rsi_signal}. "
        if mock_activity:
            summary += f"Insider activity indicates net {mock_activity}ing pressure. "
        summary += "Investors should review the full agent breakdown before making any decisions."

        return summary, risks[:3]

    def _fallback_summary(self, ticker: str, signal: str, score: float) -> str:
        """Return a minimal summary when Gemini is unavailable."""
        return (
            f"{ticker} received an Alpha Score of {score:.2f}, "
            f"resulting in a {signal} signal. "
            f"Detailed agent analysis is available in the agent_results field."
        )
