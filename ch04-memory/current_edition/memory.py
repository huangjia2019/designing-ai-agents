"""Listing 4.4: propose review-memory candidates and retrieve them for review."""

from .hierarchical_memory import HierarchicalMemory

class ArgusMemory:
    """Teaching adapter for review-memory candidates."""

    def __init__(self, memory: HierarchicalMemory):
        self.memory = memory

    def propose_after_review(self, review_summary: str,
                     project: str) -> None:
        """Store a review summary as a candidate for validation."""
        self.memory.add(
            content=f"[{project}] {review_summary}",
            source="reflection_candidate",
            importance=0.8,
        )
        # Candidate remains outside admitted recall.

    def retrieve_candidates_for_review(
            self, project: str,
            diff_summary: str) -> list[str]:
        """Retrieve similar candidates for independent validation."""
        return self.memory.retrieve(
            query=f"Past reviews for {project}: {diff_summary}",
            k=3,
        )
