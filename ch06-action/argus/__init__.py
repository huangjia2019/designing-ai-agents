"""Argus — code-review agent, Ch6 snapshot.

What Argus can do at end of Ch6 (additive over Ch5):
  + Run real tools (lint, test, apply_fix) through the Guardrail Sandwich
  + Emit ActionTrace per tool invocation — audit trail for every action
  + Pre-check (allowed tools, forbidden paths) and post-check (output size)
  + Human-in-the-loop slot: irreversible actions (fix_apply) can be gated
    on an external approver function
  + review_diff() now returns (result, p_trace, action_log) — the third
    element makes Ch6's contribution observable

Use:
    from argus import review_diff, ArgusAction
    action = ArgusAction()  # default policy
    result, p_trace, action_log = review_diff(diff, project='x', memory=m, action=action)
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction, default_policy
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory",
    "ArgusReasoning",
    "ReviewResult",
    "ArgusAction",
    "default_policy",
    "gather_review_context",
    "FileContext",
    "PerceptionTrace",
]
