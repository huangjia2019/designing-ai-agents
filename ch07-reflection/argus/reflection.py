from typing import Callable
# argus/reflection.py — Argus reflection module, Ch7 snapshot.
#
# Tracks §7.x 'Argus checkpoint' which promises this module wires:
#   * critic loop on review quality  → GeneratorCriticLoop
#   * skill library for reusable review playbooks → SkillLibrary
#   * experience replay (L0/L1/L2 hierarchy)      → ExperienceReplay
# self_heal lives in argus/self_heal.py (paired sibling).
from dataclasses import dataclass

from patterns.generator_critic import GeneratorCriticLoop, Critique
from patterns.skill_library import SkillLibrary, Skill
from patterns.experience_replay import ExperienceReplay, ExecutionTrace
from patterns.reflection_trace import ReflectionTrace


@dataclass
class ReviewQualityCheck:
    """The critique target for Argus reviews: are findings real and ranked right?"""
    findings_count: int
    likely_false_positives: int
    likely_missed: int
    score: float


class ArgusReflection:
    """Argus's self-improvement loop: critic loop + skills + experience."""

    def __init__(self):
        self.skills = SkillLibrary()
        self.experience = ExperienceReplay()
        self.last_trace: ReflectionTrace | None = None

    def critique_review(self, review_text: str, tool_evidence: str = "") -> Critique:
        """Cheap heuristic critic — production would call an LLM here.

        For the Ch7 worked example (Argus PR #4287), the critic compares
        review claims against pytest evidence and drops findings that
        cannot be reproduced.
        """
        findings = review_text.count("severity")
        # Toy heuristic: if evidence mentions "passes" without "fails", suspect FPs.
        false_positive_signal = (
            "passes" in tool_evidence.lower()
            and "fails" not in tool_evidence.lower()
            and findings > 0
        )
        likely_fp = findings // 2 if false_positive_signal else 0
        score = max(0.0, 1.0 - (likely_fp / max(findings, 1)))
        return Critique(
            score=score,
            approved=score >= 0.8,
            feedback_text=(
                f"Suspect {likely_fp}/{findings} findings as false positives "
                f"based on tool evidence." if likely_fp else "Findings consistent with evidence."
            ),
        )

    def refine(self, review_text: str, regenerate: Callable,
               tool_check: Callable | None = None) -> dict:
        """Run generator-critic over a draft review until converged."""
        loop = GeneratorCriticLoop(
            generate=lambda task, ctx: regenerate(task, ctx) if ctx else review_text,
            critique_fn=lambda task, output, tool_fb: self.critique_review(output, tool_fb),
            max_iterations=3,
            quality_threshold=0.8,
        )
        result = loop.refine(task="argus_review", tool_fn=tool_check)
        # Field names follow Listing 7.1 (task_id / critic_iterations /
        # critic_converged / quality_scores / tool_grounded). Listing 7.19
        # prints an older ReflectionTrace shape (iterations / converged /
        # final_score); the two listings disagree and 7.1 is the dataclass
        # definition, so it wins here. `final_score` is quality_scores[-1].
        self.last_trace = ReflectionTrace(
            task_id="argus_review",
            critic_iterations=result["iterations"],
            critic_converged=result["converged"],
            quality_scores=[h["score"] for h in loop.history],
            tool_grounded=tool_check is not None,
        )
        return result

    def record_outcome(self, task: str, succeeded: bool, error: str | None = None) -> None:
        """Feed an execution into experience replay for future L2 lessons."""
        self.experience.record_trace(ExecutionTrace(
            task=task,
            outcome="success" if succeeded else "failure",
            error=error or "",
        ))

    def extract_skill(self, task: str, solution: str, context: str = "") -> Skill | None:
        """Extract, verify, and store in one step. Needs a live client.

        Beyond Listing 7.19: a convenience wrapper over Listings 7.7/7.8.
        add_skill self-verifies, so an unverified candidate never lands.
        """
        skill = self.skills.extract_skill(task, solution, context)
        return skill if self.skills.add_skill(skill) else None
