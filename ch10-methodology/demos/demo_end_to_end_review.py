"""Demo: full Argus end-to-end on a real diff (offline-safe).

Wires every module from Ch3-Ch9 into the ArgusOrchestrator, runs a
small diff against this very repository, and prints every trace.

This is the capstone demo — §10.10's claim "every method call maps to
a working class" cashed in code. If this runs to completion and emits
the orchestration result, the cumulative Argus is real.

Set ANTHROPIC_API_KEY to switch the reasoning layer to live calls;
otherwise the demo uses a deterministic shim so it works offline.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus import ArgusOrchestrator, ArgusMemory, ArgusReasoning, ReviewResult


class _OfflineReasoning(ArgusReasoning):
    """No-network reasoning: classifies + emits canned verdict."""

    def __init__(self):
        super().__init__(client=None)

    def review(self, diff: str) -> ReviewResult:
        lines = diff.count("\n")
        tier = "simple" if lines < 30 else "moderate" if lines < 100 else "complex"
        return ReviewResult(
            verdict=(
                "[offline-shim] Review summary:\n"
                f" - {lines} changed lines, complexity={tier}\n"
                " - severity=info  Demo only; replace with live reasoning for real review.\n"
            ),
            reasoning_steps=[],
            confidence=0.7,
            complexity=tier,
        )


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

SAMPLE_DIFF = """\
--- a/argus/orchestrator.py
+++ b/argus/orchestrator.py
@@ -1,3 +1,4 @@
 # argus/orchestrator.py — Ch10 capstone
+# (demo addition)
 from dataclasses import dataclass
"""


def main():
    from patterns.hierarchical_memory import HierarchicalMemory

    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))
    reasoning = _OfflineReasoning() if not os.environ.get("ANTHROPIC_API_KEY") else None
    argus = ArgusOrchestrator(memory=memory, reasoning=reasoning or ArgusReasoning())

    outcome = argus.review(
        diff=SAMPLE_DIFF,
        project="argus-self-review",
        repo_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        verify_with_tools=False,  # keep offline
        refine=True,
    )

    if outcome.blocked_reason:
        print(f"BLOCKED: {outcome.blocked_reason}")
        return 1

    print("=== ORCHESTRATION RESULT ===")
    print(f"verdict ({outcome.review.complexity}, conf={outcome.review.confidence:.2f}):")
    print(outcome.review.verdict)
    print(f"\n--- perception ---")
    print(f"  {outcome.perception_trace.files_discovered} files discovered, "
          f"{outcome.perception_trace.files_selected} selected "
          f"({outcome.perception_trace.selectivity:.1%} selectivity)")
    print(f"--- action_log ---  {len(outcome.action_log)} entries")
    print(f"--- reflection ---  {json.dumps(outcome.reflection_meta)}")
    print(f"--- collaboration ---  {json.dumps(outcome.collaboration_meta)}")
    print(f"--- governance ---  {json.dumps(outcome.governance_meta)}")
    print("\nIf you see traces in every section above, §10.10 holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
