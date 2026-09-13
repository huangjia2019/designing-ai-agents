"""Listing 8.7: preserve specialist reports and request human review."""

from ..patterns.fan_out_gather import ResearchBranch


def review_with_argus(diff_path, fan, review, workspace):
    branches = [
        ResearchBranch(
            branch_id=name,
            question=f"Review {diff_path} for {name}",
            tools=("read_file",),
            result_path=f"reviews/{name}.md",
        )
        for name in ("security", "style", "complexity")
    ]
    receipts = fan.fan_out(branches)
    if len(receipts) != len(branches):
        raise RuntimeError("Partial review is not acceptable")
    reports = {
        receipt.branch_id: workspace.read_file(
            receipt.result_path
        )
        for receipt in receipts
    }
    security_packet = review.run(
        diff_path,
        acceptance=("No unresolved critical claim",),
    )
    return {
        "specialist_reports": reports,
        "security_review": security_packet,
    }
