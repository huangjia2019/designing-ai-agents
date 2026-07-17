"""Tool Dispatch — the capability bus connecting agents to tools.

Book: Chapter 6, Listing 6.4 (registry + semantic routing) and Listing 6.5
(execution with retry and self-repair).

The dispatcher keeps a registry of tool definitions, uses a cheap LLM call to
select only the relevant tools for a query (semantic routing keeps the context
window lean), then validates, executes, and self-repairs malformed arguments.

`Tool` and `Toolbox` at the bottom are the small registry the Argus facade
uses (Listing 6.13); §6.8 names this module as the home of both "the Toolbox
and self-repair logic".
"""
import json
from dataclasses import dataclass
from typing import Any, Callable

try:  # keeps this module importable without the SDK installed
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: callable
    retry_count: int = 2


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: str
    error: str = ""


class ToolDispatcher:
    """Capability bus connecting agents to tools."""

    def __init__(self, client: Anthropic):
        self.client = client
        self.registry: dict[
            str, ToolDefinition
        ] = {}

    def register(self, tool):
        self.registry[tool.name] = tool

    def select_tools(  # Semantic routing selects relevant tools only
        self, query: str,
        max_tools: int = 5,
    ) -> list[ToolDefinition]:
        summaries = "\n".join(
            f"- {t.name}: {t.description}"
            for t in self.registry.values()
        )
        resp = (
            self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content":
                    f"Task: {query}\n\n"
                    f"Select up to "
                    f"{max_tools} tools."
                    f"\n\n{summaries}\n\n"
                    f"Comma-separated "
                    f"tool names only.",
                }],
            )
        )
        names = [
            n.strip() for n in
            resp.content[0].text.split(",")
        ]
        return [
            self.registry[n]
            for n in names
            if n in self.registry
        ][:max_tools]

    def execute(  # Retry with self-repair on TypeError
        self, tool_name: str,
        arguments: dict,
    ) -> ToolResult:
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(
                tool_name, False, "",
                f"Unknown: {tool_name}",
            )
        last_err = ""
        retries = tool.retry_count + 1
        for attempt in range(retries):
            try:
                out = tool.handler(**arguments)
                return ToolResult(
                    tool_name, True, str(out),
                )
            except TypeError as e:
                fixed = self._repair_args(
                    tool, arguments, str(e),
                )
                if fixed and fixed != arguments:
                    arguments = fixed
                    continue
                last_err = str(e)
            except Exception as e:
                last_err = str(e)
        return ToolResult(
            tool_name, False, "", last_err,
        )

    def _repair_args(  # LLM fixes malformed arguments via schema
        self, tool, arguments, error,
    ):
        prompt = (
            f"Fix arguments.\n"
            f"Error: {error}\n"
            f"Schema: "
            f"{json.dumps(tool.parameters)}\n"
            f"Args: "
            f"{json.dumps(arguments)}\n"
            f"Reply JSON only."
        )
        try:
            resp = (
                self.client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    messages=[{
                        "role": "user",
                        "content": prompt,
                    }],
                )
            )
            return json.loads(
                resp.content[0].text
            )
        except Exception:
            return None


# --- The small registry the Argus facade wires (Listing 6.13) ----------
# ToolDispatcher above is the chapter's teaching implementation: it talks to
# the model to route and repair. Argus already knows which tool it wants, so
# it only needs the registry half — that is what Tool/Toolbox provide.


@dataclass
class Tool:
    """A tool the agent can call. Atomic, side-effecting, observable."""
    name: str
    description: str
    fn: Callable[..., Any]
    retry_count: int = 2  # cap retries on the same tool


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
