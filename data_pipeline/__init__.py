"""
data_pipeline
=============
Public API for the Zenith IQ data pipeline.

Agents import from here — never from submodules directly.

    from data_pipeline import fetch_stock_snapshot, scrape_news, load_pdf
    from data_pipeline import StockSnapshot, NewsBundle, PDFDocument

Quick usage
-----------
    # Stock data
    snapshot = fetch_stock_snapshot("AAPL", period="6mo")
    print(snapshot.latest_close, snapshot.pe_ratio)
    df_bars = snapshot.bars  # list[OHLCVBar]

    # News
    bundle = scrape_news("AAPL", max_articles=20)
    print(bundle.headlines)
    print(bundle.full_texts)

    # PDF filing
    doc = load_pdf("filings/aapl_10k.pdf")
    risk_section = extract_section(doc, "Risk Factors")
    chunks = doc.chunks(size=800, overlap=100)
"""

from data_pipeline.stock_fetcher import fetch_stock_snapshot, fetch_stock_info
from data_pipeline.news_scraper  import scrape_news, scrape_article_text
from data_pipeline.pdf_loader    import load_pdf, load_pdfs_from_dir, extract_section
from data_pipeline.models        import (
    OHLCVBar,
    StockSnapshot,
    NewsArticle,
    NewsBundle,
    PDFPage,
    PDFDocument,
)

__all__ = [
    # Fetchers
    "fetch_stock_snapshot",
    "fetch_stock_info",
    "scrape_news",
    "scrape_article_text",
    "load_pdf",
    "load_pdfs_from_dir",
    "extract_section",
    # Models
    "OHLCVBar",
    "StockSnapshot",
    "NewsArticle",
    "NewsBundle",
    "PDFPage",
    "PDFDocument",
]
