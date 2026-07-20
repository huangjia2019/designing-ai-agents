"""Demo: Ch6 scope-creep story made tangible.

A naive agent that calls apply_fix on three files when only one was
requested vs. Argus with the Guardrail Sandwich + HITL for fix_apply.
Output shows the guardrail blocking the over-scoped edits and emitting
an audit trail.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus import ArgusAction
from patterns.guardrail_sandwich import SafetyPolicy


def main():
    requested = ["src/auth.py"]
    proposed  = ["src/auth.py", "src/billing.py", "src/cache.py"]

    print("Naive agent (no guardrail):")
    print(f"  Requested: {requested}")
    print(f"  Will edit: {proposed}  ← scope creep")

    print("\nArgus Ch6 with Guardrail Sandwich + HITL:")
    action = ArgusAction(policy=SafetyPolicy(
        allowed_tools={"fix_apply"},
        forbidden_path_prefixes=[],
        require_human_for={"fix_apply"},
        max_output_bytes=1_000_000,
    ), human_approver=lambda action_name, args: (
        "approve" if args.get("file_path") in requested else "decline:not in scope"
    ))

    for f in proposed:
        trace = action.apply_fix(file_path=f, old="x", new="y")
        flag = "BLOCKED" if trace.guardrail_blocked else "OK"
        print(f"  [{flag:7}] fix_apply({f})  reason={trace.guardrail_reason or '(approved)'}")

    print(f"\nAudit: {sum(1 for a in action.action_log if a.guardrail_blocked)} of "
          f"{len(action.action_log)} attempts blocked.")


if __name__ == "__main__":
    main()
