# argus/core.py — Argus, Ch9 snapshot: + governance.
#
# Cumulative evolution from Ch8:
#   Ch8 added collaboration (parallel sub-agents).
#   Ch9 adds the governance layer. Every action that touches the world
#   (tools, file writes, network calls) goes through:
#     1. permission check (capability-based ACL)
#     2. policy evaluation (declarative rules)
#     3. audit log entry (append-only, hash-chained)
#   Trust updates after each action — promotions earn new capabilities,
#   blocked or failed actions cost capability.

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance

from patterns.permission_gate import Capability


def review_diff(
    diff: str,
    project: str,
    memory: ArgusMemory,
    reasoning: ArgusReasoning | None = None,
    action: ArgusAction | None = None,
    reflection: ArgusReflection | None = None,
    collaboration: ArgusCollaboration | None = None,
    governance: ArgusGovernance | None = None,
    repo_root: str = ".",
    budget: int = 50_000,
    delegate_complex: bool = True,
):
    """Argus Ch9: + governance.

    Returns (result, p_trace, action_log, reflection_meta, collab_meta, gov_meta).
    """
    reasoning = reasoning or ArgusReasoning()
    action = action or ArgusAction()
    reflection = reflection or ArgusReflection()
    collaboration = collaboration or ArgusCollaboration()
    governance = governance or ArgusGovernance()

    # --- GOVERNANCE pre-check: is reading the repo allowed? ---
    auth = governance.authorize("perceive", Capability.READ_FILES, {"repo": repo_root})
    if not auth.allowed:
        return None, None, [], {}, {}, {
            "allowed": False, "reason": auth.reason,
            "audit_size": len(governance.audit.entries),
        }
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))

    # --- COLLABORATION (Ch8) ---
    collab_meta = {"delegated": False}
    sub_synthesis = ""
    if delegate_complex and diff.count("\n") > 100:
        sub_synthesis = collaboration.parallel_review(diff)
        collab_meta = {
            "delegated": True,
            "parallel_calls": collaboration.trace.parallel_calls,
            "messages": len(collaboration.trace.messages),
        }

    # --- ACTION (Ch6) — gated by Ch9 governance check ---
    action_evidence = []
    lint_auth = governance.authorize("run_lint", Capability.RUN_LINT, {"repo": repo_root})
    if lint_auth.allowed:
        lint_trace = action.run_lint(repo_root=repo_root)
        governance.report_outcome(
            success=not lint_trace.guardrail_blocked and not lint_trace.error,
            blocked=lint_trace.guardrail_blocked,
        )
        if lint_trace.output:
            action_evidence.append(f"lint: rc={lint_trace.output.get('returncode')}")
    else:
        action_evidence.append(f"lint: blocked by governance ({lint_auth.reason})")

    sections = []
    if past:           sections.append("### Past lessons\n" + "\n".join(f"- {l}" for l in past))
    if sub_synthesis:  sections.append("### Sub-agents\n" + sub_synthesis)
    if action_evidence:sections.append("### Verification\n" + "\n".join(action_evidence))
    for c in selected: sections.append(f"### {c.path}\n```\n{c.content}\n```")
    augmented = f"{diff}\n\n# Context:\n" + "\n\n".join(sections) if sections else diff

    result = reasoning.review(augmented)

    refined = reflection.refine(
        review_text=result.verdict,
        regenerate=lambda task, ctx: reasoning.review(f"{augmented}\n\n# Critic:\n{ctx}").verdict,
    )
    reflection_meta = {
        "iterations": refined["iterations"],
        "converged": refined["converged"],
        "final_score": refined["final_score"],
    }
    result.verdict = refined["output"]
    result.confidence = min(result.confidence, refined["final_score"])

    governance.report_outcome(success=refined["converged"])
    reflection.record_outcome(task=f"review:{project}", succeeded=refined["converged"])
    memory.after_review(review_summary=result.verdict[:200], project=project)

    chain_ok, chain_len = governance.audit.verify_chain()
    gov_meta = {
        "allowed": True,
        "audit_entries": chain_len,
        "audit_chain_ok": chain_ok,
        "current_trust": governance.current_trust().level.value,
        "promotions": governance.trace.promotions,
        "demotions": governance.trace.demotions,
    }
    return result, p_trace, action.action_log, reflection_meta, collab_meta, gov_meta
