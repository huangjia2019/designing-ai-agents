"""Listings 9.5–9.7: a host-side policy envelope, not an OS sandbox."""

import time
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class SandboxConfig:
    # Policy envelope enforced by this teaching executor
    allowed_paths: list[str] = field(
        default_factory=lambda: ["/workspace"]
    )
    blocked_paths: list[str] = field(
        default_factory=lambda: ["/etc", "/root", "/.ssh"]
    )
    allowed_tools: list[str] = field(default_factory=list)
    max_actions_per_minute: int = 20
    max_cost_per_task_usd: float = 5.0
    time_lock_seconds: int = 0

    # The supplied runtime adapter must enforce these
    network_allowlist: list[str] = field(
        default_factory=lambda: ["api.anthropic.com"]
    )
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512
class SandboxedExecutor:
    """Enforce a policy envelope around a supplied runtime."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self.action_timestamps: list[float] = []
        self.cumulative_cost: float = 0.0

    @staticmethod
    def _within(candidate: Path, root: Path) -> bool:
        return candidate == root or candidate.is_relative_to(root)

    def validate_path(self, path: str) -> bool:
        candidate = Path(path).resolve()
        blocked = [Path(p).resolve() for p in self.config.blocked_paths]
        if any(self._within(candidate, root) for root in blocked):
            return False
        allowed = [Path(p).resolve() for p in self.config.allowed_paths]
        return any(self._within(candidate, root) for root in allowed)

    def check_rate_limit(self) -> bool:
        now = time.time()
        self.action_timestamps = [
            t for t in self.action_timestamps if now - t < 60
        ]
        return (
            len(self.action_timestamps)
            < self.config.max_actions_per_minute
        )

    def check_budget(self, estimated_cost: float) -> bool:
        return (
            0 <= estimated_cost < float("inf")
            and self.cumulative_cost + estimated_cost
            <= self.config.max_cost_per_task_usd
        )
    def execute(
        self, tool_name: str, args: dict,
        estimated_cost: float = 0.01,
        execute_fn=None,
    ) -> dict:
        """Check the envelope, then invoke the supplied runtime."""
        if (
            self.config.allowed_tools
            and tool_name not in self.config.allowed_tools
        ):
            return {"error": f"Tool '{tool_name}' not in allowlist"}

        path_keys = ("path", "file_path", "cwd", "repo", "repo_root")
        for key in path_keys:
            if key in args and not self.validate_path(args[key]):
                return {"error": f"{key} outside policy boundary"}

        if not self.check_rate_limit():
            return {"error": "Rate limit exceeded"}
        if not self.check_budget(estimated_cost):
            return {"error": "Budget exceeded"}

        if self.config.time_lock_seconds > 0:
            time.sleep(self.config.time_lock_seconds)

        self.action_timestamps.append(time.time())
        self.cumulative_cost += estimated_cost
        if execute_fn:
            return execute_fn(tool_name, args)
        return {"status": "checked", "tool": tool_name, "args": args}
