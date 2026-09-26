"""Runnable support model for Chapter 10's Argus listing."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""
    plan_version: str | None = None
    write_set: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class CompletionReceipt:
    status: str
    effect: Any = None
    critique: Evidence | None = None
    acceptance: Evidence | None = None
    complete: bool = False


class ReviewTask(Protocol):
    async def acceptance_probe(self, effect: Any) -> Evidence | None:
        """Read the affected environment and return acceptance evidence."""


class TaskRun:
    @classmethod
    def start(cls, task: ReviewTask) -> "TaskRun":
        return cls()

    def blocked(self, decision: Decision) -> CompletionReceipt:
        return CompletionReceipt(status=f"BLOCKED: {decision.reason}")

    def close(
        self,
        *,
        effect: Any,
        critique: Evidence | None,
        acceptance: Evidence | None,
        complete: bool,
    ) -> CompletionReceipt:
        status = "COMPLETE" if complete else "INCOMPLETE"
        return CompletionReceipt(
            status=status,
            effect=effect,
            critique=critique,
            acceptance=acceptance,
            complete=complete,
        )


class Argus:
    def __init__(
        self,
        perception: Any,
        memory: Any,
        reasoning: Any,
        governance: Any,
        action: Any,
        reflection: Any,
    ) -> None:
        self.perception = perception
        self.memory = memory
        self.reasoning = reasoning
        self.governance = governance
        self.action = action
        self.reflection = reflection

    async def review(self, task: ReviewTask) -> CompletionReceipt:
        run = TaskRun.start(task)
        context = await self.perception.build(
            task=task,
            read_file=self.governance.authorized_reader(task),
        )
        memory = await self.memory.recall(task, context)
        plan = await self.reasoning.plan(task, context, memory)

        decision = self.governance.authorize(
            task=task,
            action=plan.action,
            plan_version=plan.version,
            write_set=plan.write_set,
        )
        if not decision.allowed:
            return run.blocked(decision)

        effect = await self.action.execute(plan, decision)
        critique = await self.reflection.verify(task, effect)
        acceptance = await task.acceptance_probe(effect)
        complete = (
            critique is not None
            and acceptance is not None
            and critique.passed
            and acceptance.passed
        )

        if complete:
            memory_decision = self.governance.authorize_memory(
                task=task,
                effect=effect,
                evidence=acceptance,
            )
            if memory_decision.allowed:
                await self.memory.record(
                    task=task,
                    outcome=effect,
                    evidence=acceptance,
                    authorization=memory_decision,
                )

        return run.close(
            effect=effect,
            critique=critique,
            acceptance=acceptance,
            complete=complete,
        )
