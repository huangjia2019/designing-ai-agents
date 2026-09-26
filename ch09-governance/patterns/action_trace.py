"""ActionTrace — observable record of one agent action.

Book: Chapter 6, Listing 6.1.

Every Action that has side effects (writes a file, runs a command, calls a
remote API) emits an ActionTrace. Production agents use these for audit
logs, replay, and post-incident analysis.

The dataclass below is Listing 6.1. A short block of payload fields is
appended after `planned` — see the comment there for why.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionTrace:
    """Observable record of action decisions."""
    action_id: str
    tool_name: str
    risk_level: str                       # Guardrail's risk classification
    arguments_repaired: bool = False
    guardrail_blocked: bool = False
    guardrail_reason: str = ""
    awaiting_human_approval: bool = False  # True while paused for a reviewer
    human_decision: str | None = None      # "approved", "rejected", "edited"
    success: bool = False
    retry_count: int = 0                   # Non-zero retries signal arg issues
    wall_time_ms: int = 0
    tokens_used: int = 0
    planned: bool = True                   # Planned vs. emergent actions

    # --- Beyond Listing 6.1 -------------------------------------------
    # The book prints ActionTrace as a pure metrics record. The cumulative
    # Argus facade (argus/action.py, argus/core.py, argus/cli.py) also has
    # to carry the call's payload, so these four fields are appended here.
    # Everything above this line is exactly what Listing 6.1 shows.
    arguments: dict = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    trust_consumed: float = 0.0            # read by Ch9 governance

    def log(self):
        status = (
            "OK" if self.success else "FAIL"
        )
        flags = []
        if self.arguments_repaired:
            flags.append("repaired")
        if self.guardrail_blocked:
            flags.append(
                f"blocked:"
                f"{self.guardrail_reason}"
            )
        if self.awaiting_human_approval:
            flags.append("awaiting_human")
        if self.human_decision:
            flags.append(
                f"human:{self.human_decision}"
            )
        if not self.planned:
            flags.append("UNPLANNED")
        flag_str = (
            f" [{', '.join(flags)}]"
            if flags else ""
        )
        print(
            f"  [{self.action_id}] "
            f"{self.tool_name} "
            f"risk={self.risk_level} "
            f"{status} "
            f"retries={self.retry_count} "
            f"time={self.wall_time_ms}ms"
            f"{flag_str}"
        )
