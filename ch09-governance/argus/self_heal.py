# argus/self_heal.py — Bounded retry with rollback, Ch7 snapshot.
#
# Tracks §7.x 'Argus checkpoint' which promises a self-heal loop:
# when Argus applies a fix and tests fail, it rolls forward up to N times
# (re-reading the error, re-applying, re-testing). If the budget expires,
# it signals rollback to the pre-heal state.
#
# heal_with_tests keeps the public signature Listing 7.20 prints. Its body
# adapts the (propose_fix, run_tests) pair into the six injected
# dependencies Listing 7.15 defines — 7.20 still prints the older
# SelfHealLoop(fix_fn=..., verifier=...) constructor, which no longer
# exists. See the note in the repo's Ch7 mismatch report.
from dataclasses import dataclass

from patterns.self_heal_loop import SelfHealLoop, HealAttempt, FailureSignal


@dataclass
class HealOutcome:
    healed: bool
    iterations: int
    last_error: str | None = None
    rollback: bool = False


def heal_with_tests(initial_code: str,        # Pluggable fix / test fns; runs in CI without an LLM
                    propose_fix: callable,
                    run_tests: callable,
                    max_iterations: int = 3) -> HealOutcome:
    """Self-heal driven by a test-runner verifier.

    propose_fix(code, error) -> new_code  (typically an LLM call)
    run_tests(code)          -> (passed, error_msg)

    Both callables are pluggable so the loop is testable without an LLM.
    """
    passed, error = run_tests(initial_code)
    if passed:
        return HealOutcome(healed=True, iterations=0)

    state = {"code": initial_code}
    snapshots: dict[str, str] = {}
    counter = {"n": 0}

    def _as_signal(err: str) -> FailureSignal:
        return FailureSignal(
            kind="test_failure", severity=1, error_text=err or "",
        )

    def applier(fix_diff: str) -> str:
        # Atomic: snapshot the pre-image so rollback has a target.
        counter["n"] += 1
        commit_id = f"heal-{counter['n']}"
        snapshots[commit_id] = state["code"]
        state["code"] = fix_diff
        return commit_id

    def verifier() -> FailureSignal | None:
        ok, err = run_tests(state["code"])
        return None if ok else _as_signal(err)

    loop = SelfHealLoop(                       # Listing 7.15 is the engine
        diagnoser=lambda failure: failure.error_text,
        fix_generator=lambda diagnosis: propose_fix(state["code"], diagnosis),
        critic=lambda fix_diff, current: {},   # no cross-model critic in the CI path
        applier=applier,
        verifier=verifier,
        rollback=lambda commit_id: state.update(code=snapshots[commit_id]),
    )
    loop.MAX_ITERATIONS = max_iterations
    result = loop.heal(_as_signal(error))

    healed = result["status"] == "fixed"
    last_failure = next(
        (a.new_failure for a in reversed(result.get("history", []))
         if a.new_failure is not None),
        None,
    )
    return HealOutcome(
        healed=healed,
        iterations=result["iterations"],
        last_error=last_failure.error_text if last_failure else None,
        rollback=not healed,                   # On exhaust, signal rollback to pre-heal state
    )
