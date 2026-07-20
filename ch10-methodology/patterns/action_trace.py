"""ActionTrace — observable record of one agent action.

Every Action that has side effects (writes a file, runs a command, calls a
remote API) emits an ActionTrace. Production agents use these for audit
logs, replay, and post-incident analysis.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionTrace:
    """One action's auditable record. Designed for Append-only audit storage."""

    # What the agent decided to do.
    action_name: str
    tool: str = ""
    arguments: dict = field(default_factory=dict)

    # Guardrail decision (gate before execution).
    guardrail_blocked: bool = False
    guardrail_reason: str = ""

    # Human-in-the-loop (per Ch6 Willem comment).
    awaiting_human_approval: bool = False
    human_decision: str | None = None

    # Execution outcome.
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0

    # Trust accounting (used by Ch9 governance).
    trust_consumed: float = 0.0
