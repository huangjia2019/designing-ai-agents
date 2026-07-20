from dataclasses import dataclass, field
from enum import Enum
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

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
