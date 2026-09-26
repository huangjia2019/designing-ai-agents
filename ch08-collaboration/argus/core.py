# argus/core.py — Argus, Ch8 snapshot: + collaboration.
#
# Cumulative evolution from Ch7:
#   Ch7 added reflection (critic loop, experience replay).
#   Ch8 adds collaboration. For complex reviews, Argus delegates to three
#   parallel sub-agents (security, style, complexity), gathers their
#   findings, and synthesizes a final verdict. The dispatch decision
#   threshold lives here: only complex reviews fan out (cost discipline).

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration


def review_diff(
    diff: str,
    project: str,
    memory: ArgusMemory,
    reasoning: ArgusReasoning | None = None,
    action: ArgusAction | None = None,
    reflection: ArgusReflection | None = None,
    collaboration: ArgusCollaboration | None = None,
    repo_root: str = ".",
    budget: int = 50_000,
    delegate_complex: bool = True,
) -> tuple[ReviewResult, PerceptionTrace, list, dict, dict]:
    """Argus Ch8: + parallel sub-agent dispatch for complex reviews.

    Returns (result, p_trace, action_log, reflection_meta, collab_meta).
    """
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))

    reasoning = reasoning or ArgusReasoning()
    action = action or ArgusAction()
    reflection = reflection or ArgusReflection()
    collaboration = collaboration or ArgusCollaboration()

    # --- COLLABORATION decision: delegate to sub-agents only for complex diffs ---
    collab_meta: dict = {"delegated": False}
    sub_synthesis = ""
    if delegate_complex and diff.count("\n") > 100:
        sub_synthesis = collaboration.parallel_review(diff)
        collab_meta = {
            "delegated": True,
            "agents": collaboration.trace.agent_count,
            "token_multiplier": round(collaboration.trace.token_multiplier, 2),
            "handoff_fidelity": round(collaboration.trace.handoff_fidelity, 2),
            "wall_time_ms": collaboration.trace.wall_time_ms,
        }

    # --- ACTION: tool evidence ---
    action_evidence = []
    lint_trace = action.run_lint(repo_root=repo_root)
    if lint_trace.output:
        action_evidence.append(f"lint: {str(lint_trace.output)[:200]}")

    sections = []
    if past:
        sections.append("### Past lessons\n" + "\n".join(f"- {l}" for l in past))
    if sub_synthesis:
        sections.append("### Sub-agent synthesis\n" + sub_synthesis)
    if action_evidence:
        sections.append("### Verification\n" + "\n".join(action_evidence))
    for c in selected:
        sections.append(f"### {c.path} [{c.relevance}, {c.tokens}t]\n```\n{c.content}\n```")
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

    reflection.record_outcome(task=f"review:{project}",
                              succeeded=reflection_meta["converged"])
    memory.after_review(review_summary=result.verdict[:200], project=project)
    return result, p_trace, action.action_log, reflection_meta, collab_meta
