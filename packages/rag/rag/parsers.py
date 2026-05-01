"""Document parsers for ingestion.

Each parser yields `(text, page_num)` tuples so chunk metadata can carry
the originating page for citation. Markdown reports `page_num=None`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def parse_markdown_file(path: str | Path) -> Iterator[tuple[str, int | None]]:
    """Yield a single (text, None) — markdown is one logical "page"."""
    p = Path(path)
    yield p.read_text(encoding="utf-8"), None


def parse_pdf_file(path: str | Path) -> Iterator[tuple[str, int]]:
    """Yield (page_text, 1-indexed page_num) for each page in the PDF.

    pdfplumber preferred; falls back to PyPDF2 if pdfplumber bails on
    a page (e.g. scanned image with no text layer — that should route to
    OCR, deferred to milestone 8).
    """
    try:
        import pdfplumber  # type: ignore[import-untyped]

        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    yield text, i + 1
                    continue
                # Empty extraction — try PyPDF2 fallback for this page only.
                yield _pypdf2_page(path, i), i + 1
    except ImportError:
        # pdfplumber not installed — fall back to PyPDF2 for the whole file.
        for i, text in enumerate(_pypdf2_all(path)):
            yield text, i + 1


def _pypdf2_all(path: str | Path) -> list[str]:
    from PyPDF2 import PdfReader  # type: ignore[import-untyped]

    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def _pypdf2_page(path: str | Path, index: int) -> str:
    from PyPDF2 import PdfReader  # type: ignore[import-untyped]

    reader = PdfReader(str(path))
    if index >= len(reader.pages):
        return ""
    return reader.pages[index].extract_text() or ""
