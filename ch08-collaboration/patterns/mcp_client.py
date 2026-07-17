"""MCP Client — dynamic tool discovery over the Model Context Protocol.

Book: Chapter 6, Listing 6.6 (`connect_mcp_server`).

MCP is JSON-RPC 2.0 over stdio or HTTP. `connect_mcp_server` launches a
server process, initializes a session, asks the server what tools it has,
and converts the returned schemas into the shape the Anthropic Messages API
expects. Discovery happens when the coroutine is awaited, never at import
time: this module opens no connection and constructs no client on import.

`MCPTool` / `MCPClient` at the bottom are an offline stub from an earlier
draft. No chapter imports them. They are retained pending an author call on
whether an offline surface is still wanted for demos with no live server.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

try:  # keeps this module importable without the SDK installed
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # pragma: no cover
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


async def connect_mcp_server(
    server_command: str,
    args: list[str],
) -> dict:
    """Discover tools from MCP server.

    Spawns `server_command args...` as an MCP stdio server, initializes the
    session, and returns its tools already converted to Anthropic tool
    schemas. The connection is opened and closed inside this call.
    """
    if stdio_client is None:  # pragma: no cover
        raise RuntimeError(
            "connect_mcp_server needs the MCP SDK: pip install mcp"
        )

    server_params = StdioServerParameters(
        command=server_command, args=args,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

            anthropic_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools.tools
            ]

            return {
                "server": server_command,
                "tools": anthropic_tools,
                "tool_count": len(anthropic_tools),
            }


# ---------------------------------------------------------------------------
# Offline stub — not imported by any chapter. See the module docstring.
# ---------------------------------------------------------------------------


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
