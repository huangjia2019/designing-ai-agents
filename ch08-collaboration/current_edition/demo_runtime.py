"""A scripted tool-calling adapter for offline examples; not a model.

It records context and tool use so the collaboration boundaries are inspectable.
"""

from __future__ import annotations

from .patterns.adversarial_review import SecurityReviewLoop
from .patterns.collaboration_runtime import (
    AgentResult,
    AgentSpec,
    SharedWorkspace,
    SubagentSpawner,
)
from .patterns.collaboration_trace import (
    CollaborationTrace,
    RunSample,
    SingleAgentBaseline,
)
from .patterns.fan_out_gather import (
    BranchReceipt,
    DynamicFanOut,
    ResearchBranch,
)
from .patterns.handoff_chain import (
    HandoffChain,
    HandoffPacket,
)
from .patterns.hierarchical_delegation import (
    DelegationRequest,
    ManagerWorker,
)


class ScriptedRuntime:
    """Deterministic stand-in for a model tool-calling loop."""

    def __init__(self) -> None:
        self.calls = []

    def run(
        self,
        spec,
        task,
        context,
        tools,
        workspace,
    ) -> AgentResult:
        self.calls.append(
            {
                "agent": spec.name,
                "context": context.context_id,
                "workspace": id(workspace),
                "tools": tuple(sorted(tools)),
            }
        )

        if spec.name == "lead-researcher":
            first = tools["fan_out"](
                [
                    ResearchBranch(
                        "a",
                        "Find primary sources for companies A-M",
                        ("search",),
                        "/research/a.md",
                    ),
                    ResearchBranch(
                        "b",
                        "Find primary sources for companies N-Z",
                        ("search",),
                        "/research/b.md",
                    ),
                ]
            )
            self.assert_receipts(first)
            follow_up = tools["fan_out"](
                [
                    ResearchBranch(
                        "c",
                        "Resolve the missing source for company Q",
                        ("search",),
                        "/research/c.md",
                    )
                ]
            )
            self.assert_receipts(follow_up)
            evidence = [
                tools["read_file"](receipt.result_path)
                for receipt in first + follow_up
            ]
            return AgentResult(
                "Synthesis: " + " | ".join(evidence),
                80,
                20,
                40,
            )

        if spec.name.startswith("researcher-"):
            return AgentResult(f"sourced: {task}", 25, 15, 20)

        if spec.name == "security-reviewer":
            path = context.payload["artifact_path"]
            source = tools["read_file"](path)
            if "unsafe_eval" in source:
                tools["post_claim"](
                    "SEC-1",
                    "parser.py:1",
                    "Untrusted input reaches unsafe_eval",
                    "Arbitrary code may run",
                )
            elif "SEC-1" in workspace.claims:
                tools["close_claim"]("SEC-1")
            return AgentResult("review recorded", 30, 10, 15)

        if spec.name == "writer":
            path = context.payload["artifact_path"]
            source = tools["read_file"](path)
            version = tools["write_file"](
                path,
                source.replace("unsafe_eval", "safe_parse"),
            )
            for claim_id in context.payload["claim_ids"]:
                tools["respond_to_claim"](
                    claim_id,
                    version,
                    "Replaced the unsafe parser and added a test",
                )
            return AgentResult("patch written", 35, 15, 18)

        if spec.name == "manager":
            first = DelegationRequest(
                "T1",
                "Define the API contract",
                (),
                "Schema test passes",
                ("write_file",),
                "/work/T1.md",
            )
            second = DelegationRequest(
                "T2",
                "Implement against the accepted contract",
                ("T1",),
                "Integration test passes",
                ("read_file", "write_file"),
                "/work/T2.md",
            )
            tools["delegate"](first)
            tools["delegate"](second)
            board = tools["read_board"]()
            return AgentResult(f"Integrated: {board}", 60, 25, 45)

        if spec.name.startswith("worker-"):
            return AgentResult(
                f"accepted artifact for {task}",
                20,
                10,
                12,
            )

        return AgentResult(f"completed: {task}", 20, 10, 10)

    @staticmethod
    def assert_receipts(receipts: list[BranchReceipt]) -> None:
        if not receipts:
            raise AssertionError("Expected at least one branch receipt")


def make_system():
    workspace = SharedWorkspace()
    runtime = ScriptedRuntime()
    registry = {
        "read_file": workspace.read_file,
        "write_file": workspace.write_file,
        "post_claim": workspace.post_claim,
        "close_claim": workspace.close_claim,
        "respond_to_claim": workspace.respond_to_claim,
        "return_handoff": workspace.return_handoff,
        "read_board": workspace.read_board,
        "search": lambda query: f"source for {query}",
    }
    spawner = SubagentSpawner(runtime, workspace, registry)
    return workspace, runtime, spawner
