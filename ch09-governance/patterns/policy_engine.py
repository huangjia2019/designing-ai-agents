"""Policy Engine — declarative rules over the agent's capability surface.

Rules are evaluated at every action attempt. The engine returns
allow/deny/escalate, plus a reason that propagates to the audit log.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PolicyRule:
    name: str
    matcher: Callable[[str, str, dict], bool]   # (agent, action, args) -> matches?
    decision: str                                # "allow" | "deny" | "escalate"
    reason: str = ""


class PolicyEngine:
    """Evaluates rules in declaration order; first match wins."""

    def __init__(self):
        self.rules: list[PolicyRule] = []

    def add(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(self, agent: str, action: str,
                 args: dict | None = None) -> tuple[str, str, str | None]:
        """Return (decision, reason, matched_rule_name)."""
        args = args or {}
        for rule in self.rules:
            if rule.matcher(agent, action, args):
                return rule.decision, rule.reason, rule.name
        return "allow", "no rule matched (default allow)", None
