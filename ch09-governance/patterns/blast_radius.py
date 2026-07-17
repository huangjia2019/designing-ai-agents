import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxConfig:
    """Configuration for blast radius control.

    Each field maps to one containment layer:
    Layer 1 (capability), Layer 2 (isolation),
    Layer 3 (damage).
    """
    # Layer 1: Capability restriction
    allowed_paths: list[str] = field(
        default_factory=lambda: ["/workspace"]
    )
    blocked_paths: list[str] = field(
        default_factory=lambda: [
            "/etc", "/root", "/.ssh",
        ]
    )
    network_allowlist: list[str] = field(
        default_factory=lambda: [
            "api.anthropic.com",
        ]
    )
    allowed_tools: list[str] = field(
        default_factory=list
    )

    # Layer 2: Execution constraints
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    # Layer 3: Damage limitation
    max_actions_per_minute: int = 20
    max_cost_per_task_usd: float = 5.0
    time_lock_seconds: int = 0

class SandboxedExecutor:
    """Execute actions within blast radius
    controls.

    Implements Blast Radius Control
    (Governance × Hierarchy). Three nested
    containment layers ensure damage is bounded
    even when the agent is compromised.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.action_timestamps: list[float] = []
        self.cumulative_cost: float = 0.0

    def validate_path(
        self, path: str
    ) -> bool:
        """Layer 1: Check allowed/blocked."""
        resolved = str(Path(path).resolve())
        for blocked in self.config.blocked_paths:
            if resolved.startswith(blocked):
                return False
        for allowed in self.config.allowed_paths:
            if resolved.startswith(allowed):
                return True
        return False

    def check_rate_limit(self) -> bool:
        """Layer 3: Actions-per-minute limit."""
        now = time.time()
        self.action_timestamps = [
            t for t in self.action_timestamps
            if now - t < 60
        ]
        return (
            len(self.action_timestamps)
            < self.config.max_actions_per_minute
        )

    def check_budget(
        self, estimated_cost: float
    ) -> bool:
        """Layer 3: Per-task budget cap."""
        return (
            self.cumulative_cost + estimated_cost
            <= self.config.max_cost_per_task_usd
        )

    def execute(
        self, tool_name: str, args: dict,
        estimated_cost: float = 0.01,
        execute_fn=None,
    ) -> dict:
        """Execute within all controls."""

        # Layer 1: Capability check
        if (
            self.config.allowed_tools
            and tool_name
            not in self.config.allowed_tools
        ):
            return {
                "error": f"Tool '{tool_name}' "
                         f"not in allowlist"
            }

        if "path" in args:
            if not self.validate_path(
                args["path"]
            ):
                return {
                    "error": "Path outside sandbox"
                }

        # Layer 3: Rate limit
        if not self.check_rate_limit():
            return {"error": "Rate limit exceeded"}

        # Layer 3: Budget check
        if not self.check_budget(estimated_cost):
            return {"error": "Budget exceeded"}

        # Layer 3: Time lock
        if self.config.time_lock_seconds > 0:
            time.sleep(
                self.config.time_lock_seconds
            )

        # Execute within bounds
        self.action_timestamps.append(time.time())
        self.cumulative_cost += estimated_cost

        if execute_fn:
            return execute_fn(tool_name, args)
        return {
            "status": "executed",
            "tool": tool_name,
            "args": args,
        }
