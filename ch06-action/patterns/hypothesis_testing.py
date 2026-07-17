from dataclasses import dataclass, field
from enum import Enum
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

MODEL = "claude-sonnet-4-6"

OBSERVE_PROMPT = """Problem under investigation:
{problem}

Before forming any hypothesis, gather evidence. Propose ONE
read-only shell command that would tell you most about the
current state. Reply with the bare command and nothing else.
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
being true and being false. The predictions must differ; if the
same result is expected either way, the experiment is worthless.

Reply in exactly this format:
ACTION: <one shell command>
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
    """First non-empty line, stripped of markdown fencing."""
    for line in text.splitlines():
        line = line.strip().strip("`").strip()
        if line and not line.startswith("```"):
            return line
    return ""


def _field(text: str, label: str) -> str | None:
    """Pull `LABEL: value` out of a labelled reply."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(label + ":"):
            return stripped[len(label) + 1:].strip()
    return None


class HypothesisStatus(Enum):
    ACTIVE = "active"
    SUPPORTED = "supported"
    REFUTED = "refuted"

@dataclass
class Hypothesis:
    id: str
    description: str
    status: HypothesisStatus = (
        HypothesisStatus.ACTIVE)
    evidence_for: list[str] = field(
        default_factory=list)
    evidence_against: list[str] = field(
        default_factory=list)

    @property
    def evidence_ratio(self) -> float:  #A
        total = (len(self.evidence_for)
                 + len(self.evidence_against))
        return (len(self.evidence_for) / total
                if total else 0.5)

@dataclass
class Experiment:
    action: str
    expected_if_true: str  #B
    expected_if_false: str

class HypothesisTester:
    def __init__(self, client: Anthropic,
                 execute_fn,
                 max_iterations: int = 8):
        self.client = client
        self.execute = execute_fn  #C
        self.max_iterations = max_iterations
        self.hypotheses = {}
        self.observations = []

    def investigate(self, problem):
        initial_obs = self._observe(problem)  #D
        self._generate_hypotheses(
            problem, initial_obs)

        for i in range(self.max_iterations):
            active = [
                h for h in self.hypotheses.values()
                if h.status == HypothesisStatus.ACTIVE
            ]
            if not active:
                break
            target = min(active,  #E
                key=lambda h: abs(
                    h.evidence_ratio - 0.5))
            experiment = self._design_experiment(
                target)
            observation = self.execute(  #F
                experiment.action)
            self.observations.append({
                "action": experiment.action,
                "result": observation,
            })
            self._analyze(
                target, experiment, observation)

        return self._summarize_results()

    # --- engine behind the loop above -------------------
    # Listing 5.5b prints investigate(); these are the
    # methods it calls. Kept below the listing boundary so
    # the loop above still reads as it does in the book.

    def _observe(self, problem) -> str:
        """Gather evidence before any hypothesis exists.

        Observing first is what stops the loop from
        hypothesising and then hunting for confirmation:
        the evidence is on the table before there is a
        favoured explanation to defend.
        """
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{"role": "user",
                       "content": OBSERVE_PROMPT.format(
                           problem=problem)}],
        )
        command = _first_line(
            response.content[0].text)
        observation = self.execute(command)
        self.observations.append({
            "action": command,
            "result": observation,
        })
        return observation

    def _generate_hypotheses(
            self, problem, initial_obs) -> None:
        """Populate self.hypotheses from the first look."""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user",
                       "content": HYPOTHESIS_PROMPT.format(
                           problem=problem,
                           observation=initial_obs)}],
        )
        for line in response.content[0].text.splitlines():
            line = line.strip()
            if not line.startswith("-"):
                continue
            description = line.lstrip("-").strip()
            if not description:
                continue
            hid = f"h{len(self.hypotheses) + 1}"
            self.hypotheses[hid] = Hypothesis(
                id=hid, description=description)

    def _design_experiment(
            self, hypothesis) -> Experiment:
        """Ask for one discriminating experiment.

        An unparseable reply yields an empty action, which
        execute_fn refuses and _analyze reads as evidence.
        A refusal is a real result; a fabricated fallback
        command would not be.
        """
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user",
                       "content": EXPERIMENT_PROMPT.format(
                           description=hypothesis.description,
                           history=self._history())}],
        )
        text = response.content[0].text
        return Experiment(
            action=_field(text, "ACTION") or "",
            expected_if_true=(
                _field(text, "IF_TRUE") or ""),
            expected_if_false=(
                _field(text, "IF_FALSE") or ""),
        )

    def _analyze(self, hypothesis, experiment,
                 observation) -> None:
        """File the result as evidence for or against."""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user",
                       "content": ANALYZE_PROMPT.format(
                           description=hypothesis.description,
                           action=experiment.action,
                           if_true=experiment.expected_if_true,
                           if_false=experiment.expected_if_false,
                           observation=observation)}],
        )
        text = response.content[0].text
        verdict = (_field(text, "VERDICT") or "").upper()
        note = (_field(text, "WHY")
                or text.strip())[:300]
        if "SUPPORTS" in verdict:
            hypothesis.evidence_for.append(note)
        elif "REFUTES" in verdict:
            hypothesis.evidence_against.append(note)
        self._settle(hypothesis)

    def _settle(self, hypothesis) -> None:
        """Close a hypothesis once its evidence is unanimous.

        evidence_ratio decides, not any single verdict
        string. An experiment carries dual predictions, so
        a result matching one of them is real evidence and
        one is enough to close on — but only while nothing
        contradicts it. Mixed evidence lands near 0.5 and
        keeps the hypothesis open no matter how many
        experiments have run, which is the behaviour that
        matters: contradiction should cost more than
        repetition buys.
        """
        total = (len(hypothesis.evidence_for)
                 + len(hypothesis.evidence_against))
        if total < 1:
            return
        if hypothesis.evidence_ratio >= 0.8:
            hypothesis.status = (
                HypothesisStatus.SUPPORTED)
        elif hypothesis.evidence_ratio <= 0.2:
            hypothesis.status = (
                HypothesisStatus.REFUTED)

    def _history(self) -> str:
        """Experiments already run, for experiment design."""
        if not self.observations:
            return "(nothing yet)"
        return "\n".join(
            f"- {o['action']} -> {str(o['result'])[:120]}"
            for o in self.observations
        )

    def _summarize_results(self) -> dict:
        """Aggregate the trail. No model call.

        The verdict is arithmetic over evidence the loop
        actually collected, so it cannot drift from the
        trail it claims to rest on.
        """
        ranked = sorted(
            self.hypotheses.values(),
            key=lambda h: h.evidence_ratio,
            reverse=True,
        )
        supported = [
            h for h in ranked
            if h.status == HypothesisStatus.SUPPORTED
        ]
        return {
            "verdict": (supported[0].description
                        if supported else "inconclusive"),
            "hypotheses": [
                {"id": h.id,
                 "description": h.description,
                 "status": h.status.value,
                 "evidence_ratio": h.evidence_ratio,
                 "evidence_for": list(h.evidence_for),
                 "evidence_against": list(
                     h.evidence_against)}
                for h in ranked
            ],
            "observations": list(self.observations),
        }
