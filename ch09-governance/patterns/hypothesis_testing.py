"""A bounded observe-hypothesize-test-update loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

from patterns.response_text import first_text


MODEL = "claude-sonnet-4-6"

OBSERVE_PROMPT = """Problem under investigation:
{problem}

Before forming any hypothesis, gather evidence. Propose ONE
read-only command that would tell you most about the current
state. Reply with the bare command and nothing else.
"""

HYPOTHESIS_PROMPT = """Problem under investigation:
{problem}

First observation:
{observation}

Propose 2-4 competing explanations that this evidence does not
yet rule out. One per line, each starting with "- ". No prose.
"""

EXPERIMENT_PROMPT = """Hypothesis under test:
{description}

What has been tried so far:
{history}

Design ONE experiment that discriminates between this hypothesis
being true and being false. The predictions must differ.

Reply in exactly this format:
ACTION: <one read-only command>
IF_TRUE: <what you expect to see if the hypothesis holds>
IF_FALSE: <what you expect to see if it does not>
"""

ANALYZE_PROMPT = """Hypothesis under test:
{description}

Experiment run: {action}
Predicted if true: {if_true}
Predicted if false: {if_false}

Actual result:
{observation}

Which prediction did the result match?

Reply in exactly this format:
VERDICT: SUPPORTS | REFUTES | INCONCLUSIVE
WHY: <one sentence citing the result>
"""


def _first_line(text: str) -> str:
    for line in text.splitlines():
        value = line.strip().strip("`").strip()
        if value and not value.startswith("```"):
            return value
    return ""


def _field(text: str, label: str) -> str | None:
    prefix = f"{label.upper()}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


class HypothesisStatus(Enum):
    ACTIVE = "active"
    SUPPORTED = "supported"
    REFUTED = "refuted"


@dataclass
class Hypothesis:
    id: str
    description: str
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)

    @property
    def evidence_ratio(self) -> float:
        total = len(self.evidence_for) + len(self.evidence_against)
        return len(self.evidence_for) / total if total else 0.5


@dataclass
class Experiment:
    action: str
    expected_if_true: str
    expected_if_false: str


class HypothesisTester:
    def __init__(
        self,
        client: Anthropic,
        execute_fn,
        max_iterations: int = 8,
    ):
        self.client = client
        self.execute = execute_fn
        self.max_iterations = max(0, max_iterations)
        self.hypotheses: dict[str, Hypothesis] = {}
        self.observations: list[dict] = []

    def investigate(self, problem: str) -> dict:
        initial_observation = self._observe(problem)
        self._generate_hypotheses(problem, initial_observation)

        for _ in range(self.max_iterations):
            active = [
                hypothesis
                for hypothesis in self.hypotheses.values()
                if hypothesis.status == HypothesisStatus.ACTIVE
            ]
            if not active:
                break
            target = min(
                active,
                key=lambda hypothesis: abs(
                    hypothesis.evidence_ratio - 0.5
                ),
            )
            experiment = self._design_experiment(target)
            observation = self._execute(experiment.action)
            self.observations.append({
                "phase": "experiment",
                "hypothesis": target.id,
                "action": experiment.action,
                "result": observation,
            })
            self._analyze(target, experiment, observation)

        return self._summarize_results()

    def _execute(self, action: str) -> str:
        try:
            return str(self.execute(action))
        except Exception as exc:  # The exception is evidence, not convergence.
            return f"[execution error] {type(exc).__name__}: {exc}"

    def _observe(self, problem: str) -> str:
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": OBSERVE_PROMPT.format(problem=problem),
            }],
        )
        command = _first_line(first_text(response))
        observation = self._execute(command)
        self.observations.append({
            "phase": "initial_observation",
            "action": command,
            "result": observation,
        })
        return observation

    def _generate_hypotheses(
        self,
        problem: str,
        initial_observation: str,
    ) -> None:
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": HYPOTHESIS_PROMPT.format(
                    problem=problem,
                    observation=initial_observation,
                ),
            }],
        )
        for line in first_text(response).splitlines():
            stripped = line.strip()
            if not stripped.startswith(("-", "*", "•")):
                continue
            description = stripped.lstrip("-*• ").strip()
            if not description:
                continue
            identifier = f"h{len(self.hypotheses) + 1}"
            self.hypotheses[identifier] = Hypothesis(
                id=identifier,
                description=description,
            )

    def _design_experiment(
        self,
        hypothesis: Hypothesis,
    ) -> Experiment:
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": EXPERIMENT_PROMPT.format(
                    description=hypothesis.description,
                    history=self._history(),
                ),
            }],
        )
        text = first_text(response)
        return Experiment(
            action=_field(text, "ACTION") or "",
            expected_if_true=_field(text, "IF_TRUE") or "",
            expected_if_false=_field(text, "IF_FALSE") or "",
        )

    def _analyze(
        self,
        hypothesis: Hypothesis,
        experiment: Experiment,
        observation: str,
    ) -> None:
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": ANALYZE_PROMPT.format(
                    description=hypothesis.description,
                    action=experiment.action,
                    if_true=experiment.expected_if_true,
                    if_false=experiment.expected_if_false,
                    observation=observation,
                ),
            }],
        )
        text = first_text(response)
        verdict = (_field(text, "VERDICT") or "").upper()
        note = (_field(text, "WHY") or text.strip())[:300]
        if verdict == "SUPPORTS":
            hypothesis.evidence_for.append(note)
        elif verdict == "REFUTES":
            hypothesis.evidence_against.append(note)
        self._settle(hypothesis)

    @staticmethod
    def _settle(hypothesis: Hypothesis) -> None:
        total = len(hypothesis.evidence_for) + len(
            hypothesis.evidence_against
        )
        if total == 0:
            return
        if hypothesis.evidence_ratio >= 0.8:
            hypothesis.status = HypothesisStatus.SUPPORTED
        elif hypothesis.evidence_ratio <= 0.2:
            hypothesis.status = HypothesisStatus.REFUTED

    def _history(self) -> str:
        if not self.observations:
            return "(nothing yet)"
        return "\n".join(
            f"- {item['action']} -> {str(item['result'])[:120]}"
            for item in self.observations
        )

    def _summarize_results(self) -> dict:
        ranked = sorted(
            self.hypotheses.values(),
            key=lambda hypothesis: hypothesis.evidence_ratio,
            reverse=True,
        )
        supported = [
            item
            for item in ranked
            if item.status == HypothesisStatus.SUPPORTED
        ]
        active = [
            item
            for item in ranked
            if item.status == HypothesisStatus.ACTIVE
        ]
        if supported:
            outcome = "supported"
            verdict = supported[0].description
        elif ranked and not active:
            outcome = "refuted"
            verdict = "all generated hypotheses were refuted"
        else:
            outcome = "inconclusive"
            verdict = "inconclusive"
        return {
            "outcome": outcome,
            "verdict": verdict,
            "hypotheses": [
                {
                    "id": item.id,
                    "description": item.description,
                    "status": item.status.value,
                    "evidence_ratio": item.evidence_ratio,
                    "evidence_for": list(item.evidence_for),
                    "evidence_against": list(item.evidence_against),
                }
                for item in ranked
            ],
            "observations": list(self.observations),
        }
