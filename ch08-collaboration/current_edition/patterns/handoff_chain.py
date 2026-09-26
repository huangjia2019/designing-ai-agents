"""Handoff Chain with a versioned artifact and explicit return path."""

from __future__ import annotations

from dataclasses import dataclass

from .collaboration_runtime import (
    AgentSpec,
    SharedWorkspace,
    SubagentSpawner,
)


@dataclass(frozen=True)
class HandoffPacket:
    task_id: str
    owner: str
    receiver: str
    objective: str
    artifact_path: str
    artifact_version: int
    constraints: tuple[str, ...]
    evidence: tuple[str, ...]
    acceptance: tuple[str, ...]
    open_questions: tuple[str, ...]
    return_to: str


@dataclass(frozen=True)
class HandoffReceipt:
    accepted: bool
    task_id: str
    receiver: str
    result: str = ""
    reason: str = ""


class HandoffChain:
    def __init__(
        self,
        spawner: SubagentSpawner,
        workspace: SharedWorkspace,
    ) -> None:
        self.spawner = spawner
        self.workspace = workspace

    def transfer(
        self,
        packet: HandoffPacket,
        receiver: AgentSpec,
    ) -> HandoffReceipt:
        artifact = self.workspace.files.get(packet.artifact_path)
        missing = []
        if receiver.name != packet.receiver:
            missing.append("matching receiver")
        if artifact is None:
            missing.append("artifact")
        elif artifact.version != packet.artifact_version:
            missing.append("current artifact version")
        if not packet.evidence:
            missing.append("evidence")
        if not packet.acceptance:
            missing.append("acceptance criteria")

        if missing:
            reason = "Missing " + ", ".join(missing)
            self.workspace.return_handoff(
                packet.task_id,
                packet.return_to,
                reason,
            )
            return HandoffReceipt(
                False,
                packet.task_id,
                packet.receiver,
                reason=reason,
            )

        result = self.spawner.spawn(
            receiver,
            task=packet.objective,
            goal=packet.objective,
            parent_id=packet.owner,
            payload={
                "artifact_path": packet.artifact_path,
                "artifact_version": packet.artifact_version,
                "constraints": packet.constraints,
                "evidence": packet.evidence,
                "acceptance": packet.acceptance,
                "open_questions": packet.open_questions,
                "return_to": packet.return_to,
            },
        )
        return HandoffReceipt(
            True,
            packet.task_id,
            packet.receiver,
            result=result.text,
        )
