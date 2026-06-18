"""Handoff Chain — sequential agent specialists, each owning one stage.

Triage agent → diagnosis agent → fix agent → review agent. Each agent's
output becomes the next agent's input. Cleaner than one mega-prompt
because each stage has its own minimal context.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class HandoffStage:
    name: str
    instruction: str
    agent: Callable[[str, str], str]  # (instruction, input) -> output


def run_handoff_chain(stages: list[HandoffStage], initial_input: str) -> list[dict]:
    """Run each stage sequentially, threading output forward."""
    results = []
    current = initial_input
    for stage in stages:
        out = stage.agent(stage.instruction, current)
        results.append({"stage": stage.name, "input": current, "output": out})
        current = out
    return results
