"""Listings 9.16–9.17: compose the four governance patterns."""

import time
from copy import deepcopy

from .approval_gate import ApprovalGate, Decision, ToolAction
from .blast_radius import SandboxConfig, SandboxedExecutor
from .progressive_commitment import TrustLevel, TrustManager
from .observability_harness import AgentObserver


class ArgusGovernance:
    """A governance boundary for selected Argus tool calls."""

    def __init__(
        self,
        config: SandboxConfig | None = None,
        initial_trust: TrustLevel = TrustLevel.SUPERVISED,
    ):
        self.gate = ApprovalGate()
        self.gate.add_deny_rule(
            "git_force_push",
            "History rewrite is irreversible",
        )
        self.gate.add_allow_rule(
            "read_*", "Reads are reversible"
        )
        self.trust = TrustManager(
            initial_level=initial_trust
        )
        self.sandbox = SandboxedExecutor(
            config or SandboxConfig(
                allowed_paths=["."],
                allowed_tools=[
                    "read_file", "run_command", "edit_file",
                ],
            )
        )
        self.observer = AgentObserver("argus")
        self.trust_scope = "argus:repo_review"

    def start_review(self, pr: str):
        self.observer.start_trace(f"review {pr}")
        self.trust_scope = f"argus:repo_review:{pr}"
        self.sandbox.cumulative_cost = 0.0
    def run_tool(
        self, tool_name: str, args: dict,
        execute_fn, ask_human=None,
        cost: float = 0.01,
        review_context: dict | None = None,
    ) -> dict:
        """Gate -> trust -> policy envelope -> observe."""
        action = ToolAction(
            tool_name=tool_name, arguments=deepcopy(args)
        )
        decision, reason = self.gate.evaluate(action)
        self.observer.record_decision(
            tool_name, decision.value, reason,
            evidence_ref=(review_context or {}).get(
                "evidence_ref"
            ),
            context={"scope": self.trust_scope,
                     "policy_version": (review_context or {}).get(
                         "policy_version")},
        )
        if decision is Decision.DENY:
            return {"error": reason}

        if decision is Decision.ASK and (
            self.trust.should_ask_human(
                action.risk_level.value
            )
        ):
            required = {
                "objective", "target", "change",
                "evidence_ref", "policy_version",
            }
            if any(not (review_context or {}).get(k)
                   for k in required):
                self.observer.record_decision(
                    tool_name, "review_context_missing",
                    "Required approval evidence is absent",
                )
                return {"error": "Review context incomplete"}
            packet = {
                "tool": action.tool_name,
                "arguments": deepcopy(action.arguments),
                "risk": action.risk_level.value,
                "reversible": action.reversible,
                "policy_reason": reason,
                "context": deepcopy(review_context or {}),
            }
            reviewer_id = (
                ask_human(packet) if ask_human else None
            )
            if not isinstance(reviewer_id, str) or (
                not reviewer_id.strip()
            ):
                self.trust.record_action(
                    success=False, user_override=True
                )
                self.observer.record_decision(
                    tool_name, "declined", reason
                )
                return {"error": "Declined"}
            self.observer.record_decision(
                tool_name, "human_approved",
                f"{reason}; reviewer={reviewer_id}; "
                f"scope={self.trust_scope}",
            )
        elif decision is Decision.ASK:
            status = self.trust.get_status()
            self.observer.record_decision(
                tool_name, "approval_waived",
                f"{reason}; trust={status['level']}; "
                f"scope={self.trust_scope}",
            )
        start = time.time()
        result = self.sandbox.execute(
            tool_name, action.arguments, cost, execute_fn
        )
        ok = "error" not in result
        self.observer.record_tool_call(
            tool_name, ok,
            (time.time() - start) * 1000,
        )
        self.trust.record_action(success=ok)
        return result

    def finish_review(
        self, success: bool,
        human_override: bool = False,
    ) -> dict:
        self.observer.record_task_outcome(
            success, human_override
        )
        self.observer.finish_trace(success=success)
        return self.observer.get_dashboard()
