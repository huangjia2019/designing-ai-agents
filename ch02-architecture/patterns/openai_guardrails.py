"""Listing 2.3 — OpenAI Agents SDK guardrails (illustrative).

The book lists four guardrail callbacks by name (no_pii_in_prompts,
topic_within_scope, no_hallucinated_prices, professional_tone) but does
not define their bodies. Placeholder stubs are supplied here so the file
imports cleanly; swap them for real checks in production.

API NOTE: the real openai-agents SDK (v0.0.23+) takes the callback as a
positional argument:
    InputGuardrail(guardrail_function, name=None, run_in_parallel=True)
The book's `InputGuardrail(check=...)` form is outdated — we use the
current API below.
"""
from agents import Agent, InputGuardrail, OutputGuardrail


# Placeholder guardrail callbacks — replace with your own implementations.
def no_pii_in_prompts(ctx, agent, prompt):
    return {"ok": True}


def topic_within_scope(ctx, agent, prompt):
    return {"ok": True}


def no_hallucinated_prices(ctx, agent, output):
    return {"ok": True}


def professional_tone(ctx, agent, output):
    return {"ok": True}


agent = Agent(
    name="customer_service",
    instructions="Help customers with billing questions.",
    input_guardrails=[
        InputGuardrail(no_pii_in_prompts),
        InputGuardrail(topic_within_scope),
    ],
    output_guardrails=[
        OutputGuardrail(no_hallucinated_prices),
        OutputGuardrail(professional_tone),
    ],
)
