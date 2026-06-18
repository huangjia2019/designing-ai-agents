"""Adversarial Review — generator vs distinct critic agent.

One agent produces an artifact; a SEPARATE agent (distinct system prompt,
ideally distinct model family) tries to refute it. Externalizing the
critic eliminates self-enhancement bias that Generator-Critic still
carries in single-model variants.

Multi-Agent Reflexion (MAR) [arXiv:2512.20845]: +6.2 on HumanEval pass@1.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass
class AdversarialVerdict:
    claim_survives: bool
    refutation_attempts: int
    confidence: float
    notes: str = ""


def adversarial_review(
    claim: str,
    refuters: list[Callable[[str], str]],
    refute_majority: int = 2,
) -> AdversarialVerdict:
    """Run N independent refuters; claim survives only if < majority refute."""
    refuted_votes = 0
    notes = []
    for i, refuter in enumerate(refuters):
        response = refuter(claim)
        if "refuted" in response.lower() or "false" in response.lower():
            refuted_votes += 1
            notes.append(f"r{i}: refuted ({response[:60]})")
        else:
            notes.append(f"r{i}: survived")
    survives = refuted_votes < refute_majority
    return AdversarialVerdict(
        claim_survives=survives,
        refutation_attempts=len(refuters),
        confidence=1.0 - (refuted_votes / max(len(refuters), 1)),
        notes=" | ".join(notes),
    )
