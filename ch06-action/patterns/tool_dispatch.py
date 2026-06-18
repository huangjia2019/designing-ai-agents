"""Tool Dispatch pattern — model picks the right tool from a registry.

The minimal-tool-set principle (Lance Martin, 2026): ~12 atomic tools beat
100+ specialized ones because the LLM composes them. This module gives you
the simplest dispatch loop: a Tool dataclass, a Toolbox registry, and a
dispatch function that asks the model which tool to call next and runs it.
"""
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Tool:
    """A tool the agent can call. Atomic, side-effecting, observable."""
    name: str
    description: str
    fn: Callable[..., Any]
    retry_count: int = 2  # cap retries on the same tool


@dataclass
class ToolCall:
    """One round of tool invocation: who called what with what result."""
    tool_name: str
    arguments: dict
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class Toolbox:
    """A registry of tools. Keep it small — composition over enumeration."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def describe(self) -> str:
        """Render the toolbox as a prompt-friendly block."""
        return "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools.values()
        )

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


def dispatch(toolbox: Toolbox, name: str, arguments: dict) -> ToolCall:
    """Run the named tool with the given args, capturing output or error."""
    import time
    tool = toolbox.get(name)
    call = ToolCall(tool_name=name, arguments=arguments)
    t0 = time.perf_counter()
    try:
        call.output = tool.fn(**arguments)
    except Exception as e:
        call.error = f"{type(e).__name__}: {e}"
    call.duration_ms = (time.perf_counter() - t0) * 1000
    return call
