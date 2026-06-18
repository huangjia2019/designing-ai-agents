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
from dataclasses import dataclass, field

from patterns.complexity_routing import classify_complexity, Complexity, ROUTING_TABLE
from patterns.chain_of_thought import (
    ChainOfThought,
    reason_with_cot,
    verify_chain,
)


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
            return self._quick_review(diff)
        if complexity == Complexity.MODERATE:
            return self._review_with_reasoning(diff, complexity)
        return self._deep_review(diff)

    def _quick_review(self, diff: str) -> ReviewResult:
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

    def _review_with_reasoning(self, diff: str, complexity: Complexity) -> ReviewResult:
        """CoT review with weak-step verification."""
        chain = reason_with_cot(
            self.client,
            f"Review this code diff for bugs, security issues, and style problems:\n{diff}",
        )
        if chain.weakest_step:
            issues = verify_chain(self.client, chain)
            if issues:
                # In production we'd revise the chain; for the chapter demo we
                # just record the verification round and emit a lower confidence.
                chain.final_answer += f"\n\n[Verifier flagged: {len(issues)} issue(s)]"
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

    def _deep_review(self, diff: str) -> ReviewResult:
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
