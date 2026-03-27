"""
Data Pipeline — Shared Output Models
-------------------------------------
Typed dataclasses that define the clean structured output
every pipeline module delivers to agents.

All agents import from here — never from the fetcher modules directly —
so the contract between pipeline and agents is explicit and versioned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class OHLCVBar:
    """Single OHLCV candlestick bar."""
    date:   str
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float


@dataclass
class StockSnapshot:
    """
    Full structured output of the stock fetcher.
    Consumed by: QuantAgent, CoordinatorAgent.
    """
    ticker:          str
    company_name:    str
    sector:          str
    industry:        str
    market_cap:      float | None
    pe_ratio:        float | None
    eps:             float | None
    dividend_yield:  float | None
    fifty_two_week_high: float | None
    fifty_two_week_low:  float | None
    latest_close:    float | None
    bars:            list[OHLCVBar] = field(default_factory=list)
    fetched_at:      str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "ticker":              self.ticker,
            "company_name":        self.company_name,
            "sector":              self.sector,
            "industry":            self.industry,
            "market_cap":          self.market_cap,
            "pe_ratio":            self.pe_ratio,
            "eps":                 self.eps,
            "dividend_yield":      self.dividend_yield,
            "52w_high":            self.fifty_two_week_high,
            "52w_low":             self.fifty_two_week_low,
            "latest_close":        self.latest_close,
            "bar_count":           len(self.bars),
            "bars":                [b.__dict__ for b in self.bars],
            "fetched_at":          self.fetched_at,
        }


@dataclass
class NewsArticle:
    """Single scraped news article."""
    title:       str
    url:         str
    source:      str
    published:   str          # ISO date string or raw date text
    summary:     str = ""     # first paragraph / meta description
    full_text:   str = ""     # body text if scraped


@dataclass
class NewsBundle:
    """
    Structured output of the news scraper.
    Consumed by: NewsAgent, FilingAgent (context enrichment).
    """
    ticker:      str
    query:       str
    articles:    list[NewsArticle] = field(default_factory=list)
    scraped_at:  str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def headlines(self) -> list[str]:
        return [a.title for a in self.articles]

    @property
    def full_texts(self) -> list[str]:
        return [a.full_text or a.summary for a in self.articles if a.full_text or a.summary]

    def to_dict(self) -> dict:
        return {
            "ticker":     self.ticker,
            "query":      self.query,
            "count":      len(self.articles),
            "scraped_at": self.scraped_at,
            "articles": [
                {
                    "title":     a.title,
                    "url":       a.url,
                    "source":    a.source,
                    "published": a.published,
                    "summary":   a.summary,
                }
                for a in self.articles
            ],
        }


@dataclass
class PDFPage:
    """Text content of a single PDF page."""
    page_number: int
    text:        str
    char_count:  int


@dataclass
class PDFDocument:
    """
    Structured output of the PDF loader.
    Consumed by: FilingAgent (local PDF filings).
    """
    source_path:  str
    total_pages:  int
    pages:        list[PDFPage] = field(default_factory=list)
    metadata:     dict         = field(default_factory=dict)
    loaded_at:    str          = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def full_text(self) -> str:
        """Concatenated text of all pages."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    def chunks(self, size: int = 800, overlap: int = 100) -> list[str]:
        """
        Split full_text into overlapping chunks for embedding.

        Args:
            size:    Characters per chunk.
            overlap: Overlap between consecutive chunks.

        Returns:
            List of text chunk strings.
        """
        text = self.full_text
        result = []
        start = 0
        while start < len(text):
            result.append(text[start: start + size])
            start += size - overlap
        return result

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "total_pages": self.total_pages,
            "char_count":  len(self.full_text),
            "metadata":    self.metadata,
            "loaded_at":   self.loaded_at,
        }
