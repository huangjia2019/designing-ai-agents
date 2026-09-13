"""Small deterministic adapters used by the Chapter 4 examples and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class SearchResult:
    """One result returned by the teaching index."""

    text: str
    score: float
    metadata: dict = field(default_factory=dict)


class InMemoryIndex:
    """A deterministic search adapter, not a production vector database."""

    def __init__(self) -> None:
        self._items: list[SearchResult] = []

    def upsert(self, text: str, metadata: dict | None = None) -> None:
        self._items.append(
            SearchResult(text=text, score=0.0, metadata=metadata or {})
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_terms = self._terms(query)
        ranked: list[SearchResult] = []
        for item in self._items:
            item_terms = self._terms(item.text)
            overlap = len(query_terms & item_terms)
            if overlap == 0:
                continue
            union = len(query_terms | item_terms) or 1
            ranked.append(
                SearchResult(
                    text=item.text,
                    score=overlap / union,
                    metadata=dict(item.metadata),
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.text))
        return ranked[:top_k]

    @staticmethod
    def _terms(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9_]+", text.lower()))
