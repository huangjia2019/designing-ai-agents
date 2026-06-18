# argus/core.py — Argus, Ch3 snapshot: Ch2 single-prompt review + perception layer
#
# Cumulative evolution from Ch2:
#   Ch2 review_diff(diff, context) accepted a free-form context string but did
#   nothing to populate it. The Ch3 Argus wraps that single LLM call with the
#   perception module from Listing 3.5: gather_review_context discovers
#   modified files, follows imports, finds tests, loads config, then triages
#   under a token budget. The LLM no longer sees just "the diff" — it sees the
#   minimum context that survives priority-tiered greedy budget filling.
import json

from .perception import gather_review_context, PerceptionTrace, FileContext


def _format_context(selected: list[FileContext]) -> str:
    """Serialize selected FileContexts into a prompt-friendly block."""
    sections = []
    for ctx in selected:
        sections.append(
            f"### {ctx.path}  [{ctx.relevance}, {ctx.tokens} tokens]\n"
            f"```\n{ctx.content}\n```"
        )
    return "\n\n".join(sections)


def review_diff(
    diff: str,
    repo_root: str = ".",
    budget: int = 50_000,
) -> tuple[dict, PerceptionTrace]:
    """Argus Ch3: PRA loop with perception.

    Perception:  gather_review_context — discover, prioritize, budget
    Reasoning:   Claude analyzes the diff + selected context
    Action:      structured review output

    Returns (review_json, perception_trace).  The trace is what makes the
    perception step observable — every decision about what to look at and
    what to drop is auditable post-hoc.
    """
    import anthropic  # lazy: perception is usable without LLM dependency
    client = anthropic.Anthropic()

    # --- PERCEPTION: gather + triage context under a token budget ---
    selected, trace = gather_review_context(diff, repo_root, budget)
    context = _format_context(selected) if selected else ""

    # --- REASONING: same single-pass LLM call as Ch2, now with real context ---
    system = """You are Argus, an expert code reviewer.
Respond with JSON: {"summary": "...", "comments": [
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

    # --- ACTION: parse structured output ---
    text = response.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    review = json.loads(text)
    return review, trace
