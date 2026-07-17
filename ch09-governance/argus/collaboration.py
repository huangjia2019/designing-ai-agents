# argus/collaboration.py — Argus collaboration module, Ch8 snapshot.
#
# Tracks §8.8 'Argus checkpoint': Argus dispatches review subtasks
# (security, style, complexity) to specialist sub-agents in parallel,
# then synthesizes their findings into one verdict. High-stakes individual
# claims can be routed through Adversarial Review.
#
# Thin facade over the Ch8 patterns:
#   * Fan-Out/Gather   (Listings 8.4-8.7) — patterns/fan_out_gather.py
#   * Adversarial Review (Listings 8.8-8.10) — patterns/adversarial_review.py
#   * CollaborationTrace (Listing 8.1) — patterns/collaboration_trace.py
#
# Offline-safe: with no client supplied, a stub client answers the same
# `messages.create(...)` interface the patterns call, so the real
# FanOutGather / AdversarialReview code paths still run without an API key.
import time
from types import SimpleNamespace

from patterns.fan_out_gather import FanOutGather
from patterns.adversarial_review import AdversarialReview, DebateResult
from patterns.collaboration_trace import CollaborationTrace

PERSPECTIVES = ["security", "style", "complexity"]


class _StubClient:
    """Minimal stand-in for `Anthropic`, routing to pluggable callables.

    The patterns call `client.messages.create(model=..., system=...,
    messages=[...])` and read `response.content[0].text`. This satisfies
    that contract and dispatches on the system prompt, so the demo
    exercises the genuine fan-out and gather logic offline.
    """

    def __init__(self, handlers: dict):
        self._handlers = handlers
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, model=None, max_tokens=None, system=None,
                messages=None, **kwargs):
        prompt = messages[0]["content"] if messages else ""
        system = system or ""
        for key, handler in self._handlers.items():
            if key in system:
                return SimpleNamespace(
                    content=[SimpleNamespace(text=handler(prompt))]
                )
        return SimpleNamespace(
            content=[SimpleNamespace(text="[stub] no handler matched")]
        )


class ArgusCollaboration:
    """Argus's parallel review dispatch + synthesis layer."""

    def __init__(self, client=None, security_agent=None, style_agent=None,
                 complexity_agent=None, lead_synth=None,
                 proponent_agent=None, reviewer_agent=None, judge_agent=None):
        # Each sub-agent is a pluggable callable: role-specific LLM prompts in
        # production, deterministic stubs for offline demos.
        self._handlers = {
            "expert in security": security_agent or self._default_security,
            "expert in style": style_agent or self._default_style,
            "expert in complexity": complexity_agent or self._default_complexity,
            "Synthesize multiple expert": lead_synth or self._default_lead,
            # Adversarial Review roles (Listing 8.9's three system prompts).
            "You are the PROPONENT": proponent_agent or self._default_proponent,
            "You are the REVIEWER": reviewer_agent or self._default_reviewer,
            "You are the JUDGE": judge_agent or self._default_judge,
        }
        self._client = client or _StubClient(self._handlers)
        self.fan = FanOutGather(self._client)
        self.trace = CollaborationTrace(
            task_id="argus-review",
            topology="fan-out/gather",
        )

    def parallel_review(self, diff: str) -> str:
        """Fan out to the three specialists, then synthesize (Listings 8.4-8.7)."""
        started = time.perf_counter()
        tasks = self.fan.decompose(diff, PERSPECTIVES)
        results = self.fan.fan_out(tasks)
        synthesis = self.fan.gather(diff, results, strategy="synthesize")

        self.trace.agent_count += len(results)
        self.trace.handoff_count += len(results)
        self.trace.handoff_failures += sum(
            1 for r in results if r.status == "failed"
        )
        # A single-agent baseline would have read the diff once; the fan-out
        # reads it once per worker plus the aggregator pass.
        self.trace.single_agent_estimate += len(diff)
        self.trace.total_tokens += (
            sum(len(r.description) + len(r.result) for r in results)
            + len(synthesis)
        )
        self.trace.wall_time_ms += int(
            (time.perf_counter() - started) * 1000
        )
        return synthesis

    def adversarial_check(self, claim: str, num_rounds: int = 2) -> DebateResult:
        """Optional adversarial pass on a specific claim (Listings 8.8-8.10)."""
        reviewer = AdversarialReview(
            self._client, num_rounds=num_rounds
        )
        result = reviewer.debate(claim)
        self.trace.conflicts_detected += len(result.rounds)
        if result.winning_position == "reviewer":
            self.trace.conflicts_resolved += 1
        return result

    # --- default stubs (replace with LLM-backed callables in production) ---
    def _default_security(self, prompt: str) -> str:
        return "[security] No obvious vulnerabilities surfaced by static patterns."

    def _default_style(self, prompt: str) -> str:
        return "[style] Conforms to PEP 8; comment density adequate."

    def _default_complexity(self, prompt: str) -> str:
        lines = prompt.count("\n")
        verdict = "high" if lines > 200 else "moderate" if lines > 50 else "low"
        return f"[complexity] Diff complexity: {verdict} ({lines} lines)."

    def _default_lead(self, prompt: str) -> str:
        return "[lead synthesis] Parallel review complete; see sub-agent findings."

    def _default_proponent(self, prompt: str) -> str:
        return "[proponent] The claim holds: the diff adds no new attack surface."

    def _default_reviewer(self, prompt: str) -> str:
        return "[reviewer] Objection: the claim rests on untested error paths."

    def _default_judge(self, prompt: str) -> str:
        # Shaped so Listing 8.10's keyed-line parser has something to parse.
        return (
            "VERDICT: The claim survives, narrowed to the tested paths.\n"
            "WINNER: proponent\n"
            "CONFIDENCE: 0.72"
        )
