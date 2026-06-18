"""MCP Client — Model Context Protocol client stub.

Real MCP integration lives in the anthropic SDK or langchain-mcp-adapters.
This stub mirrors the surface so book examples can demonstrate the shape
without needing a running MCP server. Swap with a real client in
production.
"""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MCPTool:
    """An MCP-exposed tool, identified by server + name."""
    server: str
    name: str
    description: str
    parameters_schema: dict = field(default_factory=dict)


class MCPClient:
    """A minimal MCP client: register servers, list tools, invoke by name."""

    def __init__(self):
        self._servers: dict[str, dict[str, MCPTool]] = {}
        self._invocations: dict[str, Callable[..., Any]] = {}

    def add_server(self, server: str, tools: list[MCPTool],
                   invoker: Callable[[str, str, dict], Any]) -> None:
        """Register a server with its tools and an invocation function.

        invoker(server, tool_name, args) -> result is the actual RPC.
        In production this is the MCP stdio/http transport; in the demo
        you can pass a closure that returns canned results.
        """
        self._servers[server] = {t.name: t for t in tools}
        self._invocations[server] = invoker

    def list_tools(self) -> list[MCPTool]:
        return [t for tools in self._servers.values() for t in tools.values()]

    def invoke(self, server: str, tool_name: str, **kwargs) -> Any:
        if server not in self._servers:
            raise KeyError(f"unknown MCP server: {server}")
        if tool_name not in self._servers[server]:
            raise KeyError(f"unknown tool '{tool_name}' on server '{server}'")
        return self._invocations[server](server, tool_name, kwargs)
