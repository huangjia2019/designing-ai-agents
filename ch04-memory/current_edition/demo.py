"""Exercise candidate retention and JSON resumption without model calls."""
from pathlib import Path
import json
import tempfile

from . import ArgusMemory, FailureJournal, HierarchicalMemory
from . import InMemoryIndex, ProgressTracker


class FixedModel:
    def generate(self, prompt):
        if "Generate 3-5 short tags" in prompt:
            return "python,dependency,import"
        return "Check which distribution owns an unexpected import."


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        index = InMemoryIndex()
        memory = HierarchicalMemory(index)
        first = ArgusMemory(memory)
        first.propose_after_review(
            "pyjwt owns the expected JWT import", "example-api"
        )
        before_storage = len(index._items)
        # Retention is a separate host decision, not admission as a rule.
        memory.consolidate()

        progress = ProgressTracker(str(root / "progress.json"))
        progress.create_plan(["inspect dependency", "review proposed fix"])
        progress.complete(0, "distribution checked", ["pyproject.toml"])
        later_progress = ProgressTracker(str(root / "progress.json"))

        failures = InMemoryIndex()  # Dedicated candidate index.
        journal = FailureJournal(FixedModel(), failures, str(root / "failures.jsonl"))
        journal.record(
            "unexpected jwt import", "ImportError: unexpected distribution",
            "inspect package metadata",
        )
        later = ArgusMemory(HierarchicalMemory(index))
        candidates = journal.consult_candidates("jwt import distribution", 0.0)
        print(json.dumps({
            "stored_before_explicit_consolidation": before_storage,
            "review_candidates": later.retrieve_candidates_for_review(
                "example-api", "jwt import"
            ),
            "checkpoint": later_progress.resumption_context(),
            "failure_candidates": [entry.candidate_heuristic for entry in candidates],
            "admission": "A separate validation and authority decision is still required.",
        }, indent=2))


if __name__ == "__main__":
    main()
