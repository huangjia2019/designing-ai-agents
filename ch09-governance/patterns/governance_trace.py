"""GovernanceTrace — audit-grade record of trust + permission decisions."""
from dataclasses import dataclass, field


@dataclass
class GovernanceEvent:
    timestamp: float
    actor: str        # which agent/sub-agent
    action: str       # which capability
    decision: str     # "allow" | "deny" | "escalate"
    reason: str = ""
    trust_before: float = 0.0
    trust_after: float = 0.0


@dataclass
class GovernanceTrace:
    events: list[GovernanceEvent] = field(default_factory=list)
    promotions: int = 0
    demotions: int = 0
