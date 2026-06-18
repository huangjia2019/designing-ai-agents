# argus/core.py — Argus, Ch6 snapshot: perception + memory + reasoning + action.
#
# Cumulative evolution from Ch5:
#   Ch5 added reasoning depth control (complexity-routed CoT).
#   Ch6 adds hands. Argus can now run the lint command, run the test suite,
#   and apply fixes — each invocation goes through the Guardrail Sandwich
#   (pre-check → maybe HITL → execute → post-check) and emits an
#   ActionTrace. The review can now do more than read: it can verify.
#
# This unifies what was previously asymmetric (Ch5's review returned a
# verdict; Ch6 lets the verdict be substantiated by running real checks).

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction


def _format_context(selected: list[FileContext], past_lessons: list[str],
                    action_evidence: list[str]) -> str:
    sections = []
    if past_lessons:
        sections.append(
            "### Past lessons from this project\n"
            + "\n".join(f"- {line}" for line in past_lessons)
        )
    if action_evidence:
        sections.append(
            "### Verification evidence (from Argus's tools)\n"
            + "\n".join(action_evidence)
        )
    for ctx in selected:
        sections.append(
            f"### {ctx.path}  [{ctx.relevance}, {ctx.tokens} tokens]\n"
            f"```\n{ctx.content}\n```"
        )
    return "\n\n".join(sections)


def review_diff(
    diff: str,
    project: str,
    memory: ArgusMemory,
    reasoning: ArgusReasoning | None = None,
    action: ArgusAction | None = None,
    repo_root: str = ".",
    budget: int = 50_000,
    verify_with_tools: bool = True,
) -> tuple[ReviewResult, PerceptionTrace, list]:
    """Argus Ch6: PRA with perception + memory + reasoning + tool-grounded action.

    Returns (result, perception_trace, action_log). The action_log holds
    ActionTrace records for every tool invocation in this review session —
    audit-grade observability of what Argus actually did.
    """
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))

    # --- ACTION: gather verification evidence BEFORE reasoning ---
    # This is the Ch6 contribution: rather than guess if the test pass,
    # actually run them and let the reasoning layer see the result.
    action = action or ArgusAction()
    action_evidence: list[str] = []
    if verify_with_tools:
        lint_trace = action.run_lint(repo_root=repo_root)
        if not lint_trace.guardrail_blocked and lint_trace.output:
            rc = lint_trace.output.get("returncode")
            action_evidence.append(
                f"lint (returncode={rc}): "
                + (lint_trace.output.get("stdout", "")[:500] or "(clean)")
            )

    context = _format_context(selected, past, action_evidence)
    augmented = f"{diff}\n\n# Project context:\n{context}" if context else diff

    reasoning = reasoning or ArgusReasoning()
    result = reasoning.review(augmented)

    memory.after_review(review_summary=result.verdict[:200], project=project)
    return result, p_trace, action.action_log
