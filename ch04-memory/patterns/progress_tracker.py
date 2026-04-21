from dataclasses import dataclass, field
from enum import Enum
import json
import time

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TaskItem:
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    files_modified: list[str] = field(default_factory=list)
    error: str | None = None

class ProgressTracker:
    """Crash-recoverable task tracking."""

    def __init__(self, storage_path: str):
        self.path = storage_path
        self.items: list[TaskItem] = []
        self._load()

    def create_plan(  #A
            self, items: list[str]) -> None:
        """Initialize task plan from high-level description."""
        self.items = [TaskItem(description=d) for d in items]
        self._save()

    def complete(self, index: int, result: str,
                 files: list[str] = None) -> None:  #B
        """Mark item completed and checkpoint immediately."""
        item = self.items[index]
        item.status = TaskStatus.COMPLETED
        item.result = result
        item.files_modified = files or []
        self._save()  # Checkpoint after every completion

    def fail(self, index: int, error: str) -> None:
        """Record a failed item with error context."""
        self.items[index].status = TaskStatus.FAILED
        self.items[index].error = error
        self._save()

    def resumption_context(self) -> str:  #C
        """Generate context for resuming after a reset."""
        completed = [i for i in self.items
                     if i.status == TaskStatus.COMPLETED]
        pending = [i for i in self.items
                   if i.status != TaskStatus.COMPLETED]

        lines = [f"Progress: {len(completed)}/{len(self.items)}",
                 "", "Completed:"]
        for item in completed:
            lines.append(f"  ✓ {item.description}")
            if item.files_modified:
                lines.append(f"    Files: {', '.join(item.files_modified)}")
        lines.append("\nRemaining:")
        for item in pending:
            prefix = "✗" if item.status == TaskStatus.FAILED else "☐"
            lines.append(f"  {prefix} {item.description}")
            if item.error:
                lines.append(f"    Last error: {item.error}")
        return "\n".join(lines)

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump([{
                "description": i.description,
                "status": i.status.value,
                "result": i.result,
                "files": i.files_modified,
                "error": i.error,
            } for i in self.items], f, indent=2)

    def _load(self) -> None:  #D
        try:
            with open(self.path) as f:
                for d in json.load(f):
                    self.items.append(TaskItem(
                        description=d["description"],
                        status=TaskStatus(d["status"]),
                        result=d.get("result"),
                        files_modified=d.get("files", []),
                        error=d.get("error"),
                    ))
        except FileNotFoundError:
            pass
