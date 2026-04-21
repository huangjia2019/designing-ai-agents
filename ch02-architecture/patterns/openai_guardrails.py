from agents import Agent, InputGuardrail, OutputGuardrail

agent = Agent(
    name="customer_service",
    instructions="Help customers with billing questions.",
    input_guardrails=[  #A
        InputGuardrail(no_pii_in_prompts),
        InputGuardrail(topic_within_scope),
    ],
    output_guardrails=[  #B
        OutputGuardrail(no_hallucinated_prices),
        OutputGuardrail(professional_tone),
    ],
)
