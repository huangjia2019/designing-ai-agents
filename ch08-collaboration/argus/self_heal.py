# argus/self_heal.py — Bounded retry with rollback, Ch7 snapshot.
#
# Tracks §7.x 'Argus checkpoint' which promises a self-heal loop:
# when Argus applies a fix and tests fail, it rolls forward up to N times
# (re-reading the error, re-applying, re-testing). If the budget expires,
# it rolls back to the original state.
from dataclasses import dataclass

from patterns.self_heal_loop import SelfHealLoop, HealAttempt


@dataclass
class HealOutcome:
    healed: bool
    iterations: int
    last_error: str | None = None
    rollback: bool = False


def heal_with_tests(initial_code: str,
                    propose_fix: callable,
                    run_tests: callable,
                    max_iterations: int = 3) -> HealOutcome:
    """Run Self-Heal Loop with a real test runner as the verifier.

    propose_fix(code, error) -> new_code  (typically an LLM call)
    run_tests(code)          -> (passed, error_msg)

    Both callables are pluggable so the loop is testable without an LLM.
    """
    loop = SelfHealLoop(
        fix_fn=propose_fix,
        verifier=run_tests,
        max_iterations=max_iterations,
    )
    result = loop.heal(initial_code)
    return HealOutcome(
        healed=result["healed"],
        iterations=result["iterations"],
        last_error=result.get("last_error"),
        rollback=not result["healed"],
    )
