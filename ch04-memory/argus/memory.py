# argus/memory.py — Chapter 4 addition
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patterns.hierarchical_memory import HierarchicalMemory


class ArgusMemory:
    """Cross-session memory for the Argus code reviewer."""

    def __init__(self, memory: "HierarchicalMemory"):
        self.memory = memory

    def after_review(self, review_summary: str,
                     project: str) -> None:
        """Persist review findings for future sessions."""
        self.memory.add(
            content=f"[{project}] {review_summary}",
            source="reflection",
            importance=0.8,
        )
        self.memory.consolidate()

    def before_review(
            self, project: str,
            diff_summary: str) -> list[str]:
        """Retrieve relevant past findings before starting."""
        return self.memory.retrieve(
            query=f"Past reviews for {project}: {diff_summary}",
            k=3,
        )
