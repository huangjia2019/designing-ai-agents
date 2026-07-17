from dataclasses import dataclass
from enum import Enum
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

# Kept short on purpose. This prompt is billed on every
# query the router sees, so it has to stay far cheaper than
# the tier it saves; a classifier that reasons at length
# about complexity has already spent the savings.
CLASSIFY_PROMPT = """Classify how much reasoning the query
below needs.

SIMPLE: a fact, a lookup, a formatting or classification
  call that can be answered directly.
MODERATE: summarizing, ordinary analysis, familiar
  multi-step work with a known shape.
COMPLEX: debugging subtle behaviour, architectural
  judgement, proofs, anything whose method is unclear.

When torn between two tiers, name the harder one: sending a
hard query to a weak model produces a wrong answer, while
sending an easy one to a strong model only wastes money. If
a wrong answer would be dangerous to the person asking,
answer COMPLEX regardless of how easy the query looks.

Length is not difficulty. "Is P=NP?" is COMPLEX; fifty
records to sort by date is SIMPLE.

Answer with one word, SIMPLE or MODERATE or COMPLEX, and
nothing else."""

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


# --- extractor behind route_and_reason above ------------
# Listing 5.3 prints the call to extract_response(); this is
# the function it calls. Kept below the listing boundary so
# the router above still reads as it does in the book.


def extract_response(response, complexity: Complexity) -> dict:
    """Flatten one tier's reply into the shape all tiers share.

    The point of the routing table is that callers should not
    care which tier answered, so every tier has to come back
    the same shape. Only the COMPLEX tier returns thinking
    blocks; the other two report thinking=None rather than
    omitting the key, so a caller never has to ask which tier
    it got before reading the result.

    The token counts ride along because this pattern exists to
    move a number on a bill. A router nobody can audit is a
    router nobody will trust with the model choice.
    """
    thinking: list[str] = []
    answer: list[str] = []
    for block in getattr(response, "content", []):
        kind = getattr(block, "type", None)
        if kind == "thinking":
            thinking.append(getattr(block, "thinking", ""))
        elif kind == "text":
            answer.append(getattr(block, "text", ""))

    usage = getattr(response, "usage", None)
    return {
        "complexity": complexity.value,
        "model": getattr(response, "model", None),
        "answer": "\n".join(x for x in answer if x).strip(),
        "thinking": ("\n".join(x for x in thinking if x).strip()
                     or None),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
