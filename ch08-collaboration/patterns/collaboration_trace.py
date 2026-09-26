"""CollaborationTrace — observable record of multi-agent coordination.

Listing 8.1 — the four metrics that decide whether a multi-agent topology
is earning its keep: token multiplier, handoff fidelity, conflict count,
and wall time.
"""
from dataclasses import dataclass


@dataclass
class CollaborationTrace:
    task_id: str
    topology: str
    agent_count: int = 0
    total_tokens: int = 0
    single_agent_estimate: int = 0
    handoff_count: int = 0
    handoff_failures: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    wall_time_ms: int = 0

    @property
    def token_multiplier(self) -> float:
        if self.single_agent_estimate == 0:
            return 0
        return (
            self.total_tokens
            / self.single_agent_estimate
        )

    @property
    def handoff_fidelity(self) -> float:
        if self.handoff_count == 0:
            return 1.0
        return 1.0 - (
            self.handoff_failures
            / self.handoff_count
        )

    def log(self):
        mult = self.token_multiplier
        fid = self.handoff_fidelity
        print(
            f"  [{self.task_id}] "
            f"{self.topology} "
            f"agents={self.agent_count} "
            f"tokens={mult:.1f}x "
            f"fidelity={fid:.0%} "
            f"conflicts="
            f"{self.conflicts_detected} "
            f"time={self.wall_time_ms}ms"
        )


if __name__ == "__main__":
    # A fan-out of 3 workers costing 4.2x the single-agent baseline,
    # with one handoff dropped along the way.
    trace = CollaborationTrace(
        task_id="review-1042",
        topology="fan-out/gather",
        agent_count=3,
        total_tokens=42_000,
        single_agent_estimate=10_000,
        handoff_count=3,
        handoff_failures=1,
        conflicts_detected=2,
        conflicts_resolved=2,
        wall_time_ms=1830,
    )
    trace.log()
