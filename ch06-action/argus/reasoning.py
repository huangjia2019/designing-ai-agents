# argus/reasoning.py — Argus reasoning module, Ch5 snapshot.
#
# Replaces the Ch5 listing fragments (free-floating defs) with a proper
# ArgusReasoning class that integrates the three reasoning patterns from
# this chapter:
#   * complexity_routing — pick model + token budget by task complexity
#   * chain_of_thought    — generate a CoT with confidence-tagged steps
#   * verify_chain        — re-check the weakest step
#
# The class is constructed once per Argus instance and decides, for each
# review request, whether to do a quick single-pass or a multi-step
# reasoning trace.
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field

from patterns.complexity_routing import classify_complexity, Complexity, ROUTING_TABLE
from patterns.chain_of_thought import (
    ChainOfThought,
    reason_with_cot,
    verify_chain,
)
from patterns.hypothesis_testing import HypothesisTester


REVISE_STEP_PROMPT = """A verifier flagged one step of a reasoning chain as invalid.
Rewrite ONLY that step. Leave every other step alone — they are not yours to touch.

Steps already accepted (context; do not restate or amend them):
{prior}

Flawed step {step_number} (self-assessed confidence {confidence:.2f}):
{content}

The verifier's objection:
{issue}

Reply in exactly this format:
REVISED: <the corrected step, one paragraph>
CONFIDENCE: <0.0-1.0, your honest confidence in the corrected step>
"""

REDERIVE_ANSWER_PROMPT = """A reasoning chain was repaired after verification. Re-state
the conclusion so that it follows from the steps as they now stand.

{steps}

The previous conclusion, drawn before the repair and possibly stale:
{old_answer}

Reply with the conclusion only.
"""

# Command heads a hypothesis test may run. See run_in_sandbox().
_ALLOWED_COMMANDS = frozenset({
    "cat", "find", "git", "grep", "head", "ls", "pytest",
    "python", "python3", "rg", "tail", "wc",
})
_ALLOWED_GIT_SUBCOMMANDS = frozenset({
    "blame", "diff", "grep", "log", "show", "status",
})
_MAX_OUTPUT_CHARS = 4000


def run_in_sandbox(cmd: str, repo_path: str, timeout: int = 30) -> str:
    """Run one hypothesis-test command against a checkout and return what it printed.

    What this contains: an allowlist of command heads, so a hypothesis test cannot
    reach for `rm` or `curl`; no shell, so `;` and `|` and `$(...)` arrive as inert
    argument text rather than operators; a working directory pinned to repo_path; a
    wall-clock timeout; and truncated output, so one chatty test cannot eat the
    context budget.

    What this does NOT contain: filesystem, network, or process isolation. `pytest`
    and `python` are on the allowlist because verifying a bug means running the
    suite, and either one can execute arbitrary code inside repo_path. This is a
    guard rail, not a jail, and the name is aspirational. Chapter 9 replaces it with
    SandboxedExecutor, which is the actual Blast Radius Control boundary. What Ch5
    needs from it is narrower: execute_fn is where reasoning touches the world, so
    execute_fn is the trust boundary — the point survives the crude implementation.

    Returns text on every path and raises nothing: HypothesisTester._analyze reads
    this return value as evidence, and a refusal is evidence too.
    """
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return f"[refused] unparseable command: {exc}"
    if not argv:
        return "[refused] empty command"

    head = os.path.basename(argv[0])
    if head not in _ALLOWED_COMMANDS:
        return (f"[refused] {head!r} is not on the hypothesis-test allowlist; "
                f"allowed: {', '.join(sorted(_ALLOWED_COMMANDS))}")
    if head == "git":
        sub = argv[1] if len(argv) > 1 else ""
        if sub not in _ALLOWED_GIT_SUBCOMMANDS:
            return (f"[refused] git {sub!r} may write; allowed subcommands: "
                    f"{', '.join(sorted(_ALLOWED_GIT_SUBCOMMANDS))}")

    try:
        proc = subprocess.run(
            argv,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"[timeout] no result after {timeout}s"
    except OSError as exc:
        return f"[error] {exc}"

    output = (proc.stdout + proc.stderr).strip()
    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n[...truncated]"
    if not output:
        return f"[exit {proc.returncode}] (no output)"
    return f"[exit {proc.returncode}]\n{output}"


def _parse_revision(text: str) -> tuple[str | None, float | None]:
    """Pull REVISED:/CONFIDENCE: out of a reviser's reply.

    Returns (None, None) when the reply carries no REVISED: block. The caller then
    keeps the original step: an unparseable reply is a failed repair, and a failed
    repair should look like one rather than overwrite a step with prose.
    """
    match = re.search(r"REVISED:\s*(.+?)(?=\nCONFIDENCE:|\Z)", text, re.S)
    if not match:
        return None, None
    content = match.group(1).strip()
    confidence = None
    conf_match = re.search(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", text)
    if conf_match:
        confidence = max(0.0, min(1.0, float(conf_match.group(1))))
    return (content or None), confidence


@dataclass
class ReviewResult:
    """The output of a reasoned review — carries the chain, not just the verdict."""
    verdict: str
    reasoning_steps: list = field(default_factory=list)
    confidence: float = 1.0
    complexity: str = "simple"


class ArgusReasoning:
    """Argus's reasoning layer: complexity-routed + CoT + verify."""

    def __init__(self, client=None):
        # client is lazy so the class is importable without anthropic installed.
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def review(self, diff: str) -> ReviewResult:
        """Route the review by complexity, then reason at the right depth."""
        complexity = classify_complexity(
            self.client,
            f"Code review task:\n{diff[:500]}",
        )
        if complexity == Complexity.SIMPLE:
            return self.quick_review(diff)
        if complexity == Complexity.MODERATE:
            return self.review_with_reasoning(diff, complexity)
        return self.deep_review(diff)

    def quick_review(self, diff: str) -> ReviewResult:
        """One pass, cheap model, structured output. Used when classifier says SIMPLE."""
        cfg = ROUTING_TABLE[Complexity.SIMPLE]
        response = self.client.messages.create(
            model=cfg["model"],
            max_tokens=cfg["max_tokens"],
            messages=[{
                "role": "user",
                "content": f"Quick code review:\n{diff}\n\nList up to 3 issues, severity-tagged.",
            }],
        )
        return ReviewResult(
            verdict=response.content[0].text,
            reasoning_steps=[],
            confidence=0.8,
            complexity="simple",
        )

    def review_with_reasoning(self, diff: str, complexity: Complexity) -> ReviewResult:
        """CoT review with weak-step verification."""
        chain = reason_with_cot(
            self.client,
            f"Review this code diff for bugs, security issues, and style problems:\n{diff}",
        )
        if chain.weakest_step:
            issues = verify_chain(self.client, chain)
            if issues:
                chain = self.revise_chain(chain, issues)
        confidence = (
            min(s.confidence for s in chain.steps)
            if chain.steps else 0.5
        )
        return ReviewResult(
            verdict=chain.final_answer,
            reasoning_steps=chain.steps,
            confidence=confidence,
            complexity=complexity.value,
        )

    def revise_chain(self, chain: ChainOfThought, issues: list[dict]) -> ChainOfThought:
        """Repair only the steps the verifier flagged, then re-derive the conclusion.

        `issues` is what verify_chain() returns: [{"step": <step_number>, "issue":
        <verifier's text>}, ...]. Any step whose number is absent from that list is
        left byte-identical. That is the entire point of the pattern: a flagged step
        is cheap to repair, a chain is expensive to regenerate, and regenerating one
        would throw away the steps that survived verification along with the audit
        trail attached to them. Steps are repaired lowest-numbered first, so a step
        being rewritten sees its predecessors in their final, repaired form.

        Mutates and returns the same chain object, matching the caller's
        `chain = self.revise_chain(chain, issues)`.
        """
        flagged: dict[int, list[str]] = {}
        for issue in issues:
            flagged.setdefault(issue["step"], []).append(issue["issue"])
        if not flagged:
            return chain

        by_number = {s.step_number: s for s in chain.steps}
        revised: list[int] = []
        for number in sorted(flagged):
            step = by_number.get(number)
            if step is None:
                continue  # verifier cited a step that is not in this chain
            prior = "\n".join(
                f"Step {s.step_number}: {s.content}"
                for s in chain.steps if s.step_number < number
            )
            response = self.client.messages.create(
                model=ROUTING_TABLE[Complexity.MODERATE]["model"],
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": REVISE_STEP_PROMPT.format(
                        prior=prior or "(none — this is the first step)",
                        step_number=number,
                        confidence=step.confidence,
                        content=step.content,
                        issue="\n".join(flagged[number]),
                    ),
                }],
            )
            content, confidence = _parse_revision(response.content[0].text)
            if content is None:
                continue  # unparseable reply: keep the step, do not fake a repair
            step.content = content
            if confidence is not None:
                step.confidence = confidence
            revised.append(number)

        if revised:
            chain.final_answer = self._rederive_answer(chain)
        return chain

    def _rederive_answer(self, chain: ChainOfThought) -> str:
        """Re-state the conclusion after a repair.

        A conclusion drawn from the broken version of a step does not survive that
        step being fixed, so it is re-stated from the repaired chain. This is one
        extra call, not a regeneration: the steps are inputs here, not outputs.
        """
        steps = "\n".join(
            f"Step {s.step_number} (confidence {s.confidence:.2f}): {s.content}"
            for s in chain.steps
        )
        response = self.client.messages.create(
            model=ROUTING_TABLE[Complexity.MODERATE]["model"],
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": REDERIVE_ANSWER_PROMPT.format(
                    steps=steps,
                    old_answer=chain.final_answer or "(none)",
                ),
            }],
        )
        return response.content[0].text.strip()

    def verify_bug(self, suspicion: str, repo_path: str):
        """Investigate a suspected bug by running experiments against a real checkout.

        Returns the evidence trail, not a yes/no: a verdict a reviewer cannot audit
        is worth about as much as the suspicion it started from.
        """
        tester = HypothesisTester(
            client=self.client,
            execute_fn=lambda cmd: run_in_sandbox(cmd, repo_path),
            max_iterations=5,
        )
        return tester.investigate(
            f"Verify whether this is a real bug: {suspicion}"
        )

    def deep_review(self, diff: str) -> ReviewResult:
        """COMPLEX path: use the highest reasoning tier from ROUTING_TABLE."""
        cfg = ROUTING_TABLE[Complexity.COMPLEX]
        kwargs = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [{
                "role": "user",
                "content": (
                    f"Deep code review. Walk through reasoning step by step.\n\n{diff}"
                ),
            }],
        }
        if cfg.get("thinking"):
            kwargs["thinking"] = cfg["thinking"]
        response = self.client.messages.create(**kwargs)
        return ReviewResult(
            verdict=response.content[0].text,
            reasoning_steps=[],
            confidence=0.9,
            complexity="complex",
        )
