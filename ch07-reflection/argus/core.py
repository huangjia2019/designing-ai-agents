# argus/core.py — Argus, Ch7 snapshot: + self-improvement.
#
# Cumulative evolution from Ch6:
#   Ch6 added action (tools, guardrail, action_log).
#   Ch7 adds reflection. After producing a review and gathering tool
#   evidence, Argus runs a critic over its own findings, drops likely
#   false positives, and records the outcome into experience replay so
#   future runs of similar diffs avoid the same mistakes.

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .self_heal import heal_with_tests


def _format_context(selected: list[FileContext], past_lessons: list[str],
                    action_evidence: list[str], skill_hits: list[str]) -> str:
    sections = []
    if past_lessons:
        sections.append(
            "### Past lessons\n" + "\n".join(f"- {l}" for l in past_lessons)
        )
    if skill_hits:
        sections.append(
            "### Relevant skills from library\n" + "\n".join(f"- {s}" for s in skill_hits)
        )
    if action_evidence:
        sections.append(
            "### Verification evidence\n" + "\n".join(action_evidence)
        )
    for ctx in selected:
        sections.append(
            f"### {ctx.path}  [{ctx.relevance}, {ctx.tokens} tokens]\n```\n{ctx.content}\n```"
        )
    return "\n\n".join(sections)


def review_diff(
    diff: str,
    project: str,
    memory: ArgusMemory,
    reasoning: ArgusReasoning | None = None,
    action: ArgusAction | None = None,
    reflection: ArgusReflection | None = None,
    repo_root: str = ".",
    budget: int = 50_000,
    verify_with_tools: bool = True,
    refine_review: bool = True,
) -> tuple[ReviewResult, PerceptionTrace, list, dict]:
    """Argus Ch7: + critic loop + experience replay.

    Returns (result, p_trace, action_log, reflection_meta) where
    reflection_meta carries convergence/iterations/final_score from the
    generator-critic loop over Argus's own review.
    """
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))

    reflection = reflection or ArgusReflection()
    skill_hits = [s.description for s in reflection.skills.retrieve(diff[:300], max_skills=3)]

    action = action or ArgusAction()
    action_evidence: list[str] = []
    if verify_with_tools:
        lint_trace = action.run_lint(repo_root=repo_root)
        if not lint_trace.guardrail_blocked and lint_trace.output:
            action_evidence.append(
                f"lint: {str(lint_trace.output)[:200]}"
            )

    context = _format_context(selected, past, action_evidence, skill_hits)
    augmented = f"{diff}\n\n# Project context:\n{context}" if context else diff

    reasoning = reasoning or ArgusReasoning()
    result = reasoning.review(augmented)

    reflection_meta: dict = {}
    if refine_review:
        tool_check = lambda text: " ".join(action_evidence)
        refined = reflection.refine(
            review_text=result.verdict,
            regenerate=lambda task, ctx: reasoning.review(f"{augmented}\n\n# Critic feedback:\n{ctx}").verdict,
            tool_check=tool_check,
        )
        reflection_meta = {
            "iterations": refined["iterations"],
            "converged": refined["converged"],
            "final_score": refined["final_score"],
        }
        result.verdict = refined["output"]
        result.confidence = min(result.confidence, refined["final_score"])

    reflection.record_outcome(
        task=f"review:{project}",
        succeeded=reflection_meta.get("converged", True),
    )
    memory.after_review(review_summary=result.verdict[:200], project=project)
    return result, p_trace, action.action_log, reflection_meta
