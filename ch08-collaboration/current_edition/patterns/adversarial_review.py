"""Writer and security reviewer with a human-owned final decision."""

from __future__ import annotations

from dataclasses import dataclass

from .collaboration_runtime import (
    AgentSpec,
    SharedWorkspace,
    SubagentSpawner,
)


@dataclass(frozen=True)
class HumanReviewPacket:
    artifact_path: str
    artifact_version: int
    rounds: int
    open_claims: tuple[str, ...]
    human_decision_required: bool = True


class SecurityReviewLoop:
    """Share artifacts and claims, not conversation history."""

    def __init__(
        self,
        spawner: SubagentSpawner,
        workspace: SharedWorkspace,
    ) -> None:
        self.spawner = spawner
        self.workspace = workspace

    def _open_claims(self) -> tuple[str, ...]:
        return tuple(
            claim_id
            for claim_id, claim in self.workspace.claims.items()
            if claim.status == "open"
        )

    def run(
        self,
        artifact_path: str,
        acceptance: tuple[str, ...],
        max_rounds: int = 2,
    ) -> HumanReviewPacket:
        reviewer = AgentSpec(
            name="security-reviewer",
            instructions=(
                "Try to falsify the security claim. Post a claim only "
                "with location, evidence, and consequence."
            ),
            tools=("read_file", "post_claim", "close_claim"),
        )
        writer = AgentSpec(
            name="writer",
            instructions=(
                "Change the artifact or rebut the claim with evidence. "
                "Record a response for every open claim."
            ),
            tools=("read_file", "write_file", "respond_to_claim"),
        )

        rounds = 0
        for round_number in range(1, max_rounds + 1):
            rounds = round_number
            self.spawner.spawn(
                reviewer,
                task=f"Review {artifact_path}",
                goal="Meet the security acceptance criteria",
                parent_id="maintainer",
                payload={
                    "artifact_path": artifact_path,
                    "acceptance": acceptance,
                    "round": round_number,
                },
            )
            open_claims = self._open_claims()
            if not open_claims:
                break
            self.spawner.spawn(
                writer,
                task=f"Address claims {open_claims}",
                goal="Meet the security acceptance criteria",
                parent_id="maintainer",
                payload={
                    "artifact_path": artifact_path,
                    "claim_ids": open_claims,
                    "round": round_number,
                },
            )

        artifact = self.workspace.files[artifact_path]
        return HumanReviewPacket(
            artifact_path,
            artifact.version,
            rounds,
            self._open_claims(),
        )
