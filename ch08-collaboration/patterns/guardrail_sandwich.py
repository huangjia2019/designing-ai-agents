"""Guardrail Sandwich — three safety layers around every action.

Book: Chapter 6, Listing 6.10 (SafetyPolicy), Listing 6.11 (the
execute_safely orchestrator), and Listing 6.12 (risk classification and
output redaction).

  Layer 1  Input filter    — classify risk, allow / block / route to human
  Layer 2  Sandbox         — run the tool
  Layer 3  Output filter   — redact sensitive patterns from the result

The gate pattern earns its keep when actions are irreversible — payments,
deployments, DB writes. Argus's code review is intentionally low-stakes for
pedagogy; the mechanism is the same regardless of stakes.
"""
import re
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyPolicy:
    """What the agent may do."""
    allowed_tools: list[str] = field(
        default_factory=list
    )
    blocked_patterns: list[str] = field(
        default_factory=list
    )
    auto_approve: list[RiskLevel] = (
        field(default_factory=lambda: [
            RiskLevel.LOW
        ])
    )
    require_human: list[RiskLevel] = (
        field(default_factory=lambda: [
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ])
    )
    sensitive_patterns: list[str] = (
        field(default_factory=lambda: [
            r"(?i)(password|secret|"
            r"api[_-]?key|token)"
            r"\s*[:=]\s*\S+",
            r"\b[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+"
            r"\.[A-Z|a-z]{2,}\b",
            r"\b\d{3}-\d{2}-\d{4}\b",
        ])
    )

    # --- Beyond Listing 6.10 ------------------------------------------
    # The book's _classify_risk (Listing 6.12) keys on generic tool names
    # (write_file, edit_file). A caller with its own vocabulary — Argus
    # calls its irreversible write `fix_apply` — needs a way to name tools
    # that always require a human, independent of keyword classification.
    require_human_tools: list[str] = field(
        default_factory=list
    )


class GuardrailSandwich:
    """Input filter, sandbox, output filter."""

    def __init__(
        self, policy: SafetyPolicy,
        human_fn: callable = None,
    ):
        self.policy = policy
        self.human_fn = (
            human_fn or (lambda *_: False)
        )

    def execute_safely(  # Orchestrates input, sandbox, output layers
        self, tool_name: str,
        arguments: dict,
        executor: callable,
    ) -> dict:
        # Layer 1: Input filter
        risk = self._classify_risk(
            tool_name, arguments
        )
        verdict = self._filter_input(
            tool_name, arguments, risk
        )
        if not verdict["approved"]:
            return {
                "executed": False,
                "blocked_by": "input_filter",
                **verdict,
            }

        # Layer 2: Execute in sandbox
        try:
            raw = executor(
                tool_name, arguments
            )
        except Exception as e:
            return {
                "executed": False,
                "blocked_by": "execution",
                "error": str(e),
            }

        # Layer 3: Output filter
        safe = self._filter_output(
            str(raw)
        )
        return {
            "executed": True,
            "risk_level": risk.value,
            "output": safe,
        }

    def _classify_risk(  # Maps tools and arguments to risk levels
        self, tool_name: str,
        arguments: dict,
    ) -> RiskLevel:
        args_str = str(arguments).lower()
        destructive = [
            "rm -rf", "drop table",
            "delete", "truncate",
        ]
        if any(
            d in args_str
            for d in destructive
        ):
            return RiskLevel.CRITICAL
        external = [
            "send_email",
            "post_message", "deploy",
        ]
        if (
            tool_name.lower() in external
            or "http" in args_str
        ):
            return RiskLevel.HIGH
        if tool_name.lower() in [
            "write_file", "edit_file",
        ]:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _filter_output(
        self, output: str,
    ):
        for pat in (
            self.policy.sensitive_patterns
        ):
            output = re.sub(
                pat, "[REDACTED]", output
            )
        return output

    # --- Beyond the printed listings ----------------------------------
    # execute_safely (Listing 6.11) calls _filter_input, which the chapter
    # references but does not print. It is Layer 1's decision procedure:
    # allow-list, then blocked patterns, then the risk thresholds the
    # policy declares for auto-approval versus human review.
    #
    # human_fn(tool_name, arguments) may return a bool or a verdict string
    # ("approved" / "approve" / "yes" to let the action through; anything
    # else declines). Listing 6.11's default — lambda *_: False — means an
    # unwired gate denies rather than waves through.
    def _filter_input(
        self, tool_name: str,
        arguments: dict,
        risk: RiskLevel,
    ) -> dict:
        policy = self.policy
        base = {"risk_level": risk.value}

        if (
            policy.allowed_tools
            and tool_name not in policy.allowed_tools
        ):
            return {
                **base, "approved": False,
                "reason": f"tool not allowed: {tool_name}",
            }

        args_str = str(arguments)
        for pat in policy.blocked_patterns:
            if re.search(pat, args_str):
                return {
                    **base, "approved": False,
                    "reason": f"blocked pattern: {pat}",
                }

        if (
            tool_name in policy.require_human_tools
            or risk in policy.require_human
        ):
            raw = self.human_fn(tool_name, arguments)
            if isinstance(raw, str):
                decision = raw
                approved = raw.strip().lower() in (
                    "approve", "approved", "yes",
                )
            else:
                decision = "approved" if raw else "rejected"
                approved = bool(raw)
            return {
                **base,
                "approved": approved,
                "human_decision": decision,
                "reason": (
                    "" if approved
                    else f"human declined: {decision}"
                ),
            }

        if risk in policy.auto_approve:
            return {**base, "approved": True, "reason": ""}

        return {
            **base, "approved": False,
            "reason": (
                f"risk {risk.value} is neither auto-approved "
                f"nor routed to a human"
            ),
        }
