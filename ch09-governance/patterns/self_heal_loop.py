"""Self-Heal Loop — failure-triggered retry with deterministic verifier.

When a tool result signals failure (test fail, build break, etc.), the
agent rolls forward: read the failure, fix the code, run the verifier
again. Capped iterations + rollback on persistent failure.

Aider popularized the --auto-test pattern. Spotify's Honk takes it
further: four-tier cascade (compile / unit / integration / property).
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class HealAttempt:
    iteration: int
    error_observed: str
    fix_applied: str
    verifier_passed: bool


class SelfHealLoop:
    """Loop until verifier passes or attempt budget exhausted."""

    def __init__(self,
                 fix_fn: Callable[[str, str], str],   # (current_code, error) -> new_code
                 verifier: Callable[[str], tuple[bool, str]],  # (code) -> (passed, error)
                 max_iterations: int = 3):
        self._fix = fix_fn
        self._verify = verifier
        self.max_iterations = max_iterations
        self.attempts: list[HealAttempt] = []

    def heal(self, initial_code: str) -> dict:
        code = initial_code
        passed, error = self._verify(code)
        if passed:
            return {"healed": True, "iterations": 0, "code": code}

        for i in range(self.max_iterations):
            new_code = self._fix(code, error)
            passed, new_error = self._verify(new_code)
            self.attempts.append(HealAttempt(
                iteration=i,
                error_observed=error,
                fix_applied=new_code[:200],
                verifier_passed=passed,
            ))
            if passed:
                return {"healed": True, "iterations": i + 1, "code": new_code}
            # Roll back if no progress; otherwise advance
            code, error = new_code, new_error

        return {"healed": False, "iterations": self.max_iterations,
                "code": initial_code, "last_error": error}
