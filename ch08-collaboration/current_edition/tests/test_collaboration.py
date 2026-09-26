"""Behavior checks for the revised Chapter 8 mechanisms."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from current_edition.demo_runtime import make_system
from current_edition.argus.collaboration import review_with_argus
from current_edition.patterns.adversarial_review import SecurityReviewLoop
from current_edition.patterns.collaboration_runtime import (
    AgentResult,
    AgentSpec,
    SharedWorkspace,
    SubagentSpawner,
)
from current_edition.patterns.collaboration_trace import (
    CollaborationTrace,
    RunSample,
    SingleAgentBaseline,
)
from current_edition.patterns.fan_out_gather import (
    BranchReceipt,
    DynamicFanOut,
    ResearchBranch,
)
from current_edition.patterns.handoff_chain import (
    HandoffChain,
    HandoffPacket,
)
from current_edition.patterns.hierarchical_delegation import (
    DelegationRequest,
    ManagerWorker,
)


class CollaborationBundleTest(unittest.TestCase):
    def test_trace_uses_average_single_agent_baseline(self):
        baseline = SingleAgentBaseline.from_runs(
            [
                RunSample(900, 12_000, 0.70),
                RunSample(1_100, 10_000, 0.80),
                RunSample(1_000, 11_000, 0.75),
            ]
        )
        trace = CollaborationTrace(
            "research-1",
            "fan-out/gather",
            agents=4,
            total_tokens=3_000,
            wall_time_ms=5_500,
            quality=0.90,
            baseline=baseline,
        )
        self.assertEqual(baseline.average_tokens, 1_000)
        self.assertEqual(baseline.average_latency_ms, 11_000)
        self.assertEqual(trace.token_multiplier, 3.0)
        self.assertEqual(trace.latency_speedup, 2.0)
        self.assertAlmostEqual(trace.quality_delta, 0.15)

    def test_handoff_rejects_missing_evidence_to_owner(self):
        workspace, _, spawner = make_system()
        workspace.write_file("/change.md", "candidate patch")
        chain = HandoffChain(spawner, workspace)
        packet = HandoffPacket(
            "H1",
            "investigator",
            "implementer",
            "Implement the verified fix",
            "/change.md",
            1,
            ("Do not change the public API",),
            (),
            ("Regression test passes",),
            ("Which call path triggers the bug?",),
            "investigator",
        )
        receiver = AgentSpec(
            "implementer",
            "Edit only the accepted artifact",
            ("read_file", "write_file", "return_handoff"),
        )
        receipt = chain.transfer(packet, receiver)
        self.assertFalse(receipt.accepted)
        self.assertEqual(workspace.returns[0].return_to, "investigator")
        self.assertIn("evidence", workspace.returns[0].reason)

    def test_subagents_have_separate_contexts_one_workspace(self):
        workspace, runtime, spawner = make_system()
        fan = DynamicFanOut(spawner, workspace)
        result = fan.research("Identify every board member")
        self.assertIn("Synthesis", result.text)
        contexts = [call["context"] for call in runtime.calls]
        self.assertEqual(len(contexts), len(set(contexts)))
        workspaces = {call["workspace"] for call in runtime.calls}
        self.assertEqual(workspaces, {id(workspace)})
        lead_call = next(
            call for call in runtime.calls
            if call["agent"] == "lead-researcher"
        )
        self.assertIn("fan_out", lead_call["tools"])
        self.assertIn("/research/c.md", workspace.files)

    def test_fan_out_refuses_dependency_graph(self):
        workspace, _, spawner = make_system()
        fan = DynamicFanOut(spawner, workspace)
        branch = ResearchBranch(
            "b",
            "Run integration after contract",
            ("search",),
            "/research/b.md",
            depends_on=("a",),
        )
        with self.assertRaisesRegex(ValueError, "independent"):
            fan.fan_out([branch])

    def test_writer_and_reviewer_share_artifact_not_context(self):
        workspace, runtime, spawner = make_system()
        workspace.write_file("/src/parser.py", "result = unsafe_eval(text)")
        loop = SecurityReviewLoop(spawner, workspace)
        packet = loop.run(
            "/src/parser.py",
            ("Untrusted text cannot execute code",),
        )
        self.assertTrue(packet.human_decision_required)
        self.assertEqual(packet.open_claims, ())
        self.assertIn("safe_parse", workspace.read_file("/src/parser.py"))
        participants = [
            call for call in runtime.calls
            if call["agent"] in {"writer", "security-reviewer"}
        ]
        contexts = {call["context"] for call in participants}
        self.assertEqual(len(contexts), len(participants))
        self.assertNotIn("write_file", participants[0]["tools"])

    def test_manager_owns_dependencies_and_delegate_tool(self):
        workspace, runtime, spawner = make_system()
        hierarchy = ManagerWorker(spawner, workspace)
        result = hierarchy.execute("Ship the API change")
        self.assertIn("completed", result.text)
        self.assertEqual(workspace.tasks["T1"].status, "completed")
        self.assertEqual(workspace.tasks["T2"].status, "completed")
        manager_call = next(
            call for call in runtime.calls
            if call["agent"] == "manager"
        )
        self.assertIn("delegate", manager_call["tools"])


    def test_argus_checkpoint_preserves_reports_and_human_review(self):
        workspace, _, spawner = make_system()
        workspace.write_file("/src/parser.py", "unsafe_eval(text)")
        result = review_with_argus(
            "/src/parser.py",
            DynamicFanOut(spawner, workspace),
            SecurityReviewLoop(spawner, workspace),
            workspace,
        )
        self.assertEqual(
            set(result["specialist_reports"]),
            {"security", "style", "complexity"},
        )
        self.assertTrue(result["security_review"].human_decision_required)

    def test_argus_checkpoint_rejects_partial_worker_set(self):
        workspace, _, _ = make_system()
        with self.assertRaisesRegex(RuntimeError, "Partial review"):
            review_with_argus(
                "/src/parser.py",
                SimpleNamespace(fan_out=lambda branches: []),
                object(),
                workspace,
            )

    def test_receiver_identity_is_checked_before_handoff(self):
        workspace, runtime, spawner = make_system()
        workspace.write_file("/change.md", "verified patch")
        packet = HandoffPacket(
            "H1", "investigator", "implementer", "Apply the verified fix",
            "/change.md", 1, ("Keep the public API",), ("test-log-1",),
            ("Regression passes",), (), "investigator",
        )
        receiver = AgentSpec("unrelated-worker", "Read only", ("read_file",))
        result = HandoffChain(spawner, workspace).transfer(packet, receiver)
        self.assertFalse(result.accepted)
        self.assertIn("matching receiver", result.reason)
        self.assertEqual(runtime.calls, [])


if __name__ == "__main__":
    unittest.main()
