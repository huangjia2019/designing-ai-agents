"""ReflectionTrace — observable record of one reflection cycle.

Book: Chapter 7, Listing 7.1.

The four metrics §7.1 argues are worth tracking: critic convergence rate,
iteration efficiency, skill hit rate, and lesson accuracy. The
`tool_grounded` flag is what makes the A/B comparison possible — it
separates Variant 3 (deterministic critic) from Variant 1 (self-critique),
which §7.2 shows differ sharply in reliability.
"""
from dataclasses import dataclass, field


@dataclass
class ReflectionTrace:
    """Observable record of one reflection cycle."""
    task_id: str
    critic_iterations: int = 0      # Detect when loop spins without improving
    critic_converged: bool = False
    quality_scores: list[float] = field(
        default_factory=list
    )
    skills_retrieved: int = 0
    skills_hit: int = 0             # Skills that contributed to success
    lessons_applied: int = 0
    lessons_effective: int = 0
    tool_grounded: bool = False     # Reliable vs. unreliable critique

    @property
    def iteration_efficiency(self) -> float:
        if len(self.quality_scores) < 2:
            return 0
        return (
            (self.quality_scores[-1]
             - self.quality_scores[0])
            / len(self.quality_scores)
        )

    @property
    def skill_hit_rate(self) -> float:
        if not self.skills_retrieved:
            return 0
        return (
            self.skills_hit
            / self.skills_retrieved
        )

    def log(self):
        mode = (
            "tool-grounded"
            if self.tool_grounded
            else "self-critique"
        )
        print(
            f"  [{self.task_id}] {mode} "
            f"iters={self.critic_iterations}"
            f" converged="
            f"{self.critic_converged} "
            f"skill_hit="
            f"{self.skill_hit_rate:.0%}"
        )
