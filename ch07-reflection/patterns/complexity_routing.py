"""Difficulty routing with a declarative model policy."""

from __future__ import annotations

from enum import Enum

try:
    from anthropic import Anthropic
except ImportError:  # Offline behavior tests use a fake client.
    Anthropic = object  # type: ignore[misc,assignment]

from patterns.response_text import all_text, first_text


CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"

CLASSIFY_PROMPT = """Classify how much reasoning the query
below needs.

SIMPLE: a fact, lookup, formatting, or classification call
  that can be answered directly.
MODERATE: ordinary analysis or familiar multi-step work with
  a known shape.
COMPLEX: subtle debugging, architectural judgment, proofs, or
  anything whose method is unclear.

When torn between two difficulty tiers, choose the harder one.
A separate consequence policy handles authorization, evidence,
approval, and containment. Do not encode consequence here.

Length is not difficulty. "Is P=NP?" is COMPLEX; fifty records
to sort by date is SIMPLE.

Answer with one word, SIMPLE or MODERATE or COMPLEX, and
nothing else."""


class Complexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


ROUTING_TABLE = {
    Complexity.SIMPLE: {
        "model": CLASSIFIER_MODEL,
        "max_tokens": 1024,
        "thinking": None,
        "effort": None,
    },
    Complexity.MODERATE: {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "thinking": None,
        "effort": "medium",
    },
    Complexity.COMPLEX: {
        "model": "claude-sonnet-4-6",
        "max_tokens": 16384,
        "thinking": {"type": "adaptive"},
        "effort": "high",
    },
}


def classify_complexity(
    client: Anthropic,
    query: str,
) -> Complexity:
    """Classify difficulty, defaulting ambiguous output to moderate."""
    response = client.messages.create(
        model=CLASSIFIER_MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"{CLASSIFY_PROMPT}\nQuery: {query}",
        }],
    )
    try:
        text = first_text(response).strip()
    except ValueError:
        return Complexity.MODERATE
    if not text:
        return Complexity.MODERATE
    first_word = text.split()[0].lower().rstrip(".:,")
    try:
        return Complexity(first_word)
    except ValueError:
        return Complexity.MODERATE


def route_and_reason(
    client: Anthropic,
    query: str,
) -> dict:
    """Classify, execute the selected path, and normalize its result."""
    complexity = classify_complexity(client, query)
    config = ROUTING_TABLE[complexity]
    kwargs = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "messages": [{"role": "user", "content": query}],
    }
    if config["thinking"]:
        kwargs["thinking"] = config["thinking"]
    if config["effort"]:
        kwargs["output_config"] = {"effort": config["effort"]}
    response = client.messages.create(**kwargs)
    return extract_response(response, complexity)


def extract_response(response, complexity: Complexity) -> dict:
    """Return one stable result shape for all routing tiers."""
    thinking = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "thinking":
            value = getattr(block, "thinking", None)
            if isinstance(value, str) and value:
                thinking.append(value)
    usage = getattr(response, "usage", None)
    return {
        "complexity": complexity.value,
        "model": getattr(response, "model", None),
        "answer": all_text(response),
        "thinking": "\n".join(thinking).strip() or None,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
