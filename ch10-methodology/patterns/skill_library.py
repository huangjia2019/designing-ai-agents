"""Skill Library / Skill Package — reusable capability extraction + retrieval.

A skill is a verified, reusable capability the agent extracts from a
successful execution and keeps for future use. Claude Code's pattern:
all skill descriptions resident as a routing catalog, skill bodies
loaded lazily when the skill is selected.
"""
from dataclasses import dataclass, field
import hashlib
from typing import Callable


@dataclass
class Skill:
    id: str
    name: str
    description: str
    body: str
    verified: bool = False
    usage_count: int = 0
    success_rate: float = 0.0


class SkillLibrary:
    """Stores skills indexed by content hash; production retrieves by embedding."""

    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def extract_skill(self, name: str, description: str, body: str) -> Skill:
        """Distill an execution trace into a reusable skill."""
        sid = hashlib.md5(body.encode("utf-8")).hexdigest()[:12]
        return Skill(id=sid, name=name, description=description, body=body)

    def verify_skill(self, skill: Skill, verifier: Callable[[Skill], bool]) -> bool:
        verified = verifier(skill)
        skill.verified = verified
        return verified

    def add_skill(self, skill: Skill) -> bool:
        if not skill.verified:
            return False
        self.skills[skill.id] = skill
        return True

    def retrieve(self, task: str, max_skills: int = 5) -> list[Skill]:
        """Pedagogical: linear scan over descriptions. In best practice,
        descriptions are the index, bodies the lazy payload — production
        retrieves top-k by embedding similarity."""
        terms = [t.lower() for t in task.split() if len(t) > 3]
        scored = sorted(
            ((sum(1 for t in terms if t in s.description.lower()), s)
             for s in self.skills.values()),
            reverse=True, key=lambda x: x[0],
        )
        return [s for score, s in scored[:max_skills] if score > 0]

    def update_lesson_effectiveness(self, skill_id: str, helped: bool) -> None:
        if skill_id not in self.skills:
            return
        s = self.skills[skill_id]
        s.usage_count += 1
        prior = s.success_rate * (s.usage_count - 1)
        s.success_rate = (prior + (1.0 if helped else 0.0)) / s.usage_count
