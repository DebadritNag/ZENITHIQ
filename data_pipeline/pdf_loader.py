"""
PDF Loader
----------
Extracts structured text from PDF files using PyMuPDF (fitz).

Handles:
    - Multi-page documents
    - Scanned PDFs (basic heuristic detection)
    - Table-heavy filings (preserves whitespace layout)
    - Metadata extraction (title, author, creation date)

Returns a clean PDFDocument dataclass ready for chunking and embedding.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import fitz  # PyMuPDF

from data_pipeline.models import PDFDocument, PDFPage

logger = logging.getLogger(__name__)

# Pages with fewer characters than this are likely scanned images
_SCANNED_PAGE_THRESHOLD = 50


def load_pdf(path: str | Path) -> PDFDocument:
    """
    Load a PDF file and extract text from every page.

    Args:
        path: Absolute or relative path to the PDF file.

    Returns:
        PDFDocument with per-page text, metadata, and helper methods
        for full-text access and chunking.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the file is not a valid PDF.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

    doc = fitz.open(str(path))
    metadata = _extract_metadata(doc)
    pages = _extract_pages(doc)
    doc.close()

    scanned_count = sum(1 for p in pages if p.char_count < _SCANNED_PAGE_THRESHOLD)
    if scanned_count > len(pages) * 0.5:
        logger.warning(
            f"{path.name}: {scanned_count}/{len(pages)} pages appear scanned "
            f"(< {_SCANNED_PAGE_THRESHOLD} chars). OCR not applied."
        )

    logger.info(f"Loaded {path.name}: {len(pages)} pages, {sum(p.char_count for p in pages):,} chars")

    return PDFDocument(
        source_path = str(path),
        total_pages = len(pages),
        pages       = pages,
        metadata    = metadata,
    )


def load_pdfs_from_dir(directory: str | Path, recursive: bool = False) -> list[PDFDocument]:
    """
    Load all PDF files from a directory.

    Args:
        directory: Path to the directory containing PDFs.
        recursive: If True, also search subdirectories.

    Returns:
        List of PDFDocument objects, one per successfully loaded file.
        Files that fail to load are logged and skipped.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_paths = sorted(directory.glob(pattern))

    if not pdf_paths:
        logger.warning(f"No PDF files found in {directory}")
        return []

    documents = []
    for pdf_path in pdf_paths:
        try:
            documents.append(load_pdf(pdf_path))
        except Exception as exc:
            logger.error(f"Failed to load {pdf_path.name}: {exc}")

    return documents


def extract_section(doc: PDFDocument, keyword: str, window: int = 3000) -> str:
    """
    Extract a text window around the first occurrence of a keyword.

    Useful for pulling specific sections like "Risk Factors" or
    "Management Discussion" from long filings.

    Args:
        doc:     Loaded PDFDocument.
        keyword: Case-insensitive search term.
        window:  Number of characters to return after the keyword match.

    Returns:
        Extracted text window, or empty string if keyword not found.
    """
    full = doc.full_text
    idx = full.lower().find(keyword.lower())
    if idx == -1:
        return ""
    return full[idx: idx + window].strip()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_pages(doc: fitz.Document) -> list[PDFPage]:
    """
    Extract text from every page of an open fitz Document.

    Uses 'blocks' layout to preserve paragraph structure better than
    the default plain text extraction.

    Args:
        doc: Open fitz.Document object.

    Returns:
        List of PDFPage objects in page order.
    """
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = _clean_page_text(page.get_text("text"))
        pages.append(PDFPage(
            page_number = page_num + 1,
            text        = text,
            char_count  = len(text),
        ))
    return pages


def _clean_page_text(raw: str) -> str:
    """
    Normalise extracted page text.

    - Collapse runs of 3+ blank lines to a single blank line
    - Strip leading/trailing whitespace per line
    - Remove form-feed characters

    Args:
        raw: Raw text string from fitz.

    Returns:
        Cleaned text string.
    """
    import re
    raw = raw.replace("\f", "\n")
    lines = [line.rstrip() for line in raw.splitlines()]
    # Collapse consecutive blank lines
    cleaned_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                cleaned_lines.append(line)
        else:
            blank_run = 0
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _extract_metadata(doc: fitz.Document) -> dict:
    """
    Extract PDF metadata fields.

    Args:
        doc: Open fitz.Document object.

    Returns:
        Dict with title, author, subject, creator, creation_date, page_count.
    """
    meta = doc.metadata or {}
    return {
        "title":         meta.get("title", ""),
        "author":        meta.get("author", ""),
        "subject":       meta.get("subject", ""),
        "creator":       meta.get("creator", ""),
        "creation_date": meta.get("creationDate", ""),
        "page_count":    len(doc),
    }
