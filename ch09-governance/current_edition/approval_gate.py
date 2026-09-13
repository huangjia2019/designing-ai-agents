"""Listings 9.1–9.4: classify proposed actions and route allow/deny/ask."""

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"

@dataclass
class ToolAction:
    tool_name: str
    arguments: dict
    reversible: bool = True
    risk_level: RiskLevel = field(
        init=False, default=RiskLevel.MEDIUM
    )

@dataclass
class ApprovalRule:
    pattern: str
    decision: Decision
    reason: str
class ApprovalGate:
    """Route every proposed action to allow, deny, or ask."""

    def __init__(self):
        self.deny_rules: list[ApprovalRule] = []
        self.allow_rules: list[ApprovalRule] = []
        self.audit_log: list[dict] = []

    def add_deny_rule(self, pattern: str, reason: str):
        self.deny_rules.append(
            ApprovalRule(pattern, Decision.DENY, reason)
        )

    def add_allow_rule(self, pattern: str, reason: str):
        self.allow_rules.append(
            ApprovalRule(pattern, Decision.ALLOW, reason)
        )
    def classify_risk(self, action: ToolAction) -> RiskLevel:
        """Classify action risk by external effect and tool type."""
        external_tools = {
            "send_email", "post_api", "deploy", "delete_database",
        }
        if action.tool_name in external_tools:
            return RiskLevel.CRITICAL
        if not action.reversible:
            return RiskLevel.HIGH

        read_only_tools = {
            "search", "read_file", "list_files", "grep"
        }
        if action.tool_name in read_only_tools:
            return RiskLevel.LOW
        write_tools = {"write_file", "edit_file", "create_file"}
        if action.tool_name in write_tools:
            return RiskLevel.MEDIUM
        exec_tools = {"run_command", "execute_code", "shell"}
        if action.tool_name in exec_tools:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    def _matches(self, pattern: str, tool_name: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return tool_name.startswith(pattern[:-1])
        return pattern == tool_name
    def evaluate(
        self, action: ToolAction,
    ) -> tuple[Decision, str]:
        """Evaluate action: deny -> allow -> ask."""
        action.risk_level = self.classify_risk(action)

        for rule in self.deny_rules:
            if self._matches(rule.pattern, action.tool_name):
                self._log(action, Decision.DENY, rule.reason)
                return Decision.DENY, rule.reason

        if action.risk_level is not RiskLevel.CRITICAL:
            for rule in self.allow_rules:
                if self._matches(rule.pattern, action.tool_name):
                    self._log(action, Decision.ALLOW, rule.reason)
                    return Decision.ALLOW, rule.reason

        if action.risk_level is RiskLevel.LOW:
            reason = "Auto-approved: low risk"
            self._log(action, Decision.ALLOW, reason)
            return Decision.ALLOW, reason

        reason = (
            f"Requires approval: {action.risk_level.value} risk"
        )
        self._log(action, Decision.ASK, reason)
        return Decision.ASK, reason

    def _log(
        self, action: ToolAction,
        decision: Decision, reason: str,
    ):
        self.audit_log.append({
            "tool": action.tool_name,
            "args": deepcopy(action.arguments),
            "risk": action.risk_level.value,
            "decision": decision.value,
            "reason": reason,
        })
