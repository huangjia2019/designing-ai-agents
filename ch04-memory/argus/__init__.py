"""Argus — code-review agent, Ch4 snapshot.

What Argus can do at end of Ch4 (additive over Ch3):
  + Cross-session memory:
      - before_review: retrieve top-k relevant past lessons for this project
      - after_review:  persist today's findings into long-term memory
  + Past lessons flow into the LLM context as a dedicated section, side by
    side with the perception-selected files.
  + Underlying pattern is HierarchicalMemory (Listing 4.5), wrapped by
    ArgusMemory (§4.8) — a thin facade tailored to the review domain.

Use:
    from argus import review_diff, ArgusMemory
    from patterns.hierarchical_memory import HierarchicalMemory
    memory = ArgusMemory(HierarchicalMemory(vector_db=my_db))
    review, trace = review_diff(diff, project='my-app', memory=memory)
"""
from .perception import gather_review_context, FileContext, PerceptionTrace
from .memory import ArgusMemory
from .core import review_diff

__all__ = [
    "review_diff",
    "ArgusMemory",
    "gather_review_context",
    "FileContext",
    "PerceptionTrace",
]
