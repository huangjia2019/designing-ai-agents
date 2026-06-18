"""Argus — code-review agent, Ch10 capstone.

Ch10 makes §10.10's promise real: every cognitive function from Ch3-Ch9
is now a class, and ArgusOrchestrator wires them together in one
review() method. Reading orchestrator.py is reading the book's
contrarian insight in code form — a design pattern is not a behavior
prescription; it is a constraint that makes good runtime behavior
emerge from the orchestration.

Use:
    from argus import ArgusOrchestrator, ArgusMemory
    from patterns.hierarchical_memory import HierarchicalMemory

    memory = ArgusMemory(HierarchicalMemory(vector_db=my_db))
    argus = ArgusOrchestrator(memory=memory)

    outcome = argus.review(diff=diff_text, project="my-app")
    print(outcome.review.verdict)
    print(outcome.perception_trace.selectivity)
    print(outcome.action_log)
    print(outcome.reflection_meta)      # iterations, converged, final_score
    print(outcome.collaboration_meta)   # parallel_calls, messages
    print(outcome.governance_meta)      # audit_entries, current_trust
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance
from .orchestrator import ArgusOrchestrator, OrchestrationResult

__all__ = [
    "ArgusOrchestrator",
    "OrchestrationResult",
    "ArgusMemory", "ArgusReasoning", "ReviewResult",
    "ArgusAction", "ArgusReflection", "ArgusCollaboration", "ArgusGovernance",
    "gather_review_context", "FileContext", "PerceptionTrace",
]
