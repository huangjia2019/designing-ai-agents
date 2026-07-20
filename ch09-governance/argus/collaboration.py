# argus/collaboration.py — Argus collaboration module, Ch8 snapshot.
#
# Tracks §8.8 'Argus checkpoint': Argus dispatches review subtasks
# (security, style, complexity) to specialist sub-agents in parallel,
# then synthesizes their findings into one verdict.
from dataclasses import dataclass

from patterns.fan_out_gather import SubAgent, fan_out_gather, synthesize
from patterns.adversarial_review import adversarial_review, AdversarialVerdict
from patterns.collaboration_trace import CollaborationTrace, AgentMessage


@dataclass
class SubReview:
    perspective: str  # 'security' | 'style' | 'complexity'
    findings: str


class ArgusCollaboration:
    """Argus's parallel review dispatch + synthesis layer."""

    def __init__(self, security_agent=None, style_agent=None, complexity_agent=None,
                 lead_synth=None):
        # Default sub-agent callables. In production they call the LLM with
        # role-specific system prompts; in the demo we provide fast stubs.
        self.subs = [
            SubAgent(name="security", role="security",
                     invoke=security_agent or self._default_security),
            SubAgent(name="style", role="style",
                     invoke=style_agent or self._default_style),
            SubAgent(name="complexity", role="complexity",
                     invoke=complexity_agent or self._default_complexity),
        ]
        self._lead = lead_synth or self._default_lead
        self.trace = CollaborationTrace()

    def parallel_review(self, diff: str) -> str:
        sub_results = fan_out_gather(self.subs, diff)
        self.trace.parallel_calls += len(sub_results)
        for name, content in sub_results.items():
            self.trace.messages.append(AgentMessage(
                sender=name, recipient="lead", content=content[:200],
            ))
        return synthesize(self._lead, diff, sub_results)

    def adversarial_check(self, claim: str, refuters: list = None) -> AdversarialVerdict:
        """Optional adversarial check on a specific claim from the review."""
        refuters = refuters or [self._default_refuter] * 3
        return adversarial_review(claim, refuters, refute_majority=2)

    # --- default stubs (replace with LLM-backed callables in production) ---
    def _default_security(self, diff: str) -> str:
        return "[security] No obvious vulnerabilities surfaced by static patterns."

    def _default_style(self, diff: str) -> str:
        return "[style] Conforms to PEP 8; comment density adequate."

    def _default_complexity(self, diff: str) -> str:
        lines = diff.count("\n")
        verdict = "high" if lines > 200 else "moderate" if lines > 50 else "low"
        return f"[complexity] Diff complexity: {verdict} ({lines} lines)."

    def _default_lead(self, prompt: str) -> str:
        return f"[lead synthesis] Parallel review complete; see sub-agent findings."

    def _default_refuter(self, claim: str) -> str:
        return "survived"
