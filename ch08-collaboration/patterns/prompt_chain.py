"""Prompt Chain — the Unix pipe for LLM steps.

Book: Chapter 6, Listing 6.2 (PipelineStep) and Listing 6.3 (PromptChain).

Each step is a self-contained unit with its own system prompt, model, and
optional quality gate. The chain composes steps into a linear pipeline; when
a gate rejects a step's output, the chain feeds the failure message back to
the model and retries.
"""
from dataclasses import dataclass
from typing import Any

try:  # keeps this module importable without the SDK installed
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


@dataclass
class StepResult:
    step_name: str
    output: Any
    passed_gate: bool = True
    gate_message: str = ""
    model_used: str = ""
    tokens_used: int = 0


class PipelineStep:
    """Self-contained unit with own prompt and gate."""

    def __init__(
        self, name: str,
        system_prompt: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        gate: callable = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.gate = gate

    def run(
        self, client: Anthropic,
        input_text: str,
    ) -> StepResult:
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=[{
                "role": "user",
                "content": input_text,
            }],
        )
        output = resp.content[0].text
        passed, msg = True, ""
        if self.gate:
            passed, msg = (
                self.gate(output)
            )
        return StepResult(
            step_name=self.name,
            output=output,
            passed_gate=passed,
            gate_message=msg,
            model_used=self.model,
            tokens_used=(
                resp.usage.input_tokens
                + resp.usage.output_tokens
            ),
        )


class PromptChain:
    """Composes steps with fluent .add_step() chaining."""

    def __init__(
        self, client: Anthropic,
        max_retries: int = 2,
    ):
        self.client = client
        self.steps: list[PipelineStep] = []
        self.max_retries = max_retries
        self.trace: list[StepResult] = []

    def add_step(self, step):
        self.steps.append(step)
        return self

    def run(  # Gate retry with failure feedback to LLM
        self, initial_input: str,
    ) -> dict:
        self.trace = []
        current = initial_input
        for step in self.steps:
            for attempt in range(
                self.max_retries + 1
            ):
                result = step.run(
                    self.client, current,
                )
                self.trace.append(result)
                if result.passed_gate:
                    current = result.output
                    break
                elif (
                    attempt
                    < self.max_retries
                ):
                    current = (
                        f"{current}\n\n"
                        f"[Failed: "
                        f"{result.gate_message}"
                        f". Try again.]"
                    )
                else:
                    return {
                        "success": False,
                        "failed_at": step.name,
                        "gate_message": result.gate_message,
                    }
        return {
            "success": True,
            "output": current,
            "total_tokens": sum(
                r.tokens_used
                for r in self.trace
            ),
        }
