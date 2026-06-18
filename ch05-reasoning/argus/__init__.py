"""Argus — code-review agent, Ch5 snapshot.

What Argus can do at end of Ch5 (additive over Ch4):
  + Complexity-routed reasoning:
      - SIMPLE  diffs → cheap haiku tier, one pass, ~$0.001 per review
      - MODERATE      → sonnet + chain-of-thought, verifier on weakest step
      - COMPLEX       → sonnet with extended thinking, deep multi-step trace
  + Verdict carries the reasoning chain (steps + confidences), not just
    a summary string — observability through ReviewResult.
  + review_diff() now returns (ReviewResult, PerceptionTrace) instead of
    (dict, PerceptionTrace). The dict form was a one-shot prompt; the
    structured result was earned by reasoning.

Use:
    from argus import review_diff, ArgusMemory, ArgusReasoning
    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=my_db))
    reasoning = ArgusReasoning()
    result, p_trace = review_diff(diff, project='my-app',
                                  memory=memory, reasoning=reasoning)
    print(result.complexity, result.confidence)
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory",
    "ArgusReasoning",
    "ReviewResult",
    "gather_review_context",
    "FileContext",
    "PerceptionTrace",
]
