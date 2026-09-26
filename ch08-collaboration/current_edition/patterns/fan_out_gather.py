"""Model-directed Fan-Out/Gather with independent branch contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .collaboration_runtime import (
    AgentResult,
    AgentSpec,
    SharedWorkspace,
    SubagentSpawner,
)


@dataclass(frozen=True)
class ResearchBranch:
    branch_id: str
    question: str
    tools: tuple[str, ...]
    result_path: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class BranchReceipt:
    branch_id: str
    result_path: str
    tokens: int
    latency_ms: int


class DynamicFanOut:
    """Expose fan_out as a tool that a lead model can call repeatedly."""

    def __init__(
        self,
        spawner: SubagentSpawner,
        workspace: SharedWorkspace,
        max_parallel: int = 5,
    ) -> None:
        self.spawner = spawner
        self.workspace = workspace
        self.max_parallel = max_parallel
        tool = self.fan_out
        self.spawner.add_tool("fan_out", tool)

    def _run_branch(self, branch: ResearchBranch) -> BranchReceipt:
        spec = AgentSpec(
            name=f"researcher-{branch.branch_id}",
            instructions=(
                "Find evidence for one bounded question. "
                "Write claims with sources and uncertainty."
            ),
            tools=branch.tools,
        )
        result = self.spawner.spawn(
            spec,
            task=branch.question,
            goal=branch.question,
            parent_id="lead-researcher",
            payload={"result_path": branch.result_path},
        )
        path = branch.result_path
        write = self.workspace.write_file
        write(path, result.text)
        return BranchReceipt(
            branch.branch_id,
            branch.result_path,
            result.tokens,
            result.latency_ms,
        )

    def fan_out(
        self,
        branches: list[ResearchBranch],
    ) -> list[BranchReceipt]:
        if any(branch.depends_on for branch in branches):
            raise ValueError(
                "Fan-out branches must be independent at dispatch time"
            )
        receipts = []
        with ThreadPoolExecutor(
            max_workers=self.max_parallel
        ) as pool:
            futures = {
                pool.submit(self._run_branch, branch): branch
                for branch in branches
            }
            for future in as_completed(futures):
                receipts.append(future.result())
        return sorted(receipts, key=lambda item: item.branch_id)

    def research(self, query: str) -> AgentResult:
        lead = AgentSpec(
            name="lead-researcher",
            instructions=(
                "Use fan_out for independent searches. Read each result, "
                "then launch follow-up branches if evidence is missing."
            ),
            tools=("fan_out", "read_file"),
        )
        return self.spawner.spawn(
            lead,
            task=query,
            goal=query,
            parent_id="user",
            payload={"completion": "Every claim has a source"},
        )
