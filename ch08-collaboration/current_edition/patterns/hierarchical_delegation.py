"""Manager-owned delegation with dependencies and worker receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .collaboration_runtime import (
    AgentResult,
    AgentSpec,
    ManagedTask,
    SharedWorkspace,
    SubagentSpawner,
)


@dataclass(frozen=True)
class DelegationRequest:
    task_id: str
    description: str
    depends_on: tuple[str, ...]
    acceptance: str
    tools: tuple[str, ...]
    result_path: str


@dataclass(frozen=True)
class DelegationReceipt:
    task_id: str
    status: str
    result_path: str = ""
    reason: str = ""


class ManagerWorker:
    """The manager owns dependencies, replanning, and integration."""

    def __init__(
        self,
        spawner: SubagentSpawner,
        workspace: SharedWorkspace,
    ) -> None:
        self.spawner = spawner
        self.workspace = workspace
        add_tool = self.spawner.add_tool
        add_tool("delegate", self.delegate)

    def delegate(
        self,
        request: DelegationRequest,
    ) -> DelegationReceipt:
        task = ManagedTask(
            request.task_id,
            request.description,
            request.depends_on,
            request.acceptance,
            result_path=request.result_path,
        )
        self.workspace.tasks[task.task_id] = task
        incomplete = [
            dependency
            for dependency in task.depends_on
            if self.workspace.tasks.get(dependency) is None
            or self.workspace.tasks[dependency].status != "completed"
        ]
        if incomplete:
            task.status = "blocked"
            return DelegationReceipt(
                task.task_id,
                task.status,
                reason=f"Waiting for {', '.join(incomplete)}",
            )

        task.status = "running"
        worker = AgentSpec(
            name=f"worker-{task.task_id}",
            instructions=(
                "Produce the bounded deliverable and evidence for its "
                "acceptance criterion."
            ),
            tools=request.tools,
        )
        result = self.spawner.spawn(
            worker,
            task=task.description,
            goal=task.description,
            parent_id="manager",
            payload={
                "depends_on": task.depends_on,
                "acceptance": task.acceptance,
                "result_path": task.result_path,
            },
        )
        self.workspace.write_file(task.result_path, result.text)
        task.status = "completed"
        return DelegationReceipt(
            task.task_id,
            task.status,
            result_path=task.result_path,
        )

    def execute(self, goal: str) -> AgentResult:
        manager_tools = (
            "delegate",
            "read_board",
            "read_file",
        )
        manager = AgentSpec(
            name="manager",
            instructions=(
                "Keep the whole goal. Use delegate to create bounded "
                "tasks, respect dependencies, inspect returns, and "
                "integrate the accepted artifacts."
            ),
            tools=manager_tools,
        )
        owner = "manager"
        return self.spawner.spawn(
            manager,
            task=goal,
            goal=goal,
            parent_id="user",
            payload={"integration_owner": owner},
        )
