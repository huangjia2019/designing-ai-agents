from dataclasses import dataclass
from enum import Enum
from anthropic import Anthropic

class Complexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

ROUTING_TABLE = {  #A
    Complexity.SIMPLE: {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "thinking": None,
    },
    Complexity.MODERATE: {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "thinking": None,
    },
    Complexity.COMPLEX: {
        "model": "claude-sonnet-4-6",
        "max_tokens": 16384,
        "thinking": {"type": "enabled",
                     "budget_tokens": 32000},
    },
}

def classify_complexity(  #B
    client: Anthropic, query: str
) -> Complexity:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user",
                   "content": CLASSIFY_PROMPT
                   + f"\nQuery: {query}"}],
    )
    first_word = response.content[0].text.split()[0]
    try:
        return Complexity(first_word.lower().rstrip(".:,"))
    except ValueError:
        return Complexity.MODERATE  #C

def route_and_reason(  #D
    client: Anthropic, query: str
) -> dict:
    complexity = classify_complexity(client, query)
    config = ROUTING_TABLE[complexity]

    kwargs = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "messages": [{"role": "user",
                      "content": query}],
    }
    if config["thinking"]:
        kwargs["thinking"] = config["thinking"]  #E

    response = client.messages.create(**kwargs)
    return extract_response(response, complexity)  #F
