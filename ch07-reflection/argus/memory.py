from patterns.hierarchical_memory import HierarchicalMemory

class ArgusMemory:
    """Cross-session memory for the Argus code reviewer."""

    def __init__(self, memory: HierarchicalMemory):
        self.memory = memory

    def after_review(self, review_summary: str,
                     project: str) -> None:  #A
        """Persist review findings for future sessions."""
        self.memory.add(
            content=f"[{project}] {review_summary}",
            source="reflection",
            importance=0.8,
        )
        self.memory.consolidate()

    def before_review(  #B
            self, project: str,
            diff_summary: str) -> list[str]:
        """Retrieve relevant past findings before starting."""
        return self.memory.retrieve(
            query=f"Past reviews for {project}: {diff_summary}",
            k=3,
        )
