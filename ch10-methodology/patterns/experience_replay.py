"""Experience Replay — three-tier hierarchy with adaptive trigger.

Tiers:
  L0 raw execution traces — full fidelity, loaded only when upper layers miss
  L1 per-task lessons     — root-cause summaries, scanned next
  L2 transferable heuristics — highest abstraction, retrieved first

Adaptive trigger (Ch7 W9 redesign): _should_extract_lessons replaces the
naive `len(traces) % 10 == 0` counter with rolling-window failure-rate
spike detection.
"""
from dataclasses import dataclass, field


@dataclass
class ExecutionTrace:
    task: str
    steps: list[dict] = field(default_factory=list)
    outcome: str = "success"  # success | failure
    error: str | None = None


@dataclass
class Lesson:
    insight: str
    source_tasks: list[str] = field(default_factory=list)
    effectiveness: float = 0.5  # updated by feedback


class ExperienceReplay:
    """Manages L0 traces, L1 reflections, L2 lessons. Adaptive trigger."""

    def __init__(self):
        self.traces: list[ExecutionTrace] = []
        self.reflections: list[dict] = []
        self.lessons: list[Lesson] = []
        self._last_extraction_at = 0

    def record_trace(self, trace: ExecutionTrace) -> None:
        """Stores trace; L1 on failure, L2 via adaptive spike detection."""
        self.traces.append(trace)
        if trace.outcome == "failure":
            reflection = self._reflect_on_failure(trace)
            self.reflections.append({
                "task": trace.task,
                "reflection": reflection,
                "error": trace.error,
            })
        if self._should_extract_lessons():
            new = self._extract_cross_task_insights()
            self.lessons.extend(new)
            self._last_extraction_at = len(self.traces)

    def _should_extract_lessons(self) -> bool:
        BATCH, WINDOW, SPIKE = 10, 30, 1.5
        new = len(self.traces) - self._last_extraction_at
        if new < BATCH or len(self.traces) < 2 * WINDOW:
            return False
        recent = self.traces[-WINDOW:]
        prior = self.traces[-2 * WINDOW:-WINDOW]
        rate_recent = sum(t.outcome == "failure" for t in recent) / WINDOW
        rate_prior = sum(t.outcome == "failure" for t in prior) / WINDOW
        return rate_recent > rate_prior * SPIKE

    def _reflect_on_failure(self, trace: ExecutionTrace) -> dict:
        return {"root_cause": "TBD", "lesson": "TBD", "prevention": "TBD"}

    def _extract_cross_task_insights(self) -> list[Lesson]:
        """L2 insights extracted when the adaptive trigger fires."""
        recent = self.traces[-20:]
        failures = [t for t in recent if t.outcome == "failure"]
        if len(failures) < 2:
            return []
        # Placeholder: production would call the LLM to identify cross-task patterns.
        return [Lesson(
            insight=f"recurring failure mode across {len(failures)} tasks",
            source_tasks=[t.task for t in failures[:10]],
        )]

    def get_relevant_experience(self, task: str, k: int = 3) -> list[Lesson]:
        if not self.lessons:
            return []
        scored = sorted(self.lessons, key=lambda l: l.effectiveness, reverse=True)
        return scored[:k]
