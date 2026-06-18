"""Argus — code-review agent, Ch9 snapshot.

What Argus can do at end of Ch9 (additive over Ch8):
  + Permission gate over every side-effect action (capability-based)
  + Declarative policy engine (allow / deny / escalate)
  + Append-only, hash-chained audit log — tamper-evident
  + Trust levels: promote on clean streaks, demote on incidents
  + Capability grants tied to trust transitions

Use:
    from argus import review_diff, ArgusGovernance
    from patterns.trust_levels import TrustLevel
    gov = ArgusGovernance(initial_trust=TrustLevel.ACT_THEN_REVIEW)
    result, p_trace, action_log, reflection_meta, collab_meta, gov_meta = \\
        review_diff(diff, project='x', memory=m, governance=gov)
    print(gov_meta)  # {'audit_chain_ok': True, 'current_trust': 1, ...}
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance, GovernanceDecision
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory", "ArgusReasoning", "ReviewResult",
    "ArgusAction", "ArgusReflection", "ArgusCollaboration", "ArgusGovernance",
    "GovernanceDecision",
    "gather_review_context", "FileContext", "PerceptionTrace",
]
