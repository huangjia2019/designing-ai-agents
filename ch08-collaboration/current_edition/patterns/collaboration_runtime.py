"""Provider-neutral runtime seam for Chapter 8 collaboration patterns."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Mapping, Protocol


Tool = Callable[..., Any]


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instructions: str
    tools: tuple[str, ...]


@dataclass(frozen=True)
class AgentContext:
    context_id: str
    parent_id: str
    goal: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AgentResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AgentRuntime(Protocol):
    def run(
        self,
        spec: AgentSpec,
        task: str,
        context: AgentContext,
        tools: Mapping[str, Tool],
        workspace: "SharedWorkspace",
    ) -> AgentResult:
        """Run one fresh agent context and execute its tool calls."""


@dataclass
class VersionedArtifact:
    content: str
    version: int = 1


@dataclass
class ReviewClaim:
    claim_id: str
    location: str
    evidence: str
    consequence: str
    status: str = "open"


@dataclass(frozen=True)
class WriterResponse:
    claim_id: str
    artifact_version: int
    response: str


@dataclass(frozen=True)
class ReturnNotice:
    task_id: str
    return_to: str
    reason: str
    evidence: tuple[str, ...]


@dataclass
class ManagedTask:
    task_id: str
    description: str
    depends_on: tuple[str, ...]
    acceptance: str
    status: str = "pending"
    result_path: str = ""


@dataclass
class SharedWorkspace:
    files: dict[str, VersionedArtifact] = field(default_factory=dict)
    claims: dict[str, ReviewClaim] = field(default_factory=dict)
    responses: list[WriterResponse] = field(default_factory=list)
    returns: list[ReturnNotice] = field(default_factory=list)
    tasks: dict[str, ManagedTask] = field(default_factory=dict)

    def read_file(self, path: str) -> str:
        return self.files[path].content

    def write_file(self, path: str, content: str) -> int:
        current = self.files.get(path)
        version = 1 if current is None else current.version + 1
        self.files[path] = VersionedArtifact(content, version)
        return version

    def post_claim(
        self,
        claim_id: str,
        location: str,
        evidence: str,
        consequence: str,
    ) -> None:
        self.claims[claim_id] = ReviewClaim(
            claim_id,
            location,
            evidence,
            consequence,
        )

    def close_claim(self, claim_id: str) -> None:
        self.claims[claim_id].status = "closed"

    def respond_to_claim(
        self,
        claim_id: str,
        artifact_version: int,
        response: str,
    ) -> None:
        self.responses.append(
            WriterResponse(claim_id, artifact_version, response)
        )

    def return_handoff(
        self,
        task_id: str,
        return_to: str,
        reason: str,
        evidence: tuple[str, ...] = (),
    ) -> None:
        self.returns.append(
            ReturnNotice(task_id, return_to, reason, evidence)
        )

    def read_board(self) -> dict[str, str]:
        return {
            task_id: task.status
            for task_id, task in self.tasks.items()
        }


class SubagentSpawner:
    """Create fresh contexts from an agent spec, task, and tool set."""

    def __init__(
        self,
        runtime: AgentRuntime,
        workspace: SharedWorkspace,
        registry: Mapping[str, Tool],
    ) -> None:
        self.runtime = runtime
        self.workspace = workspace
        self.registry = dict(registry)
        self.context_ids: list[str] = []
        self._counter = 0
        self._lock = Lock()

    def add_tool(self, name: str, tool: Tool) -> None:
        self.registry[name] = tool

    def spawn(
        self,
        spec: AgentSpec,
        task: str,
        goal: str,
        parent_id: str,
        payload: Mapping[str, Any],
    ) -> AgentResult:
        with self._lock:
            self._counter += 1
            context_id = f"ctx-{self._counter}"
            self.context_ids.append(context_id)
        selected = {
            name: self.registry[name]
            for name in spec.tools
        }
        context = AgentContext(
            context_id=context_id,
            parent_id=parent_id,
            goal=goal,
            payload=dict(payload),
        )
        return self.runtime.run(
            spec,
            task,
            context,
            selected,
            self.workspace,
        )
