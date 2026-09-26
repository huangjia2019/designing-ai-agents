"""Argus — code-review agent, Ch8 snapshot.

What Argus can do at end of Ch8 (additive over Ch7):
  + Delegate complex diffs to three parallel sub-agents
      (security / style / complexity perspectives)
  + Synthesize sub-agent findings into a unified review
  + Optional adversarial check on individual claims
  + CollaborationTrace for audit (token multiplier, handoff fidelity,
      conflicts, wall time)

Use:
    from argus import review_diff, ArgusCollaboration
    collab = ArgusCollaboration()  # default stub sub-agents
    result, p_trace, action_log, reflection_meta, collab_meta = review_diff(
        diff, project='x', memory=m, collaboration=collab,
    )
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory", "ArgusReasoning", "ReviewResult",
    "ArgusAction", "ArgusReflection", "ArgusCollaboration",
    "gather_review_context", "FileContext", "PerceptionTrace",
]
