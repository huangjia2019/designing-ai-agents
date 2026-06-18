"""Permission Gate — capability-based access control before any side effect.

Each agent has a set of granted capabilities. Before any tool call, the
gate checks: does this agent currently hold this capability? Capabilities
can be revoked dynamically (trust demotion) without re-architecting.
"""
from dataclasses import dataclass, field
from enum import Enum


class Capability(Enum):
    READ_FILES = "read_files"
    RUN_LINT = "run_lint"
    RUN_TESTS = "run_tests"
    WRITE_FILES = "write_files"
    NETWORK_FETCH = "network_fetch"
    SHELL_EXEC = "shell_exec"


@dataclass
class AgentIdentity:
    name: str
    capabilities: set[Capability] = field(default_factory=set)


class PermissionGate:
    """Capability check before any side-effect action."""

    def __init__(self):
        self.agents: dict[str, AgentIdentity] = {}

    def register(self, identity: AgentIdentity) -> None:
        self.agents[identity.name] = identity

    def grant(self, agent_name: str, cap: Capability) -> None:
        self.agents[agent_name].capabilities.add(cap)

    def revoke(self, agent_name: str, cap: Capability) -> None:
        self.agents[agent_name].capabilities.discard(cap)

    def check(self, agent_name: str, cap: Capability) -> tuple[bool, str]:
        if agent_name not in self.agents:
            return False, f"unknown agent: {agent_name}"
        if cap not in self.agents[agent_name].capabilities:
            return False, f"agent '{agent_name}' lacks capability '{cap.value}'"
        return True, ""
