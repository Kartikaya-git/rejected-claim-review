import hashlib
import json
import math
import re
from pathlib import Path
from typing import Protocol

from rank_bm25 import BM25Okapi

from claim_review.models import ChecklistItem
from claim_review.policy_index import Clause, PolicyIndex

RRF_K = 60
SEARCH_DEPTH = 20
MAX_CLAUSES = 4
MAX_TOTAL_CHARS = 4500
MAX_FOLLOWED_REFERENCES = 2
EMBEDDING_CACHE = Path("data/embeddings")

REFERENCE = re.compile(r"\b(?:section|clause|para(?:graph)?|condition|point)\s+([A-Z]?\d{1,2}(?:\.\d{1,3}){0,3})", re.IGNORECASE)
CODE_REFERENCE = re.compile(r"\bexcl\s?-?\s?\d{2}\b", re.IGNORECASE)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    """A small free model that runs on this machine, with results kept on disk."""

    MODEL = "BAAI/bge-small-en-v1.5"

    def __init__(self):
        self._model = None

    def _embed_now(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(self.MODEL)
        return [vector.tolist() for vector in self._model.embed(texts)]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if len(texts) == 1:
            return self._embed_now(texts)
        key = hashlib.sha256(("\n".join(texts) + self.MODEL).encode()).hexdigest()[:24]
        path = EMBEDDING_CACHE / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        vectors = self._embed_now(texts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(vectors))
        return vectors


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0


def reciprocal_rank_fusion(rankings: list[list], k: int = RRF_K) -> list:
    scores: dict = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda key: -scores[key])


class PolicySearch:
    def __init__(self, index: PolicyIndex, embedder: Embedder):
        self.index = index
        self.embedder = embedder
        texts = [clause.text for clause in index.clauses]
        self._bm25 = BM25Okapi([_words(text) for text in texts])
        self._vectors = embedder.embed(texts)

    def keyword_ranking(self, query: str) -> list[int]:
        scores = self._bm25.get_scores(_words(query))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [i for i in order[:SEARCH_DEPTH] if scores[i] != 0]

    def embedding_ranking(self, query: str) -> list[int]:
        target = self.embedder.embed([query])[0]
        scores = [_cosine(vector, target) for vector in self._vectors]
        return sorted(range(len(scores)), key=lambda i: -scores[i])[:SEARCH_DEPTH]

    def hybrid_ranking(self, keyword_query: str, semantic_query: str | None = None) -> list[int]:
        return reciprocal_rank_fusion(
            [self.keyword_ranking(keyword_query), self.embedding_ranking(semantic_query or keyword_query)]
        )

    def _exact(self, item: ChecklistItem, letter: str) -> list[Clause]:
        found = [self.index.by_code(code) for code in item.codes]
        found += [self.index.by_code(code) for code in CODE_REFERENCE.findall(letter)]
        found += [self.index.by_id(ref) for ref in REFERENCE.findall(letter)]
        return [clause for clause in found if clause]

    def _followed(self, clauses: list[Clause]) -> list[Clause]:
        references = [ref for clause in clauses for ref in REFERENCE.findall(clause.text)]
        found = [self.index.by_id(ref) for ref in references]
        return [clause for clause in found if clause][:MAX_FOLLOWED_REFERENCES]

    def find(
        self,
        item: ChecklistItem,
        letter: str = "",
        refinement: str = "",
        query: str | None = None,
        exclude: tuple[Clause, ...] = (),
    ) -> list[Clause]:
        """Exact references first, then what they point to, then the best search results."""
        semantic = query or f"{item.search_query or item.question} {refinement}".strip()
        keywords = query or f"{item.keywords or item.search_query or item.question} {refinement}".strip()
        exact = [] if query else self._exact(item, letter)
        ranked = [self.index.clauses[i] for i in self.hybrid_ranking(keywords, semantic)]
        selected: list[Clause] = []
        total = 0
        for clause in exact + self._followed(exact) + ranked:
            if clause in selected or clause in exclude or len(selected) == MAX_CLAUSES:
                continue
            if total + len(clause.text) > MAX_TOTAL_CHARS:
                continue
            selected.append(clause)
            total += len(clause.text)
        return selected
