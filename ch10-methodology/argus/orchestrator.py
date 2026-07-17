# argus/orchestrator.py — Ch10 capstone. Listing 10.1 made real.
#
# The §10.10 promise:
#     "This is not a toy example. Every method call maps to a working class
#      from Chapters 3-9. The composition is the simplest possible code that
#      wires them together."
#
# This file is the cash-out. ArgusOrchestrator instantiates ONE class per
# cognitive function (perception → memory → reasoning → action → reflection
# → collaboration → governance) and runs them in the composition flow
# described in §10.10:
#
#   1. governance gates the review through ArgusGovernance.run_tool()
#   2. perception gathers the relevant files
#   3. memory retrieves prior lessons for this project
#   4. collaboration optionally fans out to sub-agents on complex diffs
#   5. action runs deterministic verifiers (lint/tests) for evidence
#   6. reasoning produces the verdict, routed by complexity
#   7. reflection critiques the verdict, drops likely false positives
#   8. memory persists the new lesson
#   9. governance closes the trace and reports the dashboard
#
# Each step is observable via its own trace dataclass. The orchestrator
# returns a single OrchestrationResult that gathers them all.

from dataclasses import dataclass, field
from typing import Any

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance
from .core import _governance_meta

from patterns.progressive_commitment import TrustLevel


@dataclass
class OrchestrationResult:
    """Capstone return type. One per review, gathers every cognitive trace."""
    review: ReviewResult | None
    perception_trace: PerceptionTrace | None
    action_log: list = field(default_factory=list)
    reflection_meta: dict = field(default_factory=dict)
    collaboration_meta: dict = field(default_factory=dict)
    governance_meta: dict = field(default_factory=dict)
    blocked_reason: str | None = None


class ArgusOrchestrator:
    """The full Argus, wired together. One class per cognitive function."""

    def __init__(self, *,
                 memory: ArgusMemory,
                 reasoning: ArgusReasoning | None = None,
                 action: ArgusAction | None = None,
                 reflection: ArgusReflection | None = None,
                 collaboration: ArgusCollaboration | None = None,
                 governance: ArgusGovernance | None = None):
        # Each module is its own injectable class — composition, not inheritance.
        self.memory = memory
        self.reasoning = reasoning or ArgusReasoning()
        self.action = action or ArgusAction()
        self.reflection = reflection or ArgusReflection()
        self.collaboration = collaboration or ArgusCollaboration()
        # Ch9's trust ladder (OBSERVE/ASSIST/SUPERVISED/AUTONOMOUS/
        # DELEGATED) replaced the old four-rung one. The capstone used to
        # start at ACT_THEN_REVIEW: act without pre-approval, human reviews
        # the record afterwards. AUTONOMOUS is that same contract on the
        # new ladder — everything but CRITICAL runs unattended, and the
        # Observability Harness keeps the record for the review.
        self.governance = governance or ArgusGovernance(
            initial_trust=TrustLevel.AUTONOMOUS,
        )

    def review(self, diff: str, project: str,
               repo_root: str = ".", budget: int = 50_000,
               delegate_complex: bool = True,
               verify_with_tools: bool = True,
               refine: bool = True,
               ask_human=None) -> OrchestrationResult:
        """The capstone review() flow from §10.10."""

        self.governance.start_review(project)

        # 1. governance — is this review allowed at all?
        perceive = self.governance.run_tool(
            "read_file", {"repo": repo_root},
            execute_fn=lambda tool, args: {"repo": args["repo"]},
            ask_human=ask_human,
        )
        if "error" in perceive:
            return OrchestrationResult(
                review=None, perception_trace=None,
                blocked_reason=perceive["error"],
                governance_meta={
                    "allowed": False, "reason": perceive["error"],
                },
            )

        # 2. perception — gather files
        selected, p_trace = gather_review_context(diff, repo_root, budget)

        # 3. memory (before) — recall prior lessons
        past_lessons = self.memory.before_review(
            project=project,
            diff_summary=diff[:300].replace("\n", " "),
        )

        # 4. collaboration — fan out to sub-agents on complex diffs
        collab_meta = {"delegated": False}
        sub_synthesis = ""
        if delegate_complex and diff.count("\n") > 100:
            sub_synthesis = self.collaboration.parallel_review(diff)
            collab_meta = {
                "delegated": True,
                "agents": self.collaboration.trace.agent_count,
                "token_multiplier": round(
                    self.collaboration.trace.token_multiplier, 2
                ),
                "handoff_fidelity": round(
                    self.collaboration.trace.handoff_fidelity, 2
                ),
                "wall_time_ms": self.collaboration.trace.wall_time_ms,
            }

        # 5. action — gather deterministic verifier evidence (gated by governance)
        # run_tool books the trust outcome itself, so the old separate
        # report_outcome call is gone: success is 'no error came back'.
        action_evidence: list[str] = []
        if verify_with_tools:

            def _lint(tool: str, args: dict) -> dict:
                trace = self.action.run_lint(repo_root=args["repo"])
                if trace.guardrail_blocked:
                    return {"error": f"guardrail: {trace.guardrail_reason}"}
                if trace.error:
                    return {"error": trace.error}
                return {"trace": trace}

            lint_result = self.governance.run_tool(
                "run_command", {"cmd": "lint", "repo": repo_root},
                execute_fn=_lint, ask_human=ask_human,
            )
            if "error" in lint_result:
                action_evidence.append(
                    f"lint: blocked by governance ({lint_result['error']})"
                )
            elif lint_result["trace"].output:
                action_evidence.append(
                    f"lint: rc={lint_result['trace'].output.get('returncode')}"
                )

        # 6. reasoning — produce the verdict
        sections = []
        if past_lessons:
            sections.append("### Past lessons\n" + "\n".join(f"- {l}" for l in past_lessons))
        if sub_synthesis:
            sections.append("### Sub-agent synthesis\n" + sub_synthesis)
        if action_evidence:
            sections.append("### Verification evidence\n" + "\n".join(action_evidence))
        for c in selected:
            sections.append(
                f"### {c.path}  [{c.relevance}, {c.tokens} tokens]\n```\n{c.content}\n```"
            )
        augmented = f"{diff}\n\n# Project context:\n" + "\n\n".join(sections) if sections else diff
        result = self.reasoning.review(augmented)

        # 7. reflection — critic over the verdict
        reflection_meta: dict = {}
        if refine:
            refined = self.reflection.refine(
                review_text=result.verdict,
                regenerate=lambda task, ctx: self.reasoning.review(
                    f"{augmented}\n\n# Critic feedback:\n{ctx}"
                ).verdict,
                tool_check=lambda text: " ".join(action_evidence),
            )
            reflection_meta = {
                "iterations": refined["iterations"],
                "converged": refined["converged"],
                "final_score": refined["final_score"],
            }
            result.verdict = refined["output"]
            result.confidence = min(result.confidence, refined["final_score"])

        # 8. memory (after) + outcome bookkeeping
        converged = reflection_meta.get("converged", True)
        self.governance.trust.record_action(success=converged)
        self.reflection.record_outcome(
            task=f"review:{project}",
            succeeded=converged,
        )
        self.memory.after_review(review_summary=result.verdict[:200], project=project)

        # 9. governance — close the trace, report the dashboard (§9.5).
        # Listing 10.1's '#H Governance: record outcome for observability
        # and trust tracking' is this call.
        dashboard = self.governance.finish_review(success=converged)
        governance_meta = _governance_meta(
            self.governance, allowed=True, dashboard=dashboard,
        )

        return OrchestrationResult(
            review=result,
            perception_trace=p_trace,
            action_log=self.action.action_log,
            reflection_meta=reflection_meta,
            collaboration_meta=collab_meta,
            governance_meta=governance_meta,
        )
