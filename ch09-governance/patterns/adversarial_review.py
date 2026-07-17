"""Adversarial Review — Collaboration x Loop.

A proponent argues for a position, a reviewer attacks it, and a judge
synthesizes the verdict. The pattern exploits an asymmetry: fabrications
collapse under cross-examination, truth survives because it is internally
consistent.

Listing 8.8  — DebateRound / DebateResult + shared _call_agent
Listing 8.9  — debate setup and the multi-round loop
Listing 8.10 — judge verdict + parsing (continues inside debate())
"""
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]


@dataclass
class DebateRound:
    round_number: int
    proponent_argument: str
    reviewer_objection: str


@dataclass
class DebateResult:
    verdict: str
    winning_position: str
    rounds: list[DebateRound]
    confidence: float


class AdversarialReview:
    def __init__(
        self,
        client: Anthropic,
        model: str = "claude-sonnet-4-6",
        num_rounds: int = 2,
    ):
        self.client = client
        self.model = model
        self.num_rounds = num_rounds

    def _call_agent(
        self,
        system: str,
        messages: list[dict],
    ) -> str:
        response = (
            self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=messages,
            )
        )
        return response.content[0].text

    def debate(
        self, question: str
    ) -> DebateResult:
        proponent_sys = (
            "You are the PROPONENT. Argue FOR "
            "the position with evidence. Do not "
            "concede unless genuinely weaker."
        )
        reviewer_sys = (
            "You are the REVIEWER. Find "
            "weaknesses, challenge assumptions. "
            "Explain WHY something is wrong."
        )
        judge_sys = (
            "You are the JUDGE. Provide:\n"
            "VERDICT: [conclusion]\n"
            "WINNER: [proponent or reviewer]\n"
            "CONFIDENCE: [0.0 to 1.0]"
        )

        opening = self._call_agent(
            proponent_sys,
            [{"role": "user", "content":
              f"Take a position on: {question}"
            }],
        )
        transcript = (
            f"Proponent (Round 1): "
            f"{opening}\n\n"
        )
        rounds = []

        for rn in range(self.num_rounds):
            rev = self._call_agent(
                reviewer_sys,
                [{"role": "user", "content": (
                    f"Question: {question}\n\n"
                    f"Debate:\n{transcript}\n\n"
                    f"Challenge the proponent."
                )}],
            )
            transcript += (
                f"Reviewer (Round {rn + 1}): "
                f"{rev}\n\n"
            )
            pro = ""
            if rn < self.num_rounds - 1:
                pro = self._call_agent(
                    proponent_sys,
                    [{"role": "user", "content": (
                        f"Question: {question}\n"
                        f"\nDebate:\n{transcript}"
                        f"\n\nAddress challenges."
                    )}],
                )
                transcript += (
                    f"Proponent (Round {rn+2}): "
                    f"{pro}\n\n"
                )
            rounds.append(DebateRound(
                round_number=rn + 1,
                proponent_argument=(
                    opening if rn == 0 else pro
                ),
                reviewer_objection=rev,
            ))

        verdict = self._call_agent(
            judge_sys,
            [{"role": "user", "content": (
                f"Question: {question}\n\n"
                f"Transcript:\n{transcript}"
                f"\n\nDeliver your verdict."
            )}],
        )
        winner = "proponent"
        conf = 0.7
        for line in verdict.split("\n"):
            ln = line.strip()
            if ln.startswith("WINNER:"):
                w = ln.split(":", 1)[1].lower()
                if "reviewer" in w:
                    winner = "reviewer"
            elif ln.startswith("CONFIDENCE:"):
                try:
                    conf = float(
                        ln.split(":", 1)[1].strip()
                    )
                except ValueError:
                    pass
        return DebateResult(
            verdict=verdict,
            winning_position=winner,
            rounds=rounds,
            confidence=conf,
        )


if __name__ == "__main__":
    # Live demo — needs ANTHROPIC_API_KEY.
    from anthropic import Anthropic as _Anthropic

    reviewer = AdversarialReview(_Anthropic(), num_rounds=2)
    result = reviewer.debate(
        "This service should migrate from REST to gRPC."
    )
    print(f"winner={result.winning_position} "
          f"confidence={result.confidence:.2f} "
          f"rounds={len(result.rounds)}")
    print(result.verdict)
