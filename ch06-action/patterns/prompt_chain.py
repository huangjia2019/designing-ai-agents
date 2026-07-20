"""Prompt Chain — sequential prompts where step N+1 sees step N's output.

The most basic compositional pattern. Each step is a focused prompt with
strict output shape; the chain composes them into a workflow. Used by
Argus to: classify diff → identify hotspots → recommend reviewers.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ChainStep:
    name: str
    prompt_template: str  # may contain {prev_output} placeholder
    parse: Callable[[str], object] | None = None


def run_chain(steps: list[ChainStep], initial: str,
              llm_call: Callable[[str], str]) -> list[dict]:
    """Run each step, threading the previous output forward.

    llm_call(prompt) -> response_text — pluggable so the chain is testable
    without an actual LLM (pass a fake llm_call for unit tests).
    """
    results = []
    prev = initial
    for step in steps:
        prompt = step.prompt_template.format(prev_output=prev, initial=initial)
        out = llm_call(prompt)
        parsed = step.parse(out) if step.parse else out
        results.append({"step": step.name, "raw": out, "parsed": parsed})
        prev = out
    return results
