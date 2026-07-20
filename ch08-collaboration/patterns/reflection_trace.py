"""ReflectionTrace — observable record of one reflection cycle."""
from dataclasses import dataclass, field


@dataclass
class ReflectionTrace:
    iterations: int = 0
    converged: bool = False
    final_score: float = 0.0
    issue_history: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
