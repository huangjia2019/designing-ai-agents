"""Same-task baseline and collaboration trace metrics."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class RunSample:
    tokens: int
    latency_ms: int
    quality: float


@dataclass(frozen=True)
class SingleAgentBaseline:
    runs: int
    average_tokens: float
    average_latency_ms: float
    average_quality: float

    @classmethod
    def from_runs(
        cls,
        samples: list[RunSample],
    ) -> "SingleAgentBaseline":
        if not samples:
            raise ValueError("At least one baseline run is required")
        return cls(
            runs=len(samples),
            average_tokens=mean(run.tokens for run in samples),
            average_latency_ms=mean(
                run.latency_ms for run in samples
            ),
            average_quality=mean(run.quality for run in samples),
        )


@dataclass(frozen=True)
class CollaborationTrace:
    task_id: str
    topology: str
    agents: int
    total_tokens: int
    wall_time_ms: int
    quality: float
    baseline: SingleAgentBaseline
    failed_workers: int = 0
    unresolved_conflicts: int = 0

    @property
    def token_multiplier(self) -> float:
        average = self.baseline.average_tokens
        return self.total_tokens / average

    @property
    def latency_speedup(self) -> float:
        average = self.baseline.average_latency_ms
        return average / self.wall_time_ms

    @property
    def quality_delta(self) -> float:
        average = self.baseline.average_quality
        return self.quality - average
