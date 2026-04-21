from dataclasses import dataclass, field
import json
import time

@dataclass
class FailureEntry:
    context: str           # What the agent was trying to do
    error_type: str        # Exception class or error category
    error_message: str     # The actual error message
    fix: str              # What resolved the error
    heuristic: str        # Transferable lesson (high-level)
    tags: list[str]       # Semantic tags for retrieval
    timestamp: float = field(default_factory=time.time)

class FailureJournal:
    """Append-only failure log with semantic retrieval."""

    def __init__(self, llm, vector_db, journal_path: str):
        self.llm = llm
        self.vector_db = vector_db
        self.path = journal_path

    def record(self, context: str, error: str,
               fix: str) -> FailureEntry:  #A
        """Record a failure with auto-generated heuristic."""
        heuristic = self.llm.generate(
            f"Agent encountered this error:\n"
            f"Context: {context}\nError: {error}\nFix: {fix}\n\n"
            f"Extract a transferable heuristic, a general lesson "
            f"for similar situations. One to two sentences."
        )
        entry = FailureEntry(
            context=context,
            error_type=self._classify(error),
            error_message=error, fix=fix,
            heuristic=heuristic,
            tags=self._auto_tag(context, error),
        )
        self._append(entry)  #B
        self.vector_db.upsert(
            text=f"{context} | {error} | {heuristic}",
            metadata={"fix": fix, "tags": entry.tags},
        )
        return entry

    def consult(self, current_context: str,
                k: int = 3) -> list[FailureEntry]:  #C
        """Before acting, check if similar failures have occurred."""
        results = self.vector_db.search(current_context, top_k=k)
        return [self._to_entry(r) for r in results
                if r.score > 0.7]

    def _append(self, entry: FailureEntry) -> None:
        """Append-only—never overwrite the journal."""
        with open(self.path, "a") as f:
            f.write(json.dumps({
                "context": entry.context,
                "error_type": entry.error_type,
                "error_message": entry.error_message,
                "fix": entry.fix,
                "heuristic": entry.heuristic,
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
            heuristic=parts[-1],
            tags=result.metadata.get("tags", []),
        )
