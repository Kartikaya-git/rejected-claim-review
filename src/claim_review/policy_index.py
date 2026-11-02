import re
from dataclasses import dataclass

from claim_review.documents import PAGE_BREAK

MAX_CLAUSE_CHARS = 2000
MIN_CLAUSE_CHARS = 25

HEADING = re.compile(
    r"^[ \t]*(?:"
    r"(?P<def>Def\.?\s*\d{1,3})\.?"
    r"|(?P<num>\d{1,2}(?:\.\d{1,3}){0,3})\.?(?=\s+[A-Z(])"
    r"|(?P<letter>[IVXL]{2,7}|[A-Z]{1,2})\.(?=\s+[A-Z])"
    r")",
    re.MULTILINE,
)
CODE = re.compile(r"excl\s?-?\s?(\d{2})", re.IGNORECASE)
CONTENTS_LINE = re.compile(r"\.{4,}")


def normalise_code(text: str) -> str | None:
    match = CODE.search(text)
    return f"excl{match.group(1)}" if match else None


@dataclass(frozen=True)
class Clause:
    id: str
    text: str
    page: int
    codes: tuple[str, ...] = ()


class PolicyIndex:
    def __init__(self, clauses: list[Clause]):
        self.clauses = clauses

    def by_id(self, clause_id: str) -> Clause | None:
        wanted = clause_id.strip().rstrip(".").lower()
        return next((c for c in self.clauses if c.id.lower() == wanted), None)

    def by_code(self, code: str) -> Clause | None:
        wanted = normalise_code(code)
        return next((c for c in self.clauses if wanted in c.codes), None)


def _parts(text: str) -> list[str]:
    if len(text) <= MAX_CLAUSE_CHARS:
        return [text]
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.;:])\s+", text):
        if current and len(current) + len(sentence) + 1 > MAX_CLAUSE_CHARS:
            parts.append(current)
            current = ""
        current = f"{current} {sentence}".strip()[: MAX_CLAUSE_CHARS * 2]
    return parts + [current] if current else parts


def build_index(text: str) -> PolicyIndex:
    lines = [line for line in text.split("\n") if not CONTENTS_LINE.search(line)]
    body = "\n".join(lines)
    marks = [m for m in HEADING.finditer(body)]
    clauses = []
    for number, mark in enumerate(marks):
        end = marks[number + 1].start() if number + 1 < len(marks) else len(body)
        raw = body[mark.start():end]
        if len(raw.strip()) < MIN_CLAUSE_CHARS:
            continue
        label = re.sub(r"\s+", " ", mark.group("def") or mark.group("num") or mark.group("letter"))
        page = body.count(PAGE_BREAK, 0, mark.start()) + 1
        codes = tuple(dict.fromkeys(f"excl{c}" for c in CODE.findall(raw)))
        clauses.extend(Clause(label, part, page, codes) for part in _parts(" ".join(raw.split())))
    return PolicyIndex(clauses)
