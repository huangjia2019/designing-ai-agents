"""Plan-and-Execute — split planning from execution.

The Planner (expensive call, runs once) produces a list of subtasks. An
Executor (cheap calls, runs many times) handles each subtask, with the
option to replan if a step fails. Cost split: one expensive plan, many
cheap executions. Agent contexts often call the executor a "subagent"
(Anthropic, Claude Code, LangChain, DeerFlow); this module sticks with
"executor" because it pairs cleanly with the pattern name.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Subtask:
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"          # pending | running | done | failed
    result: str | None = None
    error: str | None = None


@dataclass
class Plan:
    objective: str
    subtasks: list[Subtask] = field(default_factory=list)

    def ready_subtasks(self) -> list[Subtask]:
        done = {s.id for s in self.subtasks if s.status == "done"}
        return [
            s for s in self.subtasks
            if s.status == "pending" and set(s.depends_on).issubset(done)
        ]

    def is_complete(self) -> bool:
        return all(s.status in ("done", "failed") for s in self.subtasks)


def execute_plan(plan: Plan,
                 executor: Callable[[Subtask], tuple[str | None, str | None]],
                 max_iterations: int = 50) -> Plan:
    """Run subtasks in dependency order until done or stuck."""
    for _ in range(max_iterations):
        ready = plan.ready_subtasks()
        if not ready:
            break
        for st in ready:
            st.status = "running"
            result, error = executor(st)
            if error:
                st.status = "failed"
                st.error = error
            else:
                st.status = "done"
                st.result = result
        if plan.is_complete():
            break
    return plan
