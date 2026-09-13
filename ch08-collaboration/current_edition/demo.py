"""Inspect collaboration boundaries with a scripted offline runtime."""

import json

from .argus.collaboration import review_with_argus
from .demo_runtime import make_system
from .patterns.adversarial_review import SecurityReviewLoop
from .patterns.fan_out_gather import DynamicFanOut


def run_demo() -> dict:
    workspace, runtime, spawner = make_system()
    workspace.write_file("/src/parser.py", "result = unsafe_eval(text)")
    result = review_with_argus(
        "/src/parser.py",
        DynamicFanOut(spawner, workspace),
        SecurityReviewLoop(spawner, workspace),
        workspace,
    )
    contexts = [call["context"] for call in runtime.calls]
    review = result["security_review"]
    return {
        "mode": "scripted offline example; no model or external tool calls",
        "specialists": sorted(result["specialist_reports"]),
        "separate_contexts": len(contexts) == len(set(contexts)),
        "shared_workspaces": len({call["workspace"] for call in runtime.calls}),
        "open_security_claims": list(review.open_claims),
        "human_decision_required": review.human_decision_required,
        "artifact": workspace.read_file("/src/parser.py"),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
