"""Application-visible reasoning records and targeted verification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from anthropic import Anthropic
except ImportError:  # The offline behavior tests do not need the SDK.
    Anthropic = object  # type: ignore[misc,assignment]

from patterns.response_text import first_text


MODEL = "claude-sonnet-4-6"

COT_SYSTEM_PROMPT = """\
Reason through the question one step at a time
and show the work, rather than presenting only the conclusion.

Rules:
- One claim per step. If a step joins two claims with "and",
  split it into two steps.
- Every step must follow from an earlier step or from evidence
  stated in the question. Do not jump to a conclusion you
  already hold and reconstruct the steps behind it.
- Rate each step's confidence honestly, from 0.00 to 1.00. The
  rating is about that step alone, not about the final answer.
  A step you cannot check against the material in front of you
  is low confidence even when it sounds obvious, and a step
  that merely restates an assumption is lower still.

Reply in exactly this format and nothing else:
Step 1 (0.95): <the first step>
Step 2 (0.72): <the step that follows from it>
ANSWER: <the conclusion the steps lead to>
"""

VERIFY_PROMPT = """\
Original question and available evidence:
{question}

Steps already accepted, for context. Take them as
given and do not re-litigate them (empty if the step under
review is the first one):
{prior}

The step now under review, as a structured record:
{step}

Does this step follow from the steps above and from sound
reasoning? Judge the step on its own merits, not on whether
you like the conclusion it leads toward: a step that reaches a
defensible answer through a leap of logic is still invalid.

Reply in exactly this format:
VERDICT: SOUND | INVALID
WHY: <one sentence naming the specific defect, or naming what
     makes the step hold>

Use the word INVALID on the VERDICT line only.
"""

_UNRATED = 0.5
_STEP_RE = re.compile(
    r"^step\s*\d+\s*"
    r"(?:\(([^)]*)\))?"
    r"\s*:\s*(.*)$",
    re.IGNORECASE,
)
_ANSWER_RE = re.compile(
    r"^(?:final\s+)?answer\s*:\s*(.*)$",
    re.IGNORECASE,
)
_CONF_RE = re.compile(r"([+-]?[0-9]*\.?[0-9]+)\s*(%?)")


@dataclass
class ReasoningStep:
    step_number: int
    content: str
    confidence: float


@dataclass
class ChainOfThought:
    """A represented decision record, not a private-reasoning export."""

    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    source_question: str = ""

    def add_step(
        self,
        content: str,
        confidence: float = 1.0,
    ) -> ReasoningStep:
        step = ReasoningStep(
            step_number=len(self.steps) + 1,
            content=content,
            confidence=confidence,
        )
        self.steps.append(step)
        return step

    @property
    def weakest_step(self) -> ReasoningStep | None:
        if not self.steps:
            return None
        return min(self.steps, key=lambda step: step.confidence)


def _confidence(raw: str | None) -> float:
    """Parse a contracted 0..1 rating; unknown scales remain unknown."""
    if raw is None:
        return _UNRATED
    match = _CONF_RE.search(raw)
    if not match:
        return _UNRATED
    value = float(match.group(1))
    if match.group(2) == "%":
        value /= 100.0
    if not 0.0 <= value <= 1.0:
        return _UNRATED
    return value


def parse_chain(text: str) -> ChainOfThought:
    """Turn the prompt's line contract into a structured record."""
    chain = ChainOfThought()
    parsed_steps: list[tuple[float, list[str]]] = []
    answer: list[str] = []
    target: list[str] | None = None

    for raw in text.splitlines():
        line = raw.replace("**", "").strip()
        if not line:
            continue
        step_match = _STEP_RE.match(line)
        if step_match:
            parsed_steps.append(
                (_confidence(step_match.group(1)), [step_match.group(2)])
            )
            target = parsed_steps[-1][1]
            continue
        answer_match = _ANSWER_RE.match(line)
        if answer_match:
            answer.append(answer_match.group(1))
            target = answer
            continue
        if target is not None:
            target.append(line)

    for confidence, lines in parsed_steps:
        content = " ".join(item for item in lines if item).strip()
        if content:
            chain.add_step(content, confidence)

    chain.final_answer = " ".join(item for item in answer if item).strip()
    if not chain.final_answer:
        chain.final_answer = (
            chain.steps[-1].content if chain.steps else text.strip()
        )
    return chain


def reason_with_cot(
    client: Anthropic,
    question: str,
) -> ChainOfThought:
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=COT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    chain = parse_chain(first_text(response))
    chain.source_question = question
    return chain


def verify_chain(
    client: Anthropic,
    chain: ChainOfThought,
    targets: list[ReasoningStep] | None = None,
) -> list[dict]:
    """Verify selected steps; default to the whole represented chain."""
    issues = []
    for step in targets or chain.steps:
        try:
            index = chain.steps.index(step)
        except ValueError:
            continue
        prior = "\n".join(
            f"Step {item.step_number}: {item.content}"
            for item in chain.steps[:index]
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": VERIFY_PROMPT.format(
                    question=chain.source_question,
                    prior=prior,
                    step=(
                        f"Step {step.step_number} "
                        f"({step.confidence:.2f}): {step.content}"
                    ),
                ),
            }],
        )
        text = first_text(response)
        if "INVALID" in text.upper():
            issues.append({"step": step.step_number, "issue": text})
    return issues
