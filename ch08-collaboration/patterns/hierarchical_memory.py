from dataclasses import dataclass, field
from enum import IntEnum
import time

class MemoryTier(IntEnum):
    WORKING = 1    # Context window
    SESSION = 2    # Current session buffer
    LONGTERM = 3   # Persistent storage

@dataclass
class MemoryEntry:
    content: str
    tier: MemoryTier
    source: str               # "user", "tool", "reflection", "file"
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5   # 0.0 (trivial) to 1.0 (critical)
    token_count: int = 0

class HierarchicalMemory:
    """Three-tier memory with promotion and eviction."""

    def __init__(self, vector_db, working_budget: int = 150_000):
        self.vector_db = vector_db
        self.working_budget = working_budget
        self.working: list[MemoryEntry] = []  #A
        self.session: list[MemoryEntry] = []  #B

    def add(self, content: str, source: str,
            importance: float = 0.5) -> None:  #C
        """Add new information to working memory."""
        entry = MemoryEntry(
            content=content, tier=MemoryTier.WORKING,
            source=source, importance=importance,
            token_count=len(content) // 4,
        )
        self.working.append(entry)
        self._enforce_budget()

    def retrieve(self, query: str, k: int = 5) -> list[str]:
        """Promote relevant long-term  #D
    memories to working."""
        results = self.vector_db.search(query, top_k=k)
        for result in results:
            entry = MemoryEntry(
                content=result.text, tier=MemoryTier.WORKING,
                source="longterm_retrieval",
                importance=result.score,
                token_count=len(result.text) // 4,
            )
            self.working.append(entry)
        self._enforce_budget()
        return [r.text for r in results]

    def _enforce_budget(self) -> None:  #E
        """Evict lowest-priority items when over budget."""
        total = sum(e.token_count for e in self.working)
        if total <= self.working_budget:
            return

        now = time.time()
        for entry in self.working:
            recency = 1.0 / (1.0 + (now - entry.last_accessed) / 3600)
            entry._score = (
                entry.importance * 0.5
                + recency * 0.3
                + min(entry.access_count / 10, 1.0) * 0.2
            )
        self.working.sort(key=lambda e: e._score)

        while total > self.working_budget and self.working:
            evicted = self.working.pop(0)
            evicted.tier = MemoryTier.SESSION
            self.session.append(evicted)
            total -= evicted.token_count

    def consolidate(self) -> None:  #F
        """End-of-session: persist important memories."""
        important = [e for e in self.session + self.working
                     if e.importance > 0.6 or e.source == "reflection"]
        for entry in important:
            self.vector_db.upsert(
                text=entry.content,
                metadata={"source": entry.source,
                          "importance": entry.importance},
            )
