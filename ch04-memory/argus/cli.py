# argus/cli.py — End-to-end entry point for Ch4 Argus.
#
# Run:
#     python -m argus.cli <diff-file> --project myapp --repo /path/to/repo
#
# Shows the perception trace AND past-lessons retrieved, side by side with
# the LLM review. By default uses an in-memory dict-backed vector_db stub
# so the demo runs without external infra; pass --vector-db to wire a real
# one (chromadb, faiss, ...).
import argparse
import json
import logging
import sys
from pathlib import Path

from . import review_diff, ArgusMemory


class _Stub:
    """Minimal vector_db compatible with HierarchicalMemory."""
    class _Result:
        def __init__(self, text, score=0.5):
            self.text = text
            self.score = score
    def __init__(self):
        self._items = []
    def upsert(self, *, text, metadata=None):
        self._items.append(self._Result(text, score=(metadata or {}).get("importance", 0.5)))
    def search(self, query, top_k=5):
        terms = [t.lower() for t in str(query).split() if len(t) > 3]
        if not terms:
            return []
        scored = []
        for r in self._items:
            overlap = sum(1 for t in terms if t in r.text.lower())
            if overlap:
                relevance = overlap / len(terms)
                scored.append((relevance, self._Result(r.text, score=relevance)))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="argus", description="Argus Ch4: perception + memory.")
    parser.add_argument("diff_file")
    parser.add_argument("--project", required=True, help="project tag for memory scoping")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--budget", type=int, default=50_000)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    diff_path = Path(args.diff_file)
    if not diff_path.exists():
        print(f"error: diff file not found: {diff_path}", file=sys.stderr)
        return 2
    diff = diff_path.read_text()

    # Lazy-import HierarchicalMemory; depends on patterns/ which uses a vector_db.
    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))

    review, trace = review_diff(
        diff=diff,
        project=args.project,
        memory=memory,
        repo_root=args.repo,
        budget=args.budget,
    )

    print("=== Perception trace ===")
    print(json.dumps({
        "files_discovered": trace.files_discovered,
        "files_selected":   trace.files_selected,
        "selectivity":      round(trace.selectivity, 3),
        "tokens_selected":  trace.tokens_selected,
    }, indent=2))
    print("\n=== Review ===")
    print(json.dumps(review, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
