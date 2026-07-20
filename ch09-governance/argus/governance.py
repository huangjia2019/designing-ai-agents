# argus/governance.py — Argus governance layer, Ch9 snapshot.
#
# Tracks §9.8 'Argus checkpoint': Argus actions are now gated by an
# explicit permission check, every decision is audited, and trust
# accumulates / depletes based on outcomes.

from dataclasses import dataclass

from patterns.permission_gate import PermissionGate, AgentIdentity, Capability
from patterns.trust_levels import TrustEngine, TrustLevel, TrustState
from patterns.audit_log import AuditLog, AuditEntry
from patterns.policy_engine import PolicyEngine, PolicyRule
from patterns.governance_trace import GovernanceTrace, GovernanceEvent


@dataclass
class GovernanceDecision:
    allowed: bool
    decision: str   # "allow" | "deny" | "escalate"
    reason: str
    audit_entry: AuditEntry | None = None


class ArgusGovernance:
    """Argus's control plane: permission gates + trust + audit + policy."""

    AGENT = "argus"

    def __init__(self, initial_trust: TrustLevel = TrustLevel.ACT_THEN_REVIEW):
        self.permissions = PermissionGate()
        self.permissions.register(AgentIdentity(
            name=self.AGENT,
            capabilities={
                Capability.READ_FILES, Capability.RUN_LINT, Capability.RUN_TESTS,
            },
        ))
        # By default, Argus may NOT write files / fetch network without trust gain.
        self.trust = TrustEngine()
        self.trust.register(self.AGENT, initial=initial_trust)
        self.audit = AuditLog()
        self.policy = PolicyEngine()
        self.trace = GovernanceTrace()
        self._register_default_policy()

    def _register_default_policy(self) -> None:
        # Reject obvious destructive shell patterns at policy level.
        self.policy.add(PolicyRule(
            name="block_rm_rf",
            matcher=lambda agent, action, args: (
                action == "shell_exec"
                and any("rm -rf" in str(v) for v in args.values())
            ),
            decision="deny",
            reason="rm -rf disallowed by default policy",
        ))
        # Writes always need human approval at trust < FULL_AUTONOMY.
        self.policy.add(PolicyRule(
            name="writes_need_approval",
            matcher=lambda agent, action, args: action == "write_files",
            decision="escalate",
            reason="file writes require human approval below FULL_AUTONOMY",
        ))

    def authorize(self, action: str, cap: Capability,
                  args: dict | None = None) -> GovernanceDecision:
        """One-shot authorization: permission + policy + audit."""
        args = args or {}
        # 1. Permission check
        ok, reason = self.permissions.check(self.AGENT, cap)
        if not ok:
            entry = self.audit.record(
                actor=self.AGENT, action=action,
                decision="deny", reason=reason, **args,
            )
            self.trace.events.append(GovernanceEvent(
                timestamp=entry.timestamp, actor=self.AGENT,
                action=action, decision="deny", reason=reason,
            ))
            return GovernanceDecision(allowed=False, decision="deny",
                                      reason=reason, audit_entry=entry)
        # 2. Policy evaluation
        p_decision, p_reason, p_rule = self.policy.evaluate(self.AGENT, action, args)
        if p_decision != "allow":
            entry = self.audit.record(
                actor=self.AGENT, action=action,
                decision=p_decision, reason=f"{p_rule}: {p_reason}", **args,
            )
            self.trace.events.append(GovernanceEvent(
                timestamp=entry.timestamp, actor=self.AGENT,
                action=action, decision=p_decision,
                reason=f"{p_rule}: {p_reason}",
            ))
            return GovernanceDecision(allowed=False, decision=p_decision,
                                      reason=p_reason, audit_entry=entry)
        # 3. Allow + audit
        entry = self.audit.record(
            actor=self.AGENT, action=action,
            decision="allow", reason="permission ok, policy allow", **args,
        )
        return GovernanceDecision(allowed=True, decision="allow",
                                  reason="ok", audit_entry=entry)

    def report_outcome(self, success: bool, blocked: bool = False) -> tuple[TrustLevel, str]:
        """Update trust based on action result."""
        level, change = self.trust.update(
            self.AGENT,
            success=1 if success else 0,
            blocked=1 if blocked else 0,
            failed=0 if (success or blocked) else 1,
        )
        if change == "promoted":
            self.trace.promotions += 1
            # On promotion, grant a new capability.
            self.permissions.grant(self.AGENT, Capability.WRITE_FILES)
        elif change == "demoted":
            self.trace.demotions += 1
            self.permissions.revoke(self.AGENT, Capability.WRITE_FILES)
        return level, change

    def current_trust(self) -> TrustState:
        return self.trust.states[self.AGENT]
