"""Helpers for reading text blocks from provider responses.

The examples deliberately avoid assuming that ``content[0]`` is text. A
thinking or tool block may come first, so every Chapter 5 pattern uses the
same small boundary helper.
"""


def first_text(response) -> str:
    """Return the first text block or raise when the response has none."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) in (None, "text"):
            value = getattr(block, "text", None)
            if isinstance(value, str):
                return value
    raise ValueError("Response contained no text block")


def all_text(response) -> str:
    """Join every text block, preserving their order."""
    values = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) in (None, "text"):
            value = getattr(block, "text", None)
            if isinstance(value, str) and value:
                values.append(value)
    return "\n".join(values).strip()
