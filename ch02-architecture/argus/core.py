# argus/core.py — The simplest possible code review agent
import anthropic
import json

def review_diff(diff: str, context: str = "") -> dict:
    """One pass through the PRA loop.

    Perception: the diff text (+ optional context)
    Reasoning:  Claude analyzes the diff
    Action:     structured review output
    """
    client = anthropic.Anthropic()

    # --- PERCEPTION: assemble  #A
    # what the agent sees ---
    system = """You are Argus, an expert code reviewer.
Respond with JSON: {"summary": "...", "comments": [
  {"file": "...", "line": ..., "severity": "...", "message": "..."}
]}"""

    user_msg = f"## Diff:\n```diff\n{diff}\n```"
    if context:
        user_msg += f"\n\n## Context:\n{context}"

    # --- REASONING: Claude analyzes ---  #B
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    # --- ACTION: parse structured output ---  #C
    text = response.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    return json.loads(text)
