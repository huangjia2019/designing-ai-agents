# argus/cli.py — End-to-end entry point for Ch5 Argus.
import argparse, json, logging, sys
from pathlib import Path

from . import review_diff, ArgusMemory, ArgusReasoning


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
        scored = sorted(
            ((sum(1 for t in terms if t in r.text.lower()), r) for r in self._items),
            key=lambda x: -x[0],
        )
        return [r for s, r in scored[:top_k] if s > 0]

def main(argv=None):
    p = argparse.ArgumentParser(prog="argus", description="Argus Ch5: + complexity-routed reasoning.")
    p.add_argument("diff_file")
    p.add_argument("--project", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("--budget", type=int, default=50_000)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    diff_path = Path(args.diff_file)
    if not diff_path.exists():
        print(f"error: diff file not found: {diff_path}", file=sys.stderr); return 2

    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))
    reasoning = ArgusReasoning()

    result, p_trace = review_diff(
        diff=diff_path.read_text(),
        project=args.project,
        memory=memory,
        reasoning=reasoning,
        repo_root=args.repo,
        budget=args.budget,
    )

    print("=== Perception ===")
    print(json.dumps({
        "files_discovered": p_trace.files_discovered,
        "files_selected":   p_trace.files_selected,
        "selectivity":      round(p_trace.selectivity, 3),
    }, indent=2))
    print(f"\n=== Reasoning ({result.complexity}, conf={result.confidence:.2f}) ===")
    print(result.verdict)
    if result.reasoning_steps:
        print(f"\n=== Chain ({len(result.reasoning_steps)} steps) ===")
        for s in result.reasoning_steps:
            print(f"  step{s.step_number} [conf={s.confidence:.2f}]: {s.content[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
