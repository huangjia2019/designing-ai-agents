"""Hierarchical Delegation — Collaboration x Hierarchy.

A manager decomposes a goal into structured subtasks, delegates each to a
specialized worker, and coordinates execution through topological
scheduling. Model tiering is the point: an expensive manager plans once,
cheap workers execute many times.

Listing 8.11 — WorkerRole / Subtask schema + manager decompose
Listing 8.12 — execute_worker
Listing 8.13 — coordinate (topological scheduling)
Listing 8.14 — _parse_subtasks / _build
"""
from dataclasses import dataclass, field
from enum import Enum
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]


class WorkerRole(Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    GENERAL = "general"


@dataclass
class Subtask:
    id: str
    description: str
    role: WorkerRole
    dependencies: list[str] = field(
        default_factory=list
    )
    result: str = ""
    status: str = "pending"


class HierarchicalDelegation:
    def __init__(
        self,
        client: Anthropic,
        manager_model: str = (
            "claude-sonnet-4-6"
        ),
        worker_model: str = (
            "claude-haiku-4-5-20251001"
        ),
    ):
        self.client = client
        self.manager_model = manager_model
        self.worker_model = worker_model

    def decompose(
        self, goal: str
    ) -> list[Subtask]:
        prompt = (
            f"Decompose into 3-8 subtasks:\n"
            f"Goal: {goal}\n\n"
            f"For each:\n"
            f"TASK_ID: [T1]\n"
            f"ROLE: [backend/frontend/...]\n"
            f"DESCRIPTION: [actionable]\n"
            f"DEPENDS_ON: [IDs or none]"
        )
        response = (
            self.client.messages.create(
                model=self.manager_model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": prompt,
                }],
            )
        )
        return self._parse_subtasks(
            response.content[0].text
        )

    def execute_worker(
        self,
        subtask: Subtask,
        context: dict[str, str],
    ) -> str:
        roles = {
            WorkerRole.BACKEND: (
                "Expert backend engineer."
            ),
            WorkerRole.FRONTEND: (
                "Expert frontend engineer."
            ),
            WorkerRole.TESTING: (
                "Expert QA engineer."
            ),
            WorkerRole.DOCUMENTATION: (
                "Technical writer."
            ),
            WorkerRole.GENERAL: (
                "Skilled software engineer."
            ),
        }
        dep_ctx = ""
        for dep_id in subtask.dependencies:
            if dep_id in context:
                dep_ctx += (
                    f"\nFrom {dep_id}:\n"
                    f"{context[dep_id][:500]}\n"
                )
        response = (
            self.client.messages.create(
                model=self.worker_model,
                max_tokens=4096,
                system=roles.get(
                    subtask.role,
                    roles[WorkerRole.GENERAL],
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Execute:\n"
                        f"{subtask.description}"
                        f"{dep_ctx}"
                    ),
                }],
            )
        )
        return response.content[0].text

    def coordinate(
        self, goal: str
    ) -> dict:
        subtasks = self.decompose(goal)
        context: dict[str, str] = {}
        completed = []
        max_iter = len(subtasks) * 2

        for _ in range(max_iter):
            ready = [
                t for t in subtasks
                if t.status == "pending"
                and all(
                    d in context
                    for d in t.dependencies
                )
            ]
            if not ready:
                break
            for task in ready:
                task.status = "running"
                try:
                    result = (
                        self.execute_worker(
                            task, context
                        )
                    )
                    task.result = result
                    task.status = "completed"
                    context[task.id] = result
                    completed.append(task)
                except Exception as e:
                    task.status = "failed"
                    task.result = f"Error: {e}"

        return {
            "goal": goal,
            "total": len(subtasks),
            "completed": len(completed),
            "results": {
                t.id: t.result[:300]
                for t in completed
            },
        }

    def _parse_subtasks(
        self, text: str
    ) -> list[Subtask]:
        subtasks = []
        current: dict = {}
        for line in text.split("\n"):
            ln = line.strip()
            if ln.startswith("TASK_ID:"):
                if current.get("id"):
                    subtasks.append(
                        self._build(current)
                    )
                current = {
                    "id": ln.split(":", 1)[1]
                    .strip()
                }
            elif ln.startswith("ROLE:"):
                current["role"] = (
                    ln.split(":", 1)[1]
                    .strip().lower()
                )
            elif ln.startswith("DESCRIPTION:"):
                current["description"] = (
                    ln.split(":", 1)[1].strip()
                )
            elif ln.startswith("DEPENDS_ON:"):
                deps = (
                    ln.split(":", 1)[1].strip()
                )
                current["deps"] = (
                    []
                    if deps.lower() == "none"
                    else [
                        d.strip()
                        for d in deps.split(",")
                    ]
                )
        if current.get("id"):
            subtasks.append(
                self._build(current)
            )
        return subtasks

    def _build(
        self, data: dict
    ) -> Subtask:
        role_map = {
            r.value: r for r in WorkerRole
        }
        return Subtask(
            id=data["id"],
            description=data.get(
                "description", ""
            ),
            role=role_map.get(
                data.get("role", "general"),
                WorkerRole.GENERAL,
            ),
            dependencies=data.get("deps", []),
        )


if __name__ == "__main__":
    # Live demo — needs ANTHROPIC_API_KEY.
    from anthropic import Anthropic as _Anthropic

    hd = HierarchicalDelegation(_Anthropic())
    out = hd.coordinate(
        "Build a URL shortener with auth, storage, API, and tests."
    )
    print(f"total={out['total']} completed={out['completed']}")
    for tid, preview in out["results"].items():
        print(f"  {tid}: {preview[:70]}")
