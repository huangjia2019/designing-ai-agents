"""Demo: Ch7 critic-loop story — Argus PR #4287.

Generator returns 5 issues. Critic runs the test suite (deterministic).
Two issues fail to reproduce → dropped. Precision goes 3/5 → 3/3.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patterns.generator_critic import GeneratorCriticLoop, Critique


GENERATED_REVIEW = """\
Found 5 issues:
- A severity=high  null deref in auth.py:42
- B severity=med   off-by-one in cache.py:88
- C severity=high  race in connection_pool.py:130
- D severity=low   style on naming
- E severity=high  missing input validation in form.py:55
"""


def fake_generator(task, ctx):
    # Loop only refines if ctx is non-empty (i.e., not the first iteration).
    if ctx and "phantom" in ctx.lower():
        # Trimmed review after critic feedback.
        return """\
Found 3 issues:
- A severity=high  null deref in auth.py:42
- C severity=high  race in connection_pool.py:130
- E severity=high  missing input validation in form.py:55
"""
    return GENERATED_REVIEW


def fake_critic(task, output, tool_fb):
    if "5 issues" in output:
        return Critique(
            score=0.6,
            approved=False,
            feedback_text=(
                "Phantom findings detected by pytest evidence. "
                "Drop B and D — tests pass for both lines after fix."
            ),
        )
    return Critique(score=0.95, approved=True, feedback_text="Confirmed by tests.")


def main():
    loop = GeneratorCriticLoop(
        generate=fake_generator,
        critique_fn=fake_critic,
        max_iterations=3,
        quality_threshold=0.9,
    )
    result = loop.refine(task="review PR #4287", tool_fn=lambda x: "pytest evidence: B and D pass")
    print("=== Generator-Critic over Argus review ===")
    print(f"iterations: {result['iterations']}")
    print(f"converged:  {result['converged']}")
    print(f"final_score: {result['final_score']:.2f}")
    print()
    print("Final review (after critic dropped phantoms):")
    print(result["output"])
    print(f"Precision improvement: 3/5 → 3/3  (dropped B, D)")


if __name__ == "__main__":
    main()
