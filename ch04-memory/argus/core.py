# argus/core.py — Argus, Ch4 snapshot: perception + memory.
#
# Cumulative evolution from Ch3:
#   Ch3 added perception (gather → triage → budget under PerceptionTrace).
#   Ch4 adds cross-session memory. Before a review starts, Argus retrieves
#   what it learned from past reviews of the same project (recurring
#   anti-patterns, false-positive heuristics, project-specific conventions).
#   After the review completes, it persists the new findings so the next
#   review benefits.  The pattern under the hood is HierarchicalMemory
#   (Listing 4.5), wrapped by the domain-aware ArgusMemory facade.
import json

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory


def _format_context(selected: list[FileContext], past_lessons: list[str]) -> str:
    """Serialize Ch3 perception + Ch4 retrieved lessons into one prompt block."""
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
    repo_root: str = ".",
    budget: int = 50_000,
) -> tuple[dict, PerceptionTrace]:
    """Argus Ch4: PRA loop with perception + cross-session memory.

    The caller passes an ArgusMemory the agent has been writing to over time.
    Before the review starts, before_review retrieves prior lessons for this
    project. After the review completes, after_review persists the summary
    so the next session inherits today's discovery.

    Returns (review_json, perception_trace).
    """
    import anthropic
    client = anthropic.Anthropic()

    # --- PERCEPTION: gather + triage ---
    selected, trace = gather_review_context(diff, repo_root, budget)

    # --- MEMORY (before): pull relevant past lessons ---
    diff_summary = diff[:300].replace("\n", " ")
    past_lessons = memory.before_review(project=project, diff_summary=diff_summary)

    context = _format_context(selected, past_lessons)

    # --- REASONING: same single-pass LLM call, now grounded in past + present ---
    system = """You are Argus, an expert code reviewer.
You have access to past lessons from this project and the current diff
context. Respond with JSON:
{"summary": "...", "comments": [
  {"file": "...", "line": ..., "severity": "...", "message": "..."}
]}"""

    user_msg = f"## Diff:\n```diff\n{diff}\n```"
    if context:
        user_msg += f"\n\n## Project context:\n{context}"

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    review = json.loads(text)

    # --- MEMORY (after): persist the summary so next session learns from today ---
    memory.after_review(review_summary=review.get("summary", ""), project=project)

    return review, trace
