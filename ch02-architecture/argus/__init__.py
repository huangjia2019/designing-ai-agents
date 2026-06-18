"""Argus — code-review agent, Ch2 snapshot (the seed).

What Argus can do at end of Ch2:
  * Accept a unified diff (and an optional free-form context string)
  * Send a single LLM call asking for structured review JSON
  * Parse the JSON and return it

That is barely an agent — it is a structured prompt with JSON output. The
real PRA loop, the tool calls, the memory, the reflection all come later.
Ch3 will start to make this earn the name 'agent.'
"""
from .core import review_diff

__all__ = ["review_diff"]
