"""Hierarchical Delegation — Lead agent + sub-agents in a tree.

The Lead receives the outer task, decomposes it into sub-tasks, dispatches
to specialist sub-agents, and aggregates results. Each sub-agent gets a
bounded context (the slice it needs, not the whole thing), drastically
cutting token cost vs. asking one agent to do everything.

Anthropic's multi-agent research system, DeerFlow's lead_agent+sub_agents,
LangChain's Supervisor+workers — same mechanism, different names.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class DelegationTask:
    id: str
    description: str
    assigned_to: str
    result: str | None = None


class LeadAgent:
    """Routes sub-tasks to specialists, aggregates results."""

    def __init__(self, sub_agents: dict[str, Callable[[str], str]]):
        self.sub_agents = sub_agents
        self.delegations: list[DelegationTask] = []

    def decompose(self, task: str) -> list[DelegationTask]:
        """Plan sub-tasks. Production: LLM call; demo: simple split by role."""
        out = []
        for i, (name, _) in enumerate(self.sub_agents.items()):
            out.append(DelegationTask(
                id=f"d{i}",
                description=f"From your '{name}' perspective: {task}",
                assigned_to=name,
            ))
        return out

    def dispatch(self, tasks: list[DelegationTask]) -> list[DelegationTask]:
        """Send each task to its assigned sub-agent."""
        for t in tasks:
            t.result = self.sub_agents[t.assigned_to](t.description)
            self.delegations.append(t)
        return tasks

    def aggregate(self, tasks: list[DelegationTask]) -> str:
        """Collect sub-agent outputs into a single response."""
        return "\n\n".join(
            f"## From {t.assigned_to}\n{t.result}" for t in tasks if t.result
        )

    def execute(self, task: str) -> str:
        return self.aggregate(self.dispatch(self.decompose(task)))
