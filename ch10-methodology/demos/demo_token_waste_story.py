"""Demo: Ch5 token-waste story made tangible.

Run a review on a 200-line diff first WITHOUT complexity routing
(treats every diff as COMPLEX), then WITH complexity routing
(classifies the diff and uses the cheap tier when adequate). The
token-spend delta is the chapter's claim in numbers.

This is NOT calling a real LLM — the demo wires a fake reasoning
shim so it runs offline. Replace the shim with the live reasoning
layer to see real cost.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus import ArgusOrchestrator, ArgusMemory, ArgusReasoning, ReviewResult


class _CountingReasoning(ArgusReasoning):
    """Tracks token count by complexity tier (rough proxy)."""

    TOKEN_BY_TIER = {"simple": 1500, "moderate": 6000, "complex": 32000}

    def __init__(self, *, ignore_complexity: bool = False):
        super().__init__(client=None)
        self.ignore_complexity = ignore_complexity
        self.spent = 0

    def review(self, diff: str) -> ReviewResult:
        tier = "complex" if self.ignore_complexity else self._classify(diff)
        self.spent += self.TOKEN_BY_TIER[tier]
        return ReviewResult(
            verdict=f"[{tier}] mock review",
            reasoning_steps=[],
            confidence=0.85,
            complexity=tier,
        )

    @staticmethod
    def _classify(diff: str) -> str:
        lines = diff.count("\n")
        if lines < 30: return "simple"
        if lines < 100: return "moderate"
        return "complex"


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


SAMPLE_DIFF = "\n".join(
    f"--- a/file_{i}.py\n+++ b/file_{i}.py\n@@ -1 +1 @@\n-old\n+new"
    for i in range(10)
)  # ~60 lines: falls in MODERATE tier under the classifier


def run(ignore: bool) -> tuple[int, str]:
    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=_Stub()))
    reasoning = _CountingReasoning(ignore_complexity=ignore)
    argus = ArgusOrchestrator(memory=memory, reasoning=reasoning)
    outcome = argus.review(diff=SAMPLE_DIFF, project="demo",
                           verify_with_tools=False, refine=False)
    return reasoning.spent, outcome.review.complexity


def main():
    flat_cost, flat_tier = run(ignore=True)
    routed_cost, routed_tier = run(ignore=False)
    print(f"Without complexity routing: {flat_cost:>6d} tokens (tier={flat_tier})")
    print(f"With    complexity routing: {routed_cost:>6d} tokens (tier={routed_tier})")
    savings = (flat_cost - routed_cost) / flat_cost * 100
    print(f"Savings: {savings:.1f}%  ({flat_cost - routed_cost} tokens cheaper)")


if __name__ == "__main__":
    main()
