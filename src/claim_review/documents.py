import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

MIN_CHARS_PER_PAGE = 20
PAGE_BREAK = "\f"


@dataclass(frozen=True)
class ReadDocument:
    text: str
    readable: bool


def read_pdf(path: Path) -> ReadDocument:
    """Reads a text PDF, keeping page breaks. Scanned or broken files are reported, not guessed at."""
    try:
        pages = [page.extract_text() or "" for page in PdfReader(path).pages]
    except Exception:
        return ReadDocument("", False)
    text = PAGE_BREAK.join(unicodedata.normalize("NFKC", page) for page in pages)
    if len(text.strip()) < MIN_CHARS_PER_PAGE * max(len(pages), 1):
        return ReadDocument("", False)
    return ReadDocument(text, True)
