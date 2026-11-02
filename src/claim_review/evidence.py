import re
import unicodedata
from datetime import date, datetime

MONTH_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "nine": 9,
    "twelve": 12, "eighteen": 18, "twenty four": 24, "twenty-four": 24,
    "thirty": 30, "thirty six": 36, "thirty-six": 36, "forty eight": 48, "forty-eight": 48,
}
DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d.%m.%y", "%d-%m-%y", "%Y-%m-%d")
DATE_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9},?\s+\d{4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
)


def _normalise(text: str) -> str:
    """PDF extraction splits and joins words, so spaces are ignored. Every other character must match."""
    return "".join(unicodedata.normalize("NFKC", text).split())


def quote_in_source(quote: str | None, source_text: str) -> bool:
    """A quote shortened with dots passes only if each part appears, in order, in the source."""
    if not quote or not quote.strip():
        return False
    parts = [_normalise(part) for part in re.split(r"\.{3,}|\u2026", quote)]
    parts = [part for part in parts if part]
    source = _normalise(source_text)
    position = 0
    for part in parts:
        position = source.find(part, position)
        if position < 0:
            return False
        position += len(part)
    return bool(parts)


def dates_in(text: str) -> set[date]:
    found = set()
    for match in DATE_PATTERN.findall(text):
        cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)", "", match).replace(",", "")
        for fmt in DATE_FORMATS:
            try:
                found.add(datetime.strptime(cleaned, fmt).date())
                break
            except ValueError:
                continue
    return found


def months_in(text: str) -> set[int]:
    lowered = text.lower()
    found = set()
    for number, unit in re.findall(r"(\d+)\)?[\s-]*(month|year)", lowered):
        found.add(int(number) * (12 if unit == "year" else 1))
    for number in re.findall(r"(\d+)\)?[\s-]*day", lowered):
        if int(number) % 30 == 0:
            found.add(int(number) // 30)
    for word, number in MONTH_WORDS.items():
        for unit in re.findall(rf"\b{word}\b(?:\s*\(\d+\))?[\s-]*(month|year)", lowered):
            found.add(number * (12 if unit == "year" else 1))
    return found
