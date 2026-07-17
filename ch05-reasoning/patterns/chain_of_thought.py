import re
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

COT_SYSTEM_PROMPT = """Reason through the question one step at a time
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

VERIFY_PROMPT = """Steps already accepted, for context. Take them as
given and do not re-litigate them (empty if the step under
review is the first one):
{prior}

The step now under review, as a structured record:
{step}

Does this step follow from the steps above and from sound
reasoning? Judge the step on its own merits, not on whether
you like the conclusion it leads toward: a step that reaches a
defensible answer through a leap of logic is still invalid,
and that is the case worth catching here.

Reply in exactly this format:
VERDICT: SOUND | INVALID
WHY: <one sentence naming the specific defect, or naming what
     makes the step hold>

Use the word INVALID on the VERDICT line only. The caller
scans this whole reply for that word, so a stray mention of it
in your WHY line reads as a verdict against the step.
"""

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


# --- parser behind reason_with_cot above ----------------
# Listing 5.2 prints the call to parse_chain(); this is the
# function it calls. Kept below the listing boundary so the
# chain above still reads as it does in the book.

# An unrated step is unknown, not certain. Scoring it 1.0
# would hide it from weakest_step, which is precisely the
# step most worth verifying: the one the model would not
# put a number on.
_UNRATED = 0.5

_STEP_RE = re.compile(
    r"^step\s*\d+\s*"        # "Step 3"
    r"(?:\(([^)]*)\))?"      # optional "(0.72)"
    r"\s*:\s*(.*)$",         # ": content"
    re.I,
)
_ANSWER_RE = re.compile(
    r"^(?:final\s+)?answer\s*:\s*(.*)$", re.I)
_CONF_RE = re.compile(r"([0-9]*\.?[0-9]+)\s*(%?)")


def _confidence(raw: str | None) -> float:
    """Read "0.72" or "72%" out of a step's rating.

    A rating outside 0.00-1.00 carrying no percent sign is
    off contract, and the scale intended for it cannot be
    recovered: "(7.5)" is likely seven and a half out of
    ten, and reading it as a percent would file a fairly
    confident step at 0.075 — bottom of the chain, and
    wrong, which sends verification after the wrong step.
    Unknown is the honest reading, so it lands at _UNRATED.
    """
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
    """Turn a model reply into structured ReasoningSteps.

    This is the other half of COT_SYSTEM_PROMPT's contract:
    the prompt asks for "Step N (0.72): ..." lines and an
    ANSWER: line, and this reads that shape back. Confidence
    survives the round trip, which is what lets weakest_step
    mean anything downstream.

    Nothing here raises. A model that ignores the format
    returns a chain with no steps and the whole reply as the
    answer — degraded, but callers already handle an empty
    chain (weakest_step returns None, so verification is
    skipped). Raising instead would turn a formatting wobble
    into a failed review.
    """
    chain = ChainOfThought()
    steps: list[tuple[float, list[str]]] = []
    answer: list[str] = []
    target: list[str] | None = None

    for raw in text.splitlines():
        line = raw.replace("**", "").strip()  # models bold
        if not line:
            continue
        step_match = _STEP_RE.match(line)
        if step_match:
            steps.append((_confidence(step_match.group(1)),
                          [step_match.group(2)]))
            target = steps[-1][1]
            continue
        answer_match = _ANSWER_RE.match(line)
        if answer_match:
            answer.append(answer_match.group(1))
            target = answer
            continue
        if target is not None:
            target.append(line)  # wrapped continuation
        # preamble before Step 1 is chatter; drop it

    for confidence, lines in steps:
        content = " ".join(x for x in lines if x).strip()
        if content:
            chain.add_step(content, confidence)

    chain.final_answer = " ".join(
        x for x in answer if x).strip()
    if not chain.final_answer:
        # A chain that stops at its last step has that step
        # as its conclusion; with nothing parsed at all, the
        # reply itself is the best answer available.
        chain.final_answer = (chain.steps[-1].content
                              if chain.steps else text.strip())
    return chain
