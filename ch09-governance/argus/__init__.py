"""Argus — code-review agent, Ch9 snapshot.

What Argus can do at end of Ch9 (additive over Ch8), one capability
per governance pattern:
  + Approval Gate (§9.2): every action classified by risk and routed to
    allow / deny / ask, with a reason recorded for each decision
  + Blast Radius Control (§9.3): tool allowlist, path boundaries, rate
    limit and budget cap bound the damage of whatever does run
  + Progressive Commitment (§9.4): trust escalates on clean streaks and
    demotes on errors, deciding when 'ask' still needs a human
  + Observability Harness (§9.5): spans, metrics and a dashboard over
    the whole run

Use:
    from argus import review_diff, ArgusGovernance
    from patterns.progressive_commitment import TrustLevel
    gov = ArgusGovernance(initial_trust=TrustLevel.AUTONOMOUS)
    result, p_trace, action_log, reflection_meta, collab_meta, gov_meta = \\
        review_diff(diff, project='x', memory=m, governance=gov)
    print(gov_meta)  # {'allowed': True, 'current_trust': 3, ...}

At the default SUPERVISED trust level a HIGH-risk tool (lint runs via
run_command) needs a human, so pass review_diff an approver:
    review_diff(..., ask_human=lambda action, reason: True)
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory", "ArgusReasoning", "ReviewResult",
    "ArgusAction", "ArgusReflection", "ArgusCollaboration", "ArgusGovernance",
    "gather_review_context", "FileContext", "PerceptionTrace",
]
