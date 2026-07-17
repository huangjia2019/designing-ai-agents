"""Experience Replay — three-tier hierarchy with adaptive trigger.

Book: Chapter 7, Listings 7.10-7.14.

Tiers:
  L0 raw execution traces — full fidelity, loaded only when upper layers miss
  L1 per-task lessons     — root-cause summaries, scanned next
  L2 transferable heuristics — highest abstraction, retrieved first

Adaptive trigger (Ch7 W9 redesign): _should_extract_lessons replaces the
naive `len(traces) % 10 == 0` counter with rolling-window failure-rate
spike detection. A fixed cadence wakes the agent regardless of whether
anything new has gone wrong; the adaptive version fires only when the
recent failure rate exceeds the prior window by SPIKE.
"""
from dataclasses import dataclass, field

try:  # keeps this module importable without the SDK installed
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


@dataclass
class ExecutionTrace:
    """L0 unit: every task execution becomes one trace, whatever the outcome.

    `steps` and `outcome` carry defaults so the Argus facade (Listing 7.19)
    can record an outcome without a step list. Every construction the book
    prints behaves exactly as shown.
    """
    task: str
    steps: list[dict] = field(default_factory=list)
    outcome: str = "success"        # success | failure
    error: str = ""
    duration_seconds: float = 0.0


@dataclass
class Lesson:
    """L2 unit: an insight extracted across multiple failures."""
    insight: str
    source_tasks: list[str] = field(
        default_factory=list
    )
    confidence: float = 0.5
    application_count: int = 0
    success_when_applied: int = 0

    @property
    def effectiveness(self) -> float:
        # Application history as a soft prior: lessons that helped get
        # prioritized, ones that didn't drop down. Before any application
        # lands, the declared confidence stands in.
        if self.application_count == 0:
            return self.confidence
        return (
            self.success_when_applied
            / self.application_count
        )


class ExperienceReplay:
    """Manages L0 traces, L1 reflections, L2 lessons. Adaptive trigger.

    `client` carries a None default so the replay buffer is constructible
    offline: the Argus facade (Listing 7.19) builds ExperienceReplay with
    no arguments and records traces without reaching the model. Every call
    the book shows — ExperienceReplay(client) — behaves as printed.
    """

    def __init__(
        self,
        client: "Anthropic | None" = None,
        model: str = "claude-sonnet-4-6",
    ):
        self.client = client
        self.model = model
        self.traces: list[ExecutionTrace] = []
        self.reflections: list[dict] = []
        self.lessons: list[Lesson] = []
        self._last_extraction_at = 0

    def record_trace(  # Stores trace; L1 on failure, L2 via spike detection
        self, trace: ExecutionTrace
    ):
        self.traces.append(trace)
        if trace.outcome == "failure":
            reflection = (
                self._reflect_on_failure(trace)
            )
            self.reflections.append({
                "task": trace.task,
                "reflection": reflection,
                "error": trace.error,
            })
        if self._should_extract_lessons():  # Trigger only signals
            new = (
                self._extract_cross_task_insights()
            )
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

    def _reflect_on_failure(  # L1 reflection generated only for failures
        self, trace: ExecutionTrace
    ) -> str:
        steps_text = "\n".join(
            f"Step {i+1}: {s['action']}"
            for i, s in enumerate(trace.steps)
        )
        prompt = (
            "Analyze this failed execution:\n"
            f"Task: {trace.task}\n"
            f"Steps:\n{steps_text}\n"
            f"Error: {trace.error}\n\n"
            "Provide:\n"
            "1. ROOT_CAUSE\n"
            "2. LESSON\n"
            "3. PREVENTION"
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user",
                 "content": prompt}
            ],
        )
        return response.content[0].text

    def _extract_cross_task_insights(  # L2, when the adaptive trigger fires
        self,
    ) -> list[Lesson]:
        recent = self.traces[-20:]
        failures = [
            t for t in recent
            if t.outcome == "failure"
        ]
        if len(failures) < 2:
            return []
        summary = "\n".join(
            f"- {t.task} | {t.error}"
            for t in failures[:10]
        )
        prompt = (
            "Find cross-task patterns:\n\n"
            f"FAILURES:\n{summary}\n\n"
            "Identify 1-3 GENERAL lessons.\n"
            "Format: INSIGHT: [lesson]"
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "user",
                 "content": prompt}
            ],
        )
        lessons = []
        current = ""
        for line in (
            response.content[0].text.split("\n")
        ):
            line = line.strip()
            if line.startswith("INSIGHT:"):
                if current:
                    lessons.append(Lesson(
                        insight=current,
                        source_tasks=[
                            t.task
                            for t in failures[:10]
                        ],
                    ))
                current = (
                    line.split(":", 1)[1].strip()
                )
        if current:
            lessons.append(Lesson(
                insight=current,
                source_tasks=[
                    t.task
                    for t in failures[:10]
                ],
            ))
        return lessons

    def get_relevant_experience(  # Retrieves lessons sorted by effectiveness
        self,
        task: str,
        max_items: int = 5,
    ) -> str:
        if not self.lessons:
            return ""
        knowledge = []
        for lesson in sorted(
            self.lessons,
            key=lambda l: l.effectiveness,
            reverse=True,
        ):
            knowledge.append(
                f"INSIGHT "
                f"({lesson.effectiveness:.0%})"
                f": {lesson.insight}"
            )
        if not knowledge:
            return ""
        text = "\n".join(knowledge[:max_items])
        return (
            "Review these lessons from "
            f"past experience:\n\n{text}"
        )

    def update_lesson_effectiveness(  # Deprioritizes unhelpful lessons
        self,
        lesson_index: int,
        task_succeeded: bool,
    ):
        if lesson_index < len(self.lessons):
            lesson = self.lessons[lesson_index]
            lesson.application_count += 1
            if task_succeeded:
                lesson.success_when_applied += 1
