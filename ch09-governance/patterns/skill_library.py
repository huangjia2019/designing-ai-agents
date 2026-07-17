"""Skill Library / Skill Package — reusable capability extraction + retrieval.

Book: Chapter 7, Listings 7.6-7.9.

A skill is a verified, reusable capability the agent extracts from a
successful execution and keeps for future use. Claude Code's pattern:
all skill descriptions resident as a routing catalog, skill bodies
loaded lazily when the skill is selected.

Extraction produces candidates; verification gates them. Only skills that
pass verify_skill enter the library, because an unverified skill compounds
its failure across every future invocation that retrieves it.
"""
import hashlib
from dataclasses import dataclass, field

try:  # keeps this module importable without the SDK installed
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


@dataclass
class Skill:
    name: str
    description: str
    implementation: str
    category: str
    dependencies: list[str] = field(
        default_factory=list
    )
    verified: bool = False
    usage_count: int = 0
    success_rate: float = 1.0

    @property
    def id(self) -> str:
        return hashlib.md5(
            f"{self.name}:{self.description}"
            .encode()
        ).hexdigest()[:12]


class SkillLibrary:
    """Stores skills indexed by content hash.

    `client` carries a None default so the library is constructible
    offline: the cumulative Argus facade (argus/reflection.py, Listing
    7.19) builds a SkillLibrary with no arguments and only ever calls
    retrieve() against an empty catalog, which short-circuits before it
    needs a client. Every call the book shows — SkillLibrary(client) —
    behaves exactly as printed.
    """

    def __init__(
        self,
        client: "Anthropic | None" = None,
        model: str = "claude-sonnet-4-6",
    ):
        self.client = client
        self.model = model
        self.skills: dict[str, Skill] = {}

    def extract_skill(  # Distills execution into reusable template
        self,
        task: str,
        solution: str,
        context: str = "",
    ) -> Skill:
        prompt = (
            "A task was completed. "
            "Extract a reusable skill.\n\n"
            f"Task: {task}\n"
            f"Solution: {solution}\n"
        )
        if context:
            prompt += f"Context: {context}\n"
        prompt += (
            "\nCreate a skill with:\n"
            "NAME: [snake_case]\n"
            "DESCRIPTION: [one sentence]\n"
            "CATEGORY: [debugging|testing|"
            "code_generation|analysis]\n"
            "IMPLEMENTATION: [reusable code]\n"
            "DEPENDENCIES: [names or none]"
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[
                {"role": "user",
                 "content": prompt}
            ],
        )
        return self._parse_skill(
            response.content[0].text
        )

    def verify_skill(  # Critical gate; rejects unverified skills
        self, skill: Skill
    ) -> bool:
        prompt = (
            "Evaluate this skill:\n\n"
            f"Name: {skill.name}\n"
            f"Description: {skill.description}\n"
            f"Implementation:\n"
            f"{skill.implementation}\n\n"
            "Check correctness, edge cases, "
            "reusability, security.\n"
            "Reply VERIFIED or REJECTED."
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {"role": "user",
                 "content": prompt}
            ],
        )
        verified = (
            "VERIFIED"
            in response.content[0].text.upper()
        )
        skill.verified = verified
        return verified

    def add_skill(self, skill: Skill) -> bool:
        if not skill.verified:
            if not self.verify_skill(skill):
                return False
        self.skills[skill.id] = skill
        return True

    def retrieve(  # Routes tasks to matching skills
        self,
        task: str,
        max_skills: int = 5,
    ) -> list[Skill]:
        # Pedagogical version: loads every skill's full content into
        # context. In best practice, descriptions are the index, bodies
        # the lazy payload; production swaps this LLM router for
        # embedding similarity once the library passes ~100 skills.
        if not self.skills:
            return []
        catalog = "\n".join(
            f"- {s.name}: {s.description} "
            f"(used {s.usage_count}x, "
            f"success: {s.success_rate:.0%})"
            for s in self.skills.values()
        )
        prompt = (
            f"Given this task:\n{task}\n\n"
            f"Which skills are relevant? "
            f"Select up to {max_skills}.\n\n"
            f"Available:\n{catalog}\n\n"
            f"Reply with comma-separated names."
        )
        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[
                {"role": "user",
                 "content": prompt}
            ],
        )
        result = response.content[0].text.strip()
        if "NONE" in result.upper():
            return []
        selected = {
            n.strip()
            for n in result.split(",")
        }
        return [
            s for s in self.skills.values()
            if s.name in selected
        ][:max_skills]

    # --- Beyond Listings 7.6-7.9 --------------------------------------
    # Listing 7.7 calls self._parse_skill(...), but the book never prints
    # the parser. It reads back the five markers the extraction prompt
    # writes (NAME / DESCRIPTION / CATEGORY / IMPLEMENTATION /
    # DEPENDENCIES) — which is the whole reason §7.4 gives that prompt a
    # rigid format: "so the parser downstream can populate the dataclass
    # fields without LLM ambiguity."
    _MARKERS = (
        "NAME", "DESCRIPTION", "CATEGORY",
        "IMPLEMENTATION", "DEPENDENCIES",
    )

    @classmethod
    def _parse_skill(cls, text: str) -> Skill:
        fields: dict[str, list[str]] = {}
        current: str | None = None
        for line in text.split("\n"):
            marker = line.split(":", 1)[0].strip().upper()
            if marker in cls._MARKERS and ":" in line:
                current = marker
                fields[current] = [line.split(":", 1)[1].strip()]
            elif current:
                fields[current].append(line)
        joined = {k: "\n".join(v).strip() for k, v in fields.items()}
        raw_deps = joined.get("DEPENDENCIES", "")
        deps = (
            []
            if not raw_deps or raw_deps.lower() in ("none", "[]")
            else [d.strip() for d in raw_deps.split(",") if d.strip()]
        )
        return Skill(
            name=joined.get("NAME", "unnamed_skill"),
            description=joined.get("DESCRIPTION", ""),
            implementation=joined.get("IMPLEMENTATION", ""),
            category=joined.get("CATEGORY", "analysis"),
            dependencies=deps,
        )
