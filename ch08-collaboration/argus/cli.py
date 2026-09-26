# argus/cli.py — End-to-end entry point for Ch6 Argus.
import argparse, json, sys
from pathlib import Path

from . import review_diff, ArgusMemory, ArgusReasoning, ArgusAction


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
    p = argparse.ArgumentParser(prog="argus", description="Argus Ch6: + tool-grounded action.")
    p.add_argument("diff_file")
    p.add_argument("--project", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("--no-verify", action="store_true", help="skip running tools, prove gate alone")
    args = p.parse_args(argv)

    diff = Path(args.diff_file).read_text()

    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))
    action = ArgusAction()

    result, p_trace, action_log = review_diff(
        diff=diff, project=args.project, memory=memory,
        reasoning=ArgusReasoning(), action=action,
        repo_root=args.repo,
        verify_with_tools=not args.no_verify,
    )

    print(f"=== Reasoning ({result.complexity}, conf={result.confidence:.2f}) ===")
    print(result.verdict[:1000])
    print(f"\n=== Action log ({len(action_log)} action(s)) ===")
    for a in action_log:
        flag = "BLOCKED" if a.guardrail_blocked else ("ERROR" if a.error else "OK")
        print(f"  [{flag:7}] {a.tool_name} {a.wall_time_ms:.0f}ms"
              + (f"  reason={a.guardrail_reason}" if a.guardrail_reason else "")
              + (f"  error={a.error}" if a.error else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
