# argus/cli.py — End-to-end entry point for the Ch10 capstone Argus.
#
# Run:
#     python -m argus.cli <diff-file> --project myapp --repo /path/to/repo
#
# Outputs the orchestration result with every trace visible: perception
# selectivity, action log, reflection convergence, collaboration meta,
# governance audit + trust.
import argparse, json, sys
from pathlib import Path

from . import ArgusOrchestrator, ArgusMemory


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
    p = argparse.ArgumentParser(prog="argus", description="Argus Ch10 capstone orchestrator.")
    p.add_argument("diff_file")
    p.add_argument("--project", required=True)
    p.add_argument("--repo", default=".")
    p.add_argument("--no-tools", action="store_true",
                   help="skip running lint/tests; useful for offline demos")
    p.add_argument("--no-refine", action="store_true",
                   help="skip the reflection critic loop")
    args = p.parse_args(argv)

    diff = Path(args.diff_file).read_text()

    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))
    argus = ArgusOrchestrator(memory=memory)

    outcome = argus.review(
        diff=diff,
        project=args.project,
        repo_root=args.repo,
        verify_with_tools=not args.no_tools,
        refine=not args.no_refine,
    )

    if outcome.blocked_reason:
        print(f"BLOCKED: {outcome.blocked_reason}", file=sys.stderr)
        return 1

    print(f"=== Reasoning ({outcome.review.complexity}, conf={outcome.review.confidence:.2f}) ===")
    print(outcome.review.verdict[:1500])
    print(f"\n=== Perception ===")
    print(f"  discovered/selected: {outcome.perception_trace.files_discovered}/{outcome.perception_trace.files_selected}")
    print(f"  selectivity: {outcome.perception_trace.selectivity:.1%}")
    print(f"\n=== Reflection ===")
    print(f"  {outcome.reflection_meta}")
    print(f"\n=== Collaboration ===")
    print(f"  {outcome.collaboration_meta}")
    print(f"\n=== Governance ===")
    print(f"  {outcome.governance_meta}")
    print(f"\n=== Action log ({len(outcome.action_log)} action(s)) ===")
    for a in outcome.action_log:
        flag = "BLOCKED" if a.guardrail_blocked else ("ERROR" if a.error else "OK")
        print(f"  [{flag:7}] {a.tool_name} {a.wall_time_ms:.0f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
