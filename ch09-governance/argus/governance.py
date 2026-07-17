# argus/governance.py — Argus governance layer, Ch9 snapshot.
#
# Listings 9.16-9.17 (§9.8 'The Argus checkpoint'): one control plane holding
# one instance of each of the four governance patterns. Every tool call
# goes through run_tool() in a fixed order:
#
#   gate (allow/deny/ask) -> trust (does ask still need a human?)
#     -> sandbox (bound the damage) -> observer (record the evidence)
#
# The class body below is Listings 9.16-9.17 verbatim; the imports are
# the repo-side wiring the book listings elide.

import time

from patterns.approval_gate import (
    ApprovalGate, Decision, ToolAction,
)
from patterns.blast_radius import (
    SandboxConfig, SandboxedExecutor,
)
from patterns.progressive_commitment import (
    TrustLevel, TrustManager,
)
from patterns.observability_harness import (
    AgentObserver,
)


class ArgusGovernance:
    """Argus's control plane: one chokepoint,
    all four governance patterns."""

    def __init__(
        self,
        config: SandboxConfig | None = None,
        initial_trust: TrustLevel = (
            TrustLevel.SUPERVISED
        ),
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
            config
            or SandboxConfig(
                allowed_tools=[
                    "read_file", "run_command",
                    "edit_file",
                ]
            )
        )
        self.observer = AgentObserver("argus")

    def start_review(self, pr: str):
        self.observer.start_trace(f"review {pr}")

    def run_tool(
        self, tool_name: str, args: dict,
        execute_fn, ask_human=None,
        cost: float = 0.01,
    ) -> dict:
        """Gate -> trust -> sandbox -> observe."""
        action = ToolAction(
            tool_name=tool_name, arguments=args
        )
        decision, reason = self.gate.evaluate(
            action
        )
        if decision is Decision.DENY:
            return {"error": reason}

        if decision is Decision.ASK and (
            self.trust.should_ask_human(
                action.risk_level.value
            )
        ):
            if not (
                ask_human
                and ask_human(action, reason)
            ):
                self.trust.record_action(
                    success=False,
                    user_override=True,
                )
                return {"error": "Declined"}

        start = time.time()
        result = self.sandbox.execute(
            tool_name, args, cost, execute_fn
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
        return self.observer.get_dashboard()
