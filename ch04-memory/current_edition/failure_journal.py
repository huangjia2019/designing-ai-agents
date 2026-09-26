"""Listings 4.7–4.8: preserve failure evidence and consult candidate lessons."""

from dataclasses import dataclass, field
import json
import time

@dataclass
class FailureEntry:
    context: str           # What the agent was trying to do
    error_type: str        # Exception class or error category
    error_message: str     # The actual error message
    fix: str              # What resolved the error
    candidate_heuristic: str  # Proposed lesson; not yet admitted
    tags: list[str]       # Semantic tags for retrieval
    timestamp: float = field(default_factory=time.time)

class FailureJournal:
    """Append-only failure evidence with candidate retrieval."""

    def __init__(self, llm, vector_db, journal_path: str):
        self.llm = llm
        self.vector_db = vector_db
        self.path = journal_path

    def record(self, context: str, error: str,
               fix: str) -> FailureEntry:
        """Record failure evidence and propose a candidate lesson."""
        candidate_heuristic = self.llm.generate(
            f"Agent encountered this error:\n"
            f"Context: {context}\nError: {error}\nFix: {fix}\n\n"
            f"Propose a candidate heuristic, a possible lesson "
            f"for similar situations. One to two sentences."
        )
        entry = FailureEntry(
            context=context,
            error_type=self._classify(error),
            error_message=error, fix=fix,
            candidate_heuristic=candidate_heuristic,
            tags=self._auto_tag(context, error),
        )
        self._append(entry)
        self.vector_db.upsert(
            text=f"{context} | {error} | {candidate_heuristic}",
            metadata={"fix": fix, "tags": entry.tags},
        )
        return entry
    def consult_candidates(self, current_context: str,
                min_score: float, k: int = 3):
        """Return similar candidates for review, not admitted advice."""
        results = self.vector_db.search(current_context, top_k=k)
        return [self._to_entry(r) for r in results
                if r.score > min_score]

    def _append(self, entry: FailureEntry) -> None:
        """Append-only—never overwrite the journal."""
        with open(self.path, "a") as f:
            f.write(json.dumps({
                "context": entry.context,
                "error_type": entry.error_type,
                "error_message": entry.error_message,
                "fix": entry.fix,
                "candidate_heuristic": entry.candidate_heuristic,
                "tags": entry.tags,
                "timestamp": entry.timestamp,
            }) + "\n")

    def _classify(self, error: str) -> str:
        for prefix in ["TypeError", "ValueError", "ImportError",
                       "ModuleNotFoundError", "KeyError",
                       "FileNotFoundError", "TimeoutError"]:
            if prefix in error:
                return prefix
        return "UnclassifiedError"

    def _auto_tag(self, context: str, error: str) -> list[str]:
        return self.llm.generate(
            f"Generate 3-5 short tags for:\n"
            f"Context: {context}\nError: {error}\n"
            f"Comma-separated tags only."
        ).split(",")

    def _to_entry(self, result) -> FailureEntry:
        parts = result.text.split(" | ")
        return FailureEntry(
            context=parts[0] if len(parts) > 0 else "",
            error_type="retrieved",
            error_message=parts[1] if len(parts) > 1 else "",
            fix=result.metadata.get("fix", ""),
            candidate_heuristic=parts[-1],
            tags=result.metadata.get("tags", []),
        )
