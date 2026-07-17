"""Plan-and-Execute — separate strategy from tactics.

Book: Chapter 6, Listing 6.7 (Task/Plan DAG), Listing 6.8 (planner and
executor with two-tier model routing), and Listing 6.9 (the loop).

The planner uses an expensive model and is called once; executors use a cheap
model and are called many times. The plan is a DAG — `ready_tasks()` walks it
in topological order — while the runtime control flow around it loops.
"""
from dataclasses import dataclass, field
from enum import Enum

try:  # keeps this module importable without the SDK installed
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    description: str
    dependencies: list[str] = field(
        default_factory=list
    )
    status: TaskStatus = (
        TaskStatus.PENDING
    )
    result: str = ""
    error: str = ""


@dataclass
class Plan:
    goal: str
    tasks: list[Task] = field(
        default_factory=list
    )
    revision_count: int = 0

    def ready_tasks(  # Topological ordering via dependency check
        self,
    ) -> list[Task]:
        """Find ready tasks in the DAG."""
        completed = {
            t.id for t in self.tasks
            if t.status == TaskStatus.COMPLETED
        }
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(
                d in completed
                for d in t.dependencies
            )
        ]

    def is_complete(self) -> bool:
        return all(
            t.status == TaskStatus.COMPLETED
            for t in self.tasks
        )


class PlanAndExecuteAgent:
    """Separate planning from execution."""

    def __init__(
        self, client: Anthropic,
        planner_model: str = "claude-sonnet-4-6",
        executor_model: str = "claude-haiku-4-5-20251001",
    ):
        self.client = client
        self.planner = planner_model
        self.executor = executor_model

    def create_plan(  # Planner uses expensive model, called once
        self, goal: str,
    ) -> Plan:
        """Expensive model decomposes."""
        resp = (
            self.client.messages.create(
                model=self.planner,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content":
                    f"Decompose into 3-8"
                    f" subtasks.\n\n"
                    f"Goal: {goal}\n\n"
                    f"For each: TASK_ID,"
                    f" DESCRIPTION,"
                    f" DEPENDS_ON",
                }],
            )
        )
        return self._parse_plan(
            goal, resp.content[0].text
        )

    def execute_task(  # Executor uses cheap model, called many times
        self, task: Task,
        context: dict[str, str],
    ) -> str:
        """Cheap executor runs subtask."""
        dep_ctx = "\n".join(
            f"Result of {d}: "
            f"{context[d]}"
            for d in task.dependencies
            if d in context
        )
        resp = (
            self.client.messages.create(
                model=self.executor,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content":
                    f"Execute:"
                    f" {task.description}"
                    f"\n{dep_ctx}",
                }],
            )
        )
        return resp.content[0].text

    def run(  # Main loop iterates DAG, executing ready tasks
        self, goal: str,
        max_iter: int = 20,
    ) -> dict:
        """Plan-and-execute loop."""
        plan = self.create_plan(goal)
        ctx: dict[str, str] = {}
        iters = 0

        while (
            not plan.is_complete()
            and iters < max_iter
        ):
            ready = plan.ready_tasks()
            if not ready:
                break
            for task in ready:
                task.status = (
                    TaskStatus.RUNNING
                )
                try:
                    result = (
                        self.execute_task(
                            task, ctx,
                        )
                    )
                    task.result = result
                    task.status = (
                        TaskStatus.COMPLETED
                    )
                    ctx[task.id] = result
                except Exception as e:
                    task.error = str(e)
                    task.status = (
                        TaskStatus.FAILED
                    )
            iters += 1

        return {
            "goal": plan.goal,
            "completed": [
                t.id
                for t in plan.tasks
                if t.status == TaskStatus.COMPLETED
            ],
            "failed": [
                t.id
                for t in plan.tasks
                if t.status == TaskStatus.FAILED
            ],
            "iterations": iters,
        }

    # --- Beyond the printed listings ----------------------------------
    # create_plan() (Listing 6.8) calls _parse_plan, which the chapter
    # references but does not print. It reads the planner's
    # "TASK_ID, DESCRIPTION, DEPENDS_ON" lines back into the Task DAG.
    def _parse_plan(self, goal: str, text: str) -> Plan:
        plan = Plan(goal=goal)
        for line in text.splitlines():
            line = line.strip().lstrip("-*0123456789.) ").strip()
            if not line or "," not in line:
                continue
            parts = [p.strip() for p in line.split(",")]
            task_id, description = parts[0], parts[1]
            if not task_id or not description:
                continue
            deps = [
                d for d in (parts[2:] if len(parts) > 2 else [])
                if d and d.lower() not in ("none", "-", "n/a")
            ]
            plan.tasks.append(
                Task(id=task_id, description=description, dependencies=deps)
            )
        return plan
