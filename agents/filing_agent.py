"""
Filing Agent
------------
Fetches SEC EDGAR filings (10-K / 10-Q) for a ticker,
extracts key management statements, embeds them, and stores
vectors in Supabase for semantic retrieval.
"""

import re
import requests
from typing import Any

from agents.base_agent import BaseAgent, AgentResult
from data_pipeline import load_pdf, extract_section, PDFDocument
from services.supabase_service import upsert_filing_chunks, search_filing_chunks
from services.gemini_service import query_gemini
from config import settings


SEC_SEARCH_URL = (
    "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
    "&forms=10-K,10-Q&dateRange=custom&startdt={start}&enddt={end}"
)
SEC_FILING_BASE = "https://www.sec.gov"

# EDGAR company search — used to resolve CIK from ticker
EDGAR_COMPANY_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_TICKER_URL  = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={ticker}&type=10-K&dateb=&owner=include&count=5&search_text=&output=atom"


class FilingAgent(BaseAgent):
    """
    Retrieves and analyses SEC filings for a given ticker.

    Workflow:
        1. Query EDGAR full-text search for recent 10-K / 10-Q filings.
        2. Download the filing document text.
        3. Chunk the text and store embeddings in Supabase.
        4. Run a semantic search for risk-related passages.
        5. Ask Gemini to summarise the key risk signals.
    """

    RISK_KEYWORDS = [
        "risk factor", "going concern", "material weakness",
        "litigation", "regulatory", "impairment", "liquidity",
    ]

    def __init__(self):
        super().__init__("FilingAgent")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Analyse SEC filings for `ticker`.

        Args:
            ticker:     Stock ticker symbol.
            pdf_path:   Optional local PDF path — skips EDGAR download.
            start_date: Optional YYYY-MM-DD start for EDGAR search.
            end_date:   Optional YYYY-MM-DD end for EDGAR search.

        Returns:
            AgentResult with risk summary and a 0–1 risk score.
        """
        start = kwargs.get("start_date", "2023-01-01")
        end = kwargs.get("end_date", "2025-12-31")
        pdf_path = kwargs.get("pdf_path")

        try:
            # --- Local PDF path takes priority over EDGAR download ---
            if pdf_path:
                doc: PDFDocument = load_pdf(pdf_path)
                text = doc.full_text
                chunks = doc.chunks(size=800, overlap=100)
                form_type = "PDF"
                filing_date = doc.metadata.get("creation_date", "unknown")
            else:
                filings = self._fetch_filing_list(ticker, start, end)
                if not filings:
                    return AgentResult(self.name, {"message": "No filings found on EDGAR"}, score=0.5)
                latest = filings[0]
                text = self._download_filing_text(latest["url"])
                if not text:
                    return AgentResult(self.name, {"message": "Filing download failed"}, score=0.5)
                chunks = self._chunk_text(text)
                form_type = latest["form"]
                filing_date = latest["date"]

            # Persist chunks to Supabase vector store
            upsert_filing_chunks(ticker, chunks, form_type, filing_date)

            # Semantic search for risk passages
            risk_passages = search_filing_chunks(ticker, query="risk factors material weakness")

            # Gemini summarisation
            summary = await self._summarise_risks(ticker, risk_passages)
            risk_score = self._score_risks(risk_passages)

            return AgentResult(
                self.name,
                {
                    "filing_date": filing_date,
                    "form_type": form_type,
                    "risk_passages": risk_passages[:3],
                    "summary": summary,
                },
                score=risk_score,
            )

        except Exception as exc:
            self.logger.error(f"FilingAgent failed for {ticker}: {exc}")
            return AgentResult(self.name, {}, score=0.5, error=str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_filing_list(self, ticker: str, start: str, end: str) -> list[dict]:
        """
        Query SEC EDGAR full-text search and return filing metadata.

        Uses the EDGAR full-text search API which returns hits with
        _source fields: entity_name, file_date, form_type, period_of_report,
        and a document_url pointing to the actual filing index.

        Args:
            ticker: Ticker symbol.
            start:  Start date YYYY-MM-DD.
            end:    End date YYYY-MM-DD.

        Returns:
            List of dicts with keys: url, form, date.
            Returns empty list on any network or parse error.
        """
        try:
            url = SEC_SEARCH_URL.format(ticker=ticker, start=start, end=end)
            resp = requests.get(
                url,
                headers={"User-Agent": "zenithiq research@zenithiq.ai"},
                timeout=15,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])
        except Exception as exc:
            self.logger.warning(f"EDGAR search failed for {ticker}: {exc}")
            return []

        results = []
        for hit in hits:
            src = hit.get("_source", {})

            # The correct field for the filing document URL
            doc_url = src.get("file_date", "")   # this is actually a date, not a URL
            period  = src.get("period_of_report", "")
            form    = src.get("form_type", "")
            date    = src.get("file_date", "")

            # Build the actual filing index URL from entity_id and accession_number
            entity_id  = src.get("entity_id", "")
            accession  = hit.get("_id", "").replace("-", "")

            if entity_id and accession:
                # Standard EDGAR filing index URL format
                filing_url = (
                    f"{SEC_FILING_BASE}/Archives/edgar/data/"
                    f"{entity_id}/{accession[:18].replace('-','')}-index.htm"
                )
            else:
                # Fallback: skip this hit if we can't build a valid URL
                continue

            results.append({
                "url":  filing_url,
                "form": form,
                "date": date or period,
            })

        return results

    def _download_filing_text(self, url: str) -> str:
        """
        Download and return plain text from a filing URL.

        Args:
            url: Direct URL to the filing document.

        Returns:
            Raw text content (HTML tags stripped), or empty string on failure.
        """
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "zenithiq research@zenithiq.ai"},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:
            self.logger.warning(f"Could not download filing from {url}: {exc}")
            return ""

        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
        """
        Split text into overlapping chunks for embedding.

        Args:
            text:       Full document text.
            chunk_size: Characters per chunk.
            overlap:    Overlap between consecutive chunks.

        Returns:
            List of text chunks.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _score_risks(self, passages: list[str]) -> float:
        """
        Heuristic risk score based on keyword density in retrieved passages.

        Returns:
            Float between 0.0 (low risk) and 1.0 (high risk).
        """
        if not passages:
            return 0.5
        combined = " ".join(passages).lower()
        hits = sum(combined.count(kw) for kw in self.RISK_KEYWORDS)
        # Normalise: cap at 20 keyword hits → score 1.0
        return min(hits / 20.0, 1.0)

    async def _summarise_risks(self, ticker: str, passages: list[str]) -> str:
        """
        Use Gemini to produce a concise risk summary from retrieved passages.

        Args:
            ticker:   Ticker symbol for context.
            passages: List of risk-related text passages.

        Returns:
            Gemini-generated summary string.
        """
        if not passages:
            return "No risk passages found."
        context = "\n\n".join(passages[:5])
        prompt = (
            f"You are a financial risk analyst. Based on the following excerpts from "
            f"{ticker}'s SEC filing, identify the top 3 hidden risks in 3 bullet points. "
            f"Be concise and specific.\n\n{context}"
        )
        return await query_gemini(prompt)
