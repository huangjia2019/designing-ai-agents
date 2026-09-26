"""Minimal contracts used by Chapter 10's composition example."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureHypothesis:
    decision_id: str
    task_id: str
    baseline: str
    observed_deficit: str
    proposal: tuple[str, ...]
    assumption_evidence: tuple[str, ...]
    seam_contracts: tuple[str, ...]
    acceptance_gates: tuple[str, ...]
    removal_condition: str


@dataclass(frozen=True)
class EvaluationReceipt:
    decision_id: str
    operating_point: str
    workload_version: str
    evidence_refs: tuple[str, ...]
    baseline_failed: bool
    proposal_passed: bool
    seam_tests_passed: bool
    external_acceptance_passed: bool
    risk_gates_passed: bool


def decide(receipt: EvaluationReceipt) -> str:
    """Admit a composition only when it beats a failing baseline."""
    if not receipt.evidence_refs:
        return "REJECT: no evidence attached"
    if not receipt.baseline_failed:
        return "REJECT: baseline already meets the gates"
    if not all((
        receipt.proposal_passed,
        receipt.seam_tests_passed,
        receipt.external_acceptance_passed,
        receipt.risk_gates_passed,
    )):
        return "REJECT: proposal did not pass all required gates"
    return "ACCEPT_PROVISIONALLY"
