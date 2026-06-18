from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

@dataclass
class ReasoningStep:
    step_number: int
    content: str
    confidence: float  #A

@dataclass
class ChainOfThought:
    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""

    def add_step(self, content: str, confidence: float = 1.0):
        step = ReasoningStep(
            step_number=len(self.steps) + 1,
            content=content,
            confidence=confidence,
        )
        self.steps.append(step)

    @property
    def weakest_step(self) -> ReasoningStep | None:
        if not self.steps:
            return None
        return min(  #B
        self.steps, key=lambda s: s.confidence)


def reason_with_cot(
    client: Anthropic, question: str
) -> ChainOfThought:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=COT_SYSTEM_PROMPT,  #C
        messages=[{"role": "user", "content": question}],
    )
    return parse_chain(response.content[0].text)  #D


def verify_chain(
    client: Anthropic, chain: ChainOfThought
) -> list[dict]:
    issues = []
    for i, step in enumerate(chain.steps):
        prior = "\n".join(
            f"Step {s.step_number}: {s.content}"
            for s in chain.steps[:i]
        )
        response = client.messages.create(  #E
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user",
                       "content": VERIFY_PROMPT.format(
                           prior=prior, step=step)}],
        )
        if "INVALID" in response.content[0].text.upper():
            issues.append({"step": step.step_number,
                           "issue": response.content[0].text})
    return issues  #F
