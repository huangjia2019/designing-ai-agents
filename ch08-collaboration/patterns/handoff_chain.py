"""Handoff Chain — Collaboration x Chain.

Each phase of a workflow belongs to a specialist agent that completes its
part and transfers the accumulated context to the next specialist.

Listing 8.2 — ChainAgent / HandoffContext data structures
Listing 8.3 — HandoffChain orchestrator
"""
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]


@dataclass
class ChainAgent:
    name: str
    role: str               # System prompt
    output_format: str = ""
    model: str = "claude-sonnet-4-6"


@dataclass
class HandoffContext:
    original_request: str
    phase_results: dict[str, str] = field(
        default_factory=dict
    )
    metadata: dict = field(default_factory=dict)

    def summary_for_next(
        self, max_tokens: int = 2000
    ) -> str:
        parts = [
            f"Original request: "
            f"{self.original_request}"
        ]
        for phase, result in (
            self.phase_results.items()
        ):
            budget = len(self.phase_results)
            preview = result[:max_tokens // budget]
            parts.append(
                f"\n{phase} result:\n{preview}"
            )
        return "\n".join(parts)


class HandoffChain:
    def __init__(self, client: Anthropic):
        self.client = client
        self.agents: list[ChainAgent] = []
        self.trace: list[dict] = []

    def add_agent(self, agent: ChainAgent):
        self.agents.append(agent)

    def execute(self, request: str) -> dict:
        context = HandoffContext(
            original_request=request
        )

        for i, agent in enumerate(self.agents):
            if i == 0:
                user_content = request
            else:
                fmt = agent.output_format
                task = fmt or "Continue."
                user_content = (
                    f"{context.summary_for_next()}"
                    f"\n\nYour task: {task}"
                )

            response = (
                self.client.messages.create(
                    model=agent.model,
                    max_tokens=4096,
                    system=agent.role,
                    messages=[{
                        "role": "user",
                        "content": user_content,
                    }],
                )
            )

            result = response.content[0].text
            context.phase_results[
                agent.name
            ] = result

            self.trace.append({
                "phase": i + 1,
                "agent": agent.name,
                "output_preview": result[:200],
            })

        return {
            "request": request,
            "phases": len(self.agents),
            "results": context.phase_results,
            "trace": self.trace,
        }


if __name__ == "__main__":
    # Live demo — needs ANTHROPIC_API_KEY.
    from anthropic import Anthropic as _Anthropic

    chain = HandoffChain(_Anthropic())
    chain.add_agent(ChainAgent(
        name="analyzer",
        role="You diagnose bugs. Do not write fixes.",
    ))
    chain.add_agent(ChainAgent(
        name="implementer",
        role="You write minimal fixes for a diagnosed bug.",
        output_format="Produce the patch for the diagnosis above.",
    ))
    chain.add_agent(ChainAgent(
        name="verifier",
        role="You verify that a fix resolves the reported issue.",
        output_format="Confirm or reject the fix, with reasoning.",
    ))

    out = chain.execute(
        "Login intermittently returns 401 for valid credentials."
    )
    for step in out["trace"]:
        print(f"[{step['phase']}] {step['agent']}: "
              f"{step['output_preview'][:80]}")
