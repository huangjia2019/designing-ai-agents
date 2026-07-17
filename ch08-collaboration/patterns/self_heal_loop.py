"""Self-Heal Loop — failure-triggered retry with deterministic verifier.

Book: Chapter 7, Listings 7.15-7.18.

When a tool result signals failure (test fail, build break, etc.), the
agent rolls forward: read the failure, fix the code, run the verifier
again. Capped iterations + rollback on regression.

Three structural pillars, per §7.5: the loop is *bounded* (MAX_ITERATIONS),
each fix lands as an *atomic* commit so rollback has something to revert,
and *rollback* is a first-class injected dependency rather than an
afterthought. The critic sits between fix generation and application,
which is what blocks a reckless fix before it touches the working tree.

Aider popularized the --auto-test pattern. Spotify's Honk takes it
further: four-tier cascade (format / lint / build / test).
"""
import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FailureSignal:
    """What the loop is trying to recover from."""
    kind: str
    severity: int
    error_text: str
    affected_files: list[str] = field(
        default_factory=list
    )


@dataclass
class HealAttempt:
    """One iteration of the loop, recorded for audit."""
    iteration: int
    diagnosis: str
    fix_diff: str
    commit_id: Optional[str]
    new_failure: Optional[FailureSignal]


class SelfHealLoop:
    """Bound, atomic, rollback: the three structural pillars."""

    MAX_ITERATIONS = 3

    def __init__(
        self,
        diagnoser,
        fix_generator,
        critic,          # Cross-family critic prevents echo-chamber bias
        applier,
        verifier,
        rollback,
    ):
        self.diagnoser = diagnoser
        self.fix_generator = fix_generator
        self.critic = critic
        self.applier = applier
        self.verifier = verifier
        self.rollback = rollback

    def heal(
        self,
        initial_failure: FailureSignal,
    ) -> dict:
        history: list[HealAttempt] = []
        current = initial_failure
        initial_sig = self._signature(
            initial_failure
        )
        commits: list[str] = []
        for i in range(self.MAX_ITERATIONS):
            diagnosis = self.diagnoser(current)
            fix_diff = self.fix_generator(
                diagnosis
            )
            verdict = self.critic(
                fix_diff, current
            )
            if verdict.get("block"):
                return {
                    "status": "blocked",
                    "iterations": i + 1,
                    "history": history,
                }
            # Atomic commit per iteration enables rollback
            commit_id = self.applier(fix_diff)
            commits.append(commit_id)
            new_failure = self.verifier()
            history.append(HealAttempt(
                iteration=i,
                diagnosis=diagnosis,
                fix_diff=fix_diff,
                commit_id=commit_id,
                new_failure=new_failure,
            ))
            if new_failure is None:
                return {
                    "status": "fixed",
                    "iterations": i + 1,
                    "commits": commits,
                }
            new_sig = self._signature(
                new_failure
            )
            if (
                new_sig != initial_sig
                and self._is_regression(
                    current, new_failure
                )
            ):
                for cid in reversed(commits):
                    self.rollback(cid)
                return {
                    "status": "rolled_back",
                    "iterations": i + 1,
                    "history": history,
                }
            current = new_failure
        return {
            "status": "human_handoff",
            "iterations": self.MAX_ITERATIONS,
            "history": history,
        }

    @staticmethod
    def _signature(
        f: FailureSignal,
    ) -> str:
        # Hash kind + an error-text prefix so cosmetic differences
        # (line numbers, timestamps) don't break equality.
        key = f"{f.kind}|{f.error_text[:200]}"
        return hashlib.sha256(
            key.encode()
        ).hexdigest()[:12]

    @staticmethod
    def _is_regression(
        old: FailureSignal,
        new: FailureSignal,
    ) -> bool:
        # Escalation worth rolling back: severity rose, or the blast
        # radius expanded more than 2x.
        if new.severity > old.severity:
            return True
        old_files = max(
            len(old.affected_files), 1
        )
        return (
            len(new.affected_files)
            > 2 * old_files
        )
