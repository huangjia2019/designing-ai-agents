"""Argus — code-review agent, Ch7 snapshot.

What Argus can do at end of Ch7 (additive over Ch6):
  + Critic loop over its own review (generator-critic with loop invariant)
  + Skill library: stores verified review heuristics, retrievable by task
  + Experience replay: L0 traces + L1 reflections + L2 lessons, adaptive
    trigger via _should_extract_lessons (rolling-window failure-rate)
  + Self-heal loop: bounded retry when applied fixes break tests

Use:
    from argus import review_diff, ArgusReflection
    reflection = ArgusReflection()
    result, p_trace, action_log, reflection_meta = review_diff(
        diff, project='x', memory=m, action=a, reflection=reflection,
    )
    print(reflection_meta)  # {'iterations': 2, 'converged': True, ...}
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .self_heal import heal_with_tests, HealOutcome
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory", "ArgusReasoning", "ReviewResult",
    "ArgusAction", "ArgusReflection",
    "heal_with_tests", "HealOutcome",
    "gather_review_context", "FileContext", "PerceptionTrace",
]
