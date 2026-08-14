"""Fan-out/gather in Google's ADK — repository extra, not a book listing.

patterns/fan_out_gather.py builds the topology by hand with a thread pool,
which is the point of the chapter: the pattern is a structure, not a library
call. This file shows the same structure expressed as a framework primitive.
ADK's ParallelAgent runs its children concurrently and writes each result into
shared session state; a SequentialAgent then hands that state to a synthesizer.

The comparison worth making: the hand-built version owns the concurrency and
the failure handling, the framework version inherits both. Which you want
depends on how much of the failure behaviour you need to specify yourself.

    pip install google-adk
    export GOOGLE_API_KEY=...
    python demos/adk_fan_out_gather.py
"""
import asyncio

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

APP_NAME = "argus-collaboration"
USER_ID = "reviewer"
SESSION_ID = "review-1"
MODEL = "gemini-flash-latest"

REVIEWERS = [
    ("SecurityReviewer", "security", "injection, authentication, secrets, unsafe defaults"),
    ("StyleReviewer", "style", "naming, structure, readability, dead code"),
    ("ComplexityReviewer", "complexity", "branching, coupling, and cost of change"),
]

DIFF = """--- a/auth.py
+++ b/auth.py
@@
-    query = "SELECT * FROM users WHERE name = %s"
-    cur.execute(query, (name,))
+    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
"""

# fan out: one bounded-context reviewer per concern, run concurrently
reviewers = [
    LlmAgent(
        model=MODEL,
        name=name,
        description=f"Reviews a diff for {concern} problems.",
        instruction=f"Review the diff for {focus}. Report only {concern} findings.",
        output_key=f"{concern}_findings",  # written into session state
    )
    for name, concern, focus in REVIEWERS
]

# gather: the lead reads every sub-result out of state and decides
synthesizer = LlmAgent(
    model=MODEL,
    name="Lead",
    description="Merges reviewer findings into one verdict.",
    instruction=(
        "Findings from three reviewers:\n"
        "security: {security_findings}\n"
        "style: {style_findings}\n"
        "complexity: {complexity_findings}\n\n"
        "Merge them. Drop duplicates, rank by severity, and state one verdict: "
        "block, comment, or approve."
    ),
)

argus = SequentialAgent(
    name="ArgusFanOutGather",
    sub_agents=[ParallelAgent(name="Reviewers", sub_agents=reviewers), synthesizer],
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
