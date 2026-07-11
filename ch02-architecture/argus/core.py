# argus/core.py — The simplest possible code review agent
import json

def review_diff(diff: str, context: str = "") -> dict:
    """One pass through the PRA loop.

    Perception: the diff text (+ optional context)
    Reasoning:  Claude analyzes the diff
    Action:     structured review output
    """
    import anthropic  # lazy: keep module importable without LLM SDK installed
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
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    # --- ACTION: parse structured output ---  #C
    text = response.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    return json.loads(text)


if __name__ == "__main__":
    # Minimal end-to-end demo for §2.6.2.
    # Requires: pip install anthropic; export ANTHROPIC_API_KEY=sk-ant-...
    SAMPLE_DIFF = """--- a/greet.py
+++ b/greet.py
@@ -1,3 +1,5 @@
 def greet(name):
-    return f"Hello, {name}"
+    if not name:
+        return "Hello, stranger"
+    return f"Hello, {name}!"
"""
    review = review_diff(SAMPLE_DIFF)
    print(json.dumps(review, indent=2))
