"""Argus — code-review agent, Ch3 snapshot.

What Argus can do at end of Ch3:
  * Read a unified diff and discover the modified files
  * Follow imports from modified files to gather dependencies
  * Find test files that exercise the modified modules
  * Load project configuration (linters, type checkers)
  * Triage all discovered files under a token budget, dropping low-priority
    items when the budget is exhausted
  * Emit a PerceptionTrace recording every decision (auditable observability)
  * Run one LLM pass on the selected context to produce a structured review

Use:
    from argus import review_diff, gather_review_context, PerceptionTrace
    review, trace = review_diff(diff_text, repo_root="/path/to/repo")
"""
from .perception import (
    gather_review_context,
    FileContext,
    PerceptionTrace,
)
from .core import review_diff

__all__ = [
    "review_diff",
    "gather_review_context",
    "FileContext",
    "PerceptionTrace",
]
