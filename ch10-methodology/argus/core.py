# argus/core.py — Argus, Ch9 snapshot: + governance.
#
# Cumulative evolution from Ch8:
#   Ch8 added collaboration (parallel sub-agents).
#   Ch9 adds the governance layer. Every action that touches the world
#   (tools, file writes, network calls) goes through the single
#   ArgusGovernance.run_tool() chokepoint of Listings 9.16-9.17:
#     1. Approval Gate        — allow / deny / ask (§9.2)
#     2. Progressive Commitment — does 'ask' still need a human? (§9.4)
#     3. Blast Radius Control — tool allowlist, paths, rate, budget (§9.3)
#     4. Observability Harness — record the call and the outcome (§9.5)
#   Trust updates on every outcome, so each decision is made on the
#   evidence of the last one.
#
# Approval note: run_command is classified HIGH risk, and at the default
# SUPERVISED trust level a HIGH-risk action needs a human. Pass an
# `ask_human(action, reason) -> bool` approver to let lint actually run,
# or start governance at TrustLevel.AUTONOMOUS. With no approver the
# gate declines, which is the safe default rather than a bug.

from .perception import gather_review_context, PerceptionTrace, FileContext
from .memory import ArgusMemory
from .reasoning import ArgusReasoning, ReviewResult
from .action import ArgusAction
from .reflection import ArgusReflection
from .collaboration import ArgusCollaboration
from .governance import ArgusGovernance


def _governance_meta(governance: ArgusGovernance, **extra) -> dict:
    """Roll the control plane's state into the Ch9 gov_meta dict.

    promotions/demotions are counted off the TrustManager's level_history
    rather than kept as standalone counters — the history is the record.
    """
    history = governance.trust.level_history
    meta = {
        "audit_entries": len(governance.gate.audit_log),
        "current_trust": governance.trust.level.value,
        "promotions": sum(
            1 for _, why in history if why.startswith("escalated")
        ),
        "demotions": sum(
            1 for _, why in history if why.startswith("demoted")
        ),
    }
    meta.update(extra)
    return meta


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
    ask_human=None,
):
    """Argus Ch9: + governance.

    Returns (result, p_trace, action_log, reflection_meta, collab_meta, gov_meta).
    """
    reasoning = reasoning or ArgusReasoning()
    action = action or ArgusAction()
    reflection = reflection or ArgusReflection()
    collaboration = collaboration or ArgusCollaboration()
    governance = governance or ArgusGovernance()
    governance.start_review(project)

    # --- GOVERNANCE pre-check: is reading the repo allowed? ---
    # 'read_file' is matched by the gate's read_* allow rule and sits in
    # the sandbox tool allowlist, so perception clears without a prompt.
    perceive = governance.run_tool(
        "read_file", {"repo": repo_root},
        execute_fn=lambda tool, args: {"repo": args["repo"]},
        ask_human=ask_human,
    )
    if "error" in perceive:
        return None, None, [], {}, {}, _governance_meta(
            governance, allowed=False, reason=perceive["error"],
            audit_size=len(governance.gate.audit_log),
        )
    selected, p_trace = gather_review_context(diff, repo_root, budget)
    past = memory.before_review(project=project, diff_summary=diff[:300].replace("\n", " "))

    # --- COLLABORATION (Ch8) ---
    collab_meta = {"delegated": False}
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

    # --- ACTION (Ch6) — routed through the Ch9 governance chokepoint ---
    # run_tool records the trust outcome itself, so there is no separate
    # report_outcome call: success is simply 'no error came back'.
    action_evidence = []

    def _lint(tool: str, args: dict) -> dict:
        trace = action.run_lint(repo_root=args["repo"])
        if trace.guardrail_blocked:
            return {"error": f"guardrail: {trace.guardrail_reason}"}
        if trace.error:
            return {"error": trace.error}
        return {"trace": trace}

    lint_result = governance.run_tool(
        "run_command", {"cmd": "lint", "repo": repo_root},
        execute_fn=_lint, ask_human=ask_human,
    )
    if "error" in lint_result:
        action_evidence.append(
            f"lint: blocked by governance ({lint_result['error']})"
        )
    elif lint_result["trace"].output:
        action_evidence.append(
            f"lint: {str(lint_result['trace'].output)[:200]}"
        )

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

    governance.trust.record_action(success=refined["converged"])
    reflection.record_outcome(task=f"review:{project}", succeeded=refined["converged"])
    memory.after_review(review_summary=result.verdict[:200], project=project)

    # Close the trace; finish_review returns the Observability dashboard
    # (§9.5), which replaces the old hash-chained audit summary.
    dashboard = governance.finish_review(success=refined["converged"])
    gov_meta = _governance_meta(
        governance, allowed=True, dashboard=dashboard,
    )
    return result, p_trace, action.action_log, reflection_meta, collab_meta, gov_meta
