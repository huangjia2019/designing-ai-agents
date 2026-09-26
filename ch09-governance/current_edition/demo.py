"""Run the current governance boundary with an offline stub executor."""
import json

from . import ArgusGovernance


def main():
    calls = []

    def runtime(tool, arguments):
        # Records intent only: no shell command or external action runs.
        calls.append({"tool": tool, "arguments": dict(arguments)})
        return {"ok": True, "mode": "offline stub"}

    def approve(packet):
        print("Approval packet:", json.dumps(packet, indent=2))
        # A real host authenticates the reviewer before returning this ID.
        return "demo-reviewer"

    gov = ArgusGovernance()
    gov.start_review("example-change")
    denied = gov.run_tool("git_force_push", {}, runtime)
    read = gov.run_tool("read_file", {"path": "."}, runtime)
    reviewed = gov.run_tool(
        "run_command", {"command": "run focused regression checks"}, runtime,
        ask_human=approve,
        review_context={
            "objective": "Check the proposed change",
            "target": "example-change",
            "change": "Run the focused test suite",
            "evidence_ref": "demo:packet-1",
            "policy_version": "demo-policy-1",
        },
    )
    print(json.dumps({
        "denied": denied, "read": read, "reviewed": reviewed,
        "stub_calls": calls,
        "dashboard": gov.finish_review(success=True),
    }, indent=2))


if __name__ == "__main__":
    main()
