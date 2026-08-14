"""Argus with Google's Agent Development Kit — repository extra, not a book listing.

The same PRA loop as argus/core.py, expressed in a third framework so the
architecture can be compared against openai_argus.py and langgraph_argus.py.
ADK keeps the agent declarative and puts the loop in a Runner, so perception
arrives as a Content message and the reasoning result comes back as events.

    pip install google-adk
    export GOOGLE_API_KEY=...
    python demos/adk_argus.py
"""
import asyncio

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

APP_NAME = "argus"
USER_ID = "reviewer"
SESSION_ID = "review-1"

DIFF = """--- a/cache.py
+++ b/cache.py
@@
-    entry = cache.get(key)
-    if entry is None:
-        entry = load(key)
-        cache[key] = entry
+    if key not in cache:
+        cache[key] = load(key)
+    entry = cache[key]
"""

argus = LlmAgent(
    model="gemini-flash-latest",
    name="Argus",
    description="Reviews code diffs for bugs, security issues, and style problems.",
    instruction=(
        "You are Argus, an expert code reviewer. Analyze the diff and report "
        "bugs, security issues, and style problems. Be specific about line and file."
    ),
)


async def review(diff: str) -> str:
    session_service = InMemorySessionService()
    runner = Runner(agent=argus, app_name=APP_NAME, session_service=session_service)
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    message = Content(role="user", parts=[Part(text=f"Review this diff:\n{diff}")])

    answer = "(no final response)"
    async for event in runner.run_async(
        user_id=USER_ID, session_id=SESSION_ID, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            answer = event.content.parts[0].text
    return answer


if __name__ == "__main__":
    print(asyncio.run(review(DIFF)))
