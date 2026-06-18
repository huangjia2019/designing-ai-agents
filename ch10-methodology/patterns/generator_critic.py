"""Generator-Critic Loop — produce, evaluate, refine. Loop invariant guarantees
every returned output has been critiqued (W3 redesign from Ch7 0615).

Three variants of the critique step:
  * Variant 1: self-critique (cheap, biased)
  * Variant 2: cross-model verification (sonnet drafts, opus critiques)
  * Variant 3: tool-grounded (pytest, linter — deterministic feedback)

Production agents converge on Variant 3 when a deterministic verifier is
available, falling back to Variant 2 when not.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Critique:
    score: float
    approved: bool
    feedback_text: str = ""
    issues: list[str] = field(default_factory=list)


class GeneratorCriticLoop:
    """Generator-Critic with bounded iteration + final-output guarantee."""

    def __init__(self,
                 generate: Callable[[str, str], str],
                 critique_fn: Callable[[str, str, str], Critique],
                 max_iterations: int = 3,
                 quality_threshold: float = 0.9):
        self._generate = generate
        self._critique = critique_fn
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.history: list[dict] = []

    def refine(self, task: str, tool_fn: Callable[[str], str] | None = None) -> dict:
        """Run generator-critic; final output is always paired with its critique."""
        output = self._generate(task, "")
        critique: Critique | None = None
        for i in range(self.max_iterations):
            tool_feedback = tool_fn(output) if tool_fn else ""
            critique = self._critique(task, output, tool_feedback)
            self.history.append({
                "iteration": i,
                "score": critique.score,
                "approved": critique.approved,
            })
            if critique.approved:
                return {
                    "output": output,
                    "iterations": i + 1,
                    "final_score": critique.score,
                    "converged": True,
                }
            # Refine only when iterations remain (loop invariant: output paired with critique)
            if i < self.max_iterations - 1:
                ctx = f"Issues:\n{critique.feedback_text}"
                if tool_feedback:
                    ctx += f"\nTool: {tool_feedback}"
                output = self._generate(task, ctx)
        # Loop exhausted; `critique` holds the final evaluation
        return {
            "output": output,
            "iterations": self.max_iterations,
            "final_score": critique.score if critique else 0.0,
            "converged": False,
        }
