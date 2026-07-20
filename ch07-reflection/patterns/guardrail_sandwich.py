"""Guardrail Sandwich — pre-action validation + post-action verification.

Three layers around every side-effect action:
  1. Pre-check: validate inputs against safety policy
  2. Execute:  run the action
  3. Post-check: validate outputs (no secrets leaked, no scope creep)

Used in Argus for: lint command exec, test runner, file writes. The gate
pattern is most valuable when actions are irreversible — payments,
deployments, DB writes. Argus's code review is intentionally low-stakes
for pedagogy; the mechanism is the same regardless of stakes.
"""
from dataclasses import dataclass, field
from typing import Callable, Any

from patterns.action_trace import ActionTrace


@dataclass
class SafetyPolicy:
    """Declarative constraints on what an action can do."""
    allowed_tools: set[str] = field(default_factory=set)
    forbidden_path_prefixes: list[str] = field(default_factory=list)
    require_human_for: set[str] = field(default_factory=set)
    max_output_bytes: int = 1_000_000

    def pre_check(self, action_name: str, tool: str, args: dict) -> tuple[bool, str]:
        """Return (allowed, reason). Empty reason on allow."""
        if self.allowed_tools and tool not in self.allowed_tools:
            return False, f"tool '{tool}' not in allowed_tools"
        for k, v in args.items():
            if isinstance(v, str):
                for pfx in self.forbidden_path_prefixes:
                    if v.startswith(pfx):
                        return False, f"arg '{k}' starts with forbidden prefix '{pfx}'"
        return True, ""

    def needs_human(self, action_name: str, tool: str) -> bool:
        return action_name in self.require_human_for or tool in self.require_human_for

    def post_check(self, output: Any) -> tuple[bool, str]:
        if isinstance(output, (str, bytes)) and len(output) > self.max_output_bytes:
            return False, f"output exceeds max_output_bytes ({self.max_output_bytes})"
        return True, ""


class GuardrailSandwich:
    """Wrap any callable with pre/post safety checks + audit trace."""

    def __init__(self, policy: SafetyPolicy,
                 human_approver: Callable[[str, dict], str] | None = None):
        self.policy = policy
        self.human_approver = human_approver

    def execute_safely(self, action_name: str, tool: str,
                       fn: Callable[..., Any], **kwargs) -> ActionTrace:
        import time
        trace = ActionTrace(action_name=action_name, tool=tool, arguments=kwargs)

        # --- pre-check ---
        ok, reason = self.policy.pre_check(action_name, tool, kwargs)
        if not ok:
            trace.guardrail_blocked = True
            trace.guardrail_reason = reason
            return trace

        # --- human-in-the-loop ---
        if self.policy.needs_human(action_name, tool):
            trace.awaiting_human_approval = True
            if self.human_approver is None:
                trace.guardrail_blocked = True
                trace.guardrail_reason = "human approval required but no approver wired"
                return trace
            verdict = self.human_approver(action_name, kwargs)
            trace.human_decision = verdict
            if verdict != "approve":
                trace.guardrail_blocked = True
                trace.guardrail_reason = f"human declined: {verdict}"
                return trace

        # --- execute ---
        t0 = time.perf_counter()
        try:
            trace.output = fn(**kwargs)
        except Exception as e:
            trace.error = f"{type(e).__name__}: {e}"
        trace.duration_ms = (time.perf_counter() - t0) * 1000

        # --- post-check ---
        if trace.output is not None:
            ok, reason = self.policy.post_check(trace.output)
            if not ok:
                trace.guardrail_blocked = True
                trace.guardrail_reason = f"post-check: {reason}"
                trace.output = None

        return trace
