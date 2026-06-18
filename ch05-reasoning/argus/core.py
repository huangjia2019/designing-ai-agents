# argus/core.py — Argus, Ch5 snapshot: perception + memory + reasoning.
#
# Cumulative evolution from Ch4:
#   Ch4 added cross-session memory (before/after hooks).
#   Ch5 adds reasoning depth control. Every review now routes through the
#   ArgusReasoning class (Listing 5.x): classify_complexity picks the model
#   tier, complex diffs unroll into a chain-of-thought, the weakest step
#   gets re-verified. The single-prompt review from Ch2-Ch4 becomes one of
#   three possible paths (quick / reasoned / deep).
import json

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult


def _format_context(selected: list[FileContext], past_lessons: list[str]) -> str:
    sections = []
    if past_lessons:
        sections.append(
            "### Past lessons from this project\n"
            + "\n".join(f"- {line}" for line in past_lessons)
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
    repo_root: str = ".",
    budget: int = 50_000,
) -> tuple[ReviewResult, PerceptionTrace]:
    """Argus Ch5: PRA loop with perception + memory + complexity-routed reasoning.

    The new return type is (ReviewResult, PerceptionTrace) — the verdict now
    carries the reasoning chain, the chosen complexity tier, and the
    minimum-confidence score, not just a JSON dict. The memory write
    persists a one-line summary of the verdict so the next session inherits
    today's discovery.
    """
    # --- PERCEPTION + MEMORY (before) ---
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))
    context = _format_context(selected, past)

    # Splice the context into the diff so the reasoning layer sees it.
    augmented = diff
    if context:
        augmented = f"{diff}\n\n# Project context:\n{context}"

    # --- REASONING: route by complexity, return ReviewResult ---
    reasoning = reasoning or ArgusReasoning()
    result = reasoning.review(augmented)

    # --- MEMORY (after) ---
    memory.after_review(review_summary=result.verdict[:200], project=project)

    return result, p_trace
