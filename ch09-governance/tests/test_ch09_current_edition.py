"""Offline regression tests against the current-edition Python modules."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import time
import unittest

package_root = Path(__file__).resolve().parents[1] / "current_edition"
spec = importlib.util.spec_from_file_location(
    "ch09_current_edition", package_root / "__init__.py",
    submodule_search_locations=[str(package_root)],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)

from ch09_current_edition import (
    AgentObserver, ApprovalGate, ArgusGovernance, Decision,
    EscalationThresholds, RiskLevel, SandboxConfig, SandboxedExecutor,
    ToolAction, TrustLevel, TrustManager,
)


def review_context():
    return {
        "objective": "Verify a proposed change",
        "target": "repository/example",
        "change": "Run focused checks",
        "evidence_ref": "evidence:review-1",
        "policy_version": "policy-1",
    }


class RecordingRuntime:
    """An executor stub: records inputs without performing their actions."""

    def __init__(self):
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, deepcopy(arguments)))
        return {"ok": True}


class ApprovalGateTests(unittest.TestCase):
    def test_critical_risk_cannot_be_waived_by_wildcard_allow(self):
        gate = ApprovalGate()
        gate.add_allow_rule("*", "broad allow")
        for name in ("send_email", "post_api", "deploy", "delete_database"):
            for reversible in (True, False):
                with self.subTest(name=name, reversible=reversible):
                    action = ToolAction(name, {}, reversible=reversible)
                    self.assertIs(gate.evaluate(action)[0], Decision.ASK)
                    self.assertIs(action.risk_level, RiskLevel.CRITICAL)

    def test_deny_precedes_allow_and_critical_routing(self):
        gate = ApprovalGate()
        gate.add_allow_rule("*", "allow")
        gate.add_deny_rule("send_*", "mail prohibited")
        self.assertEqual(
            gate.evaluate(ToolAction("send_email", {})),
            (Decision.DENY, "mail prohibited"),
        )

    def test_classification_and_caller_risk_spoof(self):
        gate = ApprovalGate()
        for name in ("search", "read_file", "list_files", "grep"):
            with self.subTest(name=name):
                action = ToolAction(name, {})
                self.assertIs(gate.evaluate(action)[0], Decision.ALLOW)
                self.assertIs(action.risk_level, RiskLevel.LOW)
        for name, expected in (
            ("edit_file", RiskLevel.MEDIUM),
            ("run_command", RiskLevel.HIGH),
            ("unknown", RiskLevel.MEDIUM),
        ):
            with self.subTest(name=name):
                action = ToolAction(name, {})
                self.assertIs(gate.evaluate(action)[0], Decision.ASK)
                self.assertIs(action.risk_level, expected)
        self.assertIs(
            gate.classify_risk(ToolAction("read_file", {}, reversible=False)),
            RiskLevel.HIGH,
        )
        spoof = ToolAction("send_email", {})
        spoof.risk_level = RiskLevel.LOW
        self.assertIs(gate.evaluate(spoof)[0], Decision.ASK)

    def test_audit_keeps_an_argument_snapshot(self):
        args = {"nested": {"value": 1}}
        gate = ApprovalGate()
        gate.evaluate(ToolAction("read_file", args))
        args["nested"]["value"] = 2
        self.assertEqual(gate.audit_log[0]["args"], {"nested": {"value": 1}})


class TrustTests(unittest.TestCase):
    def test_permanent_human_boundaries_at_every_level(self):
        for level in TrustLevel:
            with self.subTest(level=level):
                trust = TrustManager(initial_level=level)
                self.assertTrue(trust.should_ask_human("critical"))
                self.assertTrue(trust.should_ask_human("low", True))

    def test_routine_ask_varies_with_trust(self):
        for level in (TrustLevel.OBSERVE, TrustLevel.ASSIST):
            self.assertTrue(
                TrustManager(initial_level=level).should_ask_human("medium")
            )
        supervised = TrustManager(initial_level=TrustLevel.SUPERVISED)
        self.assertFalse(supervised.should_ask_human("medium"))
        self.assertTrue(supervised.should_ask_human("high"))
        for level in (TrustLevel.AUTONOMOUS, TrustLevel.DELEGATED):
            self.assertFalse(
                TrustManager(initial_level=level).should_ask_human("high")
            )

    def test_promotion_consumes_evidence(self):
        thresholds = EscalationThresholds(
            min_actions=3, min_success_rate=1,
            max_override_rate=0, max_error_rate=0,
        )
        trust = TrustManager(
            thresholds=thresholds, initial_level=TrustLevel.SUPERVISED
        )
        for _ in range(3):
            trust.record_action(True)
        self.assertIs(trust.level, TrustLevel.AUTONOMOUS)
        self.assertEqual(trust.metrics.total_actions, 0)

    def test_promotion_checks_error_and_override_rates(self):
        for use_override in (False, True):
            with self.subTest(use_override=use_override):
                trust = TrustManager(thresholds=EscalationThresholds(
                    min_actions=10, min_success_rate=0.9,
                    max_override_rate=0.05, max_error_rate=0.02,
                ))
                for _ in range(9):
                    trust.record_action(True)
                trust.record_action(
                    success=use_override, user_override=use_override
                )
                self.assertIs(trust.level, TrustLevel.OBSERVE)

    def test_demotion_and_floor_clear_stale_evidence(self):
        for level, expected in (
            (TrustLevel.AUTONOMOUS, TrustLevel.SUPERVISED),
            (TrustLevel.OBSERVE, TrustLevel.OBSERVE),
        ):
            with self.subTest(level=level):
                trust = TrustManager(initial_level=level)
                trust.record_action(True)
                for _ in range(3):
                    trust.record_action(False)
                self.assertIs(trust.level, expected)
                self.assertEqual(trust.metrics.total_actions, 0)


class PolicyEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.allowed = self.root / "allowed"
        self.allowed.mkdir()
        self.blocked = self.allowed / "blocked"
        self.blocked.mkdir()
        self.config = SandboxConfig(
            allowed_paths=[str(self.allowed)],
            blocked_paths=[str(self.blocked)],
            allowed_tools=["read_file", "edit_file", "run_command"],
            max_cost_per_task_usd=1,
        )
        self.sandbox = SandboxedExecutor(self.config)
        self.runtime = RecordingRuntime()

    def tearDown(self):
        self.temp.cleanup()

    def test_resolved_paths_and_blocked_precedence(self):
        self.assertTrue(self.sandbox.validate_path(str(self.allowed)))
        self.assertTrue(self.sandbox.validate_path(str(self.allowed / "safe")))
        for p in (self.blocked / "secret", self.root / "outside",
                  Path(str(self.allowed) + "-other") / "file",
                  self.allowed / ".." / "outside"):
            with self.subTest(path=p):
                self.assertFalse(self.sandbox.validate_path(str(p)))

    def test_symlink_to_outside_is_not_a_permitted_path(self):
        outside = self.root / "outside"
        outside.mkdir()
        link = self.allowed / "link"
        link.symlink_to(outside, target_is_directory=True)
        self.assertFalse(self.sandbox.validate_path(str(link / "file")))

    def test_all_host_path_keys_are_checked(self):
        for key in ("path", "file_path", "cwd", "repo", "repo_root"):
            with self.subTest(key=key):
                result = self.sandbox.execute(
                    "read_file", {key: str(self.blocked)},
                    execute_fn=self.runtime,
                )
                self.assertIn("error", result)
        self.assertEqual(self.runtime.calls, [])

    def test_tool_allowlist_prevents_execution(self):
        result = self.sandbox.execute(
            "unregistered_tool", {}, execute_fn=self.runtime
        )
        self.assertIn("error", result)
        self.assertEqual(self.runtime.calls, [])

    def test_nonfinite_and_negative_costs_cannot_execute(self):
        for value in (-1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                result = self.sandbox.execute(
                    "read_file", {}, value, self.runtime
                )
                self.assertIn("error", result)
                self.assertEqual(self.sandbox.cumulative_cost, 0)
        self.assertEqual(self.runtime.calls, [])

    def test_budget_counts_only_admitted_estimates(self):
        self.assertTrue(self.sandbox.check_budget(1))
        self.assertFalse(self.sandbox.check_budget(1.01))
        self.sandbox.execute("read_file", {}, 0.6, self.runtime)
        result = self.sandbox.execute("read_file", {}, 0.5, self.runtime)
        self.assertIn("error", result)
        self.assertEqual(len(self.runtime.calls), 1)
        self.assertAlmostEqual(self.sandbox.cumulative_cost, 0.6)

    def test_rate_limit_is_a_rolling_window(self):
        self.sandbox.action_timestamps = (
            [time.time()] * self.config.max_actions_per_minute
        )
        result = self.sandbox.execute(
            "read_file", {}, execute_fn=self.runtime
        )
        self.assertEqual(result, {"error": "Rate limit exceeded"})
        self.assertEqual(self.runtime.calls, [])
        self.sandbox.action_timestamps = [time.time() - 61] * 20
        self.assertTrue(self.sandbox.check_rate_limit())
        self.assertEqual(self.sandbox.action_timestamps, [])


class ObserverTests(unittest.TestCase):
    def test_message_and_output_references_are_exported(self):
        observer = AgentObserver("test")
        observer.start_trace("first")
        observer.record_llm_call(
            "model", 5, 7, 0.01, 2,
            messages_ref="evidence:request", output_ref="evidence:response",
        )
        observer.record_task_outcome(True, False)
        observer.finish_trace(success=True)
        exported = json.loads(observer.export_traces())
        model_span = next(s for s in exported[0] if s["type"] == "llm_call")
        self.assertEqual(model_span["metadata"]["messages_ref"], "evidence:request")
        self.assertEqual(model_span["metadata"]["output_ref"], "evidence:response")
        self.assertEqual(observer.get_dashboard()["avg_tokens_per_task"], 12)
        self.assertIsNone(observer.current_root)
        self.assertEqual(observer.current_task_tokens, 0)

    def test_decision_context_is_copied(self):
        observer = AgentObserver("test")
        observer.start_trace("first")
        context = {"version": {"policy": "v1"}}
        observer.record_decision(
            "edit_file", "ask", "policy", "evidence:packet", context
        )
        context["version"]["policy"] = "v2"
        decision = observer.current_trace[-1]
        self.assertEqual(decision.metadata["context"]["version"]["policy"], "v1")
        self.assertEqual(decision.metadata["evidence_ref"], "evidence:packet")

    def test_empty_dashboard_and_per_task_tokens(self):
        observer = AgentObserver("test")
        self.assertEqual(observer.get_dashboard()["avg_tokens_per_task"], 0)
        observer.start_trace("first")
        observer.record_llm_call("model", 4, 6, 0.01, 1)
        observer.record_task_outcome(True, False)
        observer.finish_trace()
        observer.start_trace("second")
        observer.record_llm_call("model", 1, 1, 0.01, 1)
        observer.record_task_outcome(False, True)
        observer.finish_trace()
        dashboard = observer.get_dashboard()
        self.assertEqual(dashboard["avg_tokens_per_task"], 6)
        self.assertEqual(dashboard["task_success_rate"], "50.0%")


class GovernanceCompositionTests(unittest.TestCase):
    def setUp(self):
        self.gov = ArgusGovernance()
        self.gov.start_review("PR-42")
        self.runtime = RecordingRuntime()

    def test_deny_is_recorded_and_never_reaches_runtime(self):
        self.gov.trust.level = TrustLevel.DELEGATED
        result = self.gov.run_tool("git_force_push", {}, self.runtime)
        self.assertIn("error", result)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(self.gov.observer.current_trace[-1].metadata["decision"],
                         "deny")

    def test_missing_review_context_blocks_before_prompt_or_execution(self):
        for absent in review_context():
            with self.subTest(absent=absent):
                context = review_context()
                del context[absent]
                prompts = []
                result = self.gov.run_tool(
                    "run_command", {}, self.runtime,
                    ask_human=lambda packet: prompts.append(packet),
                    review_context=context,
                )
                self.assertEqual(result, {"error": "Review context incomplete"})
                self.assertEqual(prompts, [])
        self.assertEqual(self.runtime.calls, [])

    def test_boolean_or_empty_approval_is_not_a_reviewer_identity(self):
        for identity in (None, False, True, "", " ", 42):
            with self.subTest(identity=identity):
                # Each refusal has independent trust metrics.
                gov = ArgusGovernance()
                gov.start_review("identity-check")
                result = gov.run_tool(
                    "run_command", {}, self.runtime,
                    ask_human=lambda packet: identity,
                    review_context=review_context(),
                )
                self.assertEqual(result, {"error": "Declined"})
        self.assertEqual(self.runtime.calls, [])

    def test_human_sees_copied_proposal_and_cannot_mutate_execution(self):
        arguments = {"command": "test", "options": {"target": "original"}}
        context = review_context()
        captured = []

        def approve(packet):
            captured.append(deepcopy(packet))
            packet["arguments"]["options"]["target"] = "changed"
            packet["context"]["policy_version"] = "changed"
            arguments["options"]["target"] = "caller-mutated"
            context["policy_version"] = "caller-mutated"
            return "reviewer-7"

        result = self.gov.run_tool(
            "run_command", arguments, self.runtime,
            ask_human=approve, review_context=context,
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured[0]["context"]["policy_version"], "policy-1")
        self.assertEqual(captured[0]["risk"], "high")
        self.assertEqual(self.runtime.calls[0][1]["options"]["target"], "original")
        decisions = [s.metadata for s in self.gov.observer.current_trace
                     if s.span_type == "decision"]
        self.assertIn("human_approved", [s["decision"] for s in decisions])

    def test_waived_ask_is_explicit_and_does_not_prompt(self):
        prompts = []
        result = self.gov.run_tool(
            "edit_file", {}, self.runtime,
            ask_human=lambda packet: prompts.append(packet),
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(prompts, [])
        decisions = [s.metadata["decision"]
                     for s in self.gov.observer.current_trace
                     if s.span_type == "decision"]
        self.assertEqual(decisions, ["ask", "approval_waived"])

    def test_critical_actions_still_require_review_at_delegated_level(self):
        config = SandboxConfig(allowed_paths=["."], allowed_tools=["send_email"])
        gov = ArgusGovernance(config, TrustLevel.DELEGATED)
        gov.gate.add_allow_rule("*", "broad allow")
        gov.start_review("critical")
        result = gov.run_tool("send_email", {}, self.runtime)
        self.assertEqual(result, {"error": "Review context incomplete"})
        self.assertEqual(self.runtime.calls, [])
        result = gov.run_tool(
            "send_email", {}, self.runtime,
            ask_human=lambda packet: "authorized-reviewer",
            review_context=review_context(),
        )
        self.assertEqual(result, {"ok": True})

    def test_general_telemetry_uses_evidence_reference_not_argument_payload(self):
        secret = "sensitive-example-value"
        result = self.gov.run_tool(
            "run_command", {"secret": secret}, self.runtime,
            ask_human=lambda packet: "reviewer-7",
            review_context=review_context(),
        )
        self.assertEqual(result, {"ok": True})
        exported = self.gov.observer.export_traces()
        self.assertNotIn(secret, exported)
        self.assertIn("evidence:review-1", exported)
        self.assertIn("policy-1", exported)
        # The gate's local audit is a protected record, not general telemetry.
        self.assertEqual(self.gov.gate.audit_log[0]["args"]["secret"], secret)

    def test_new_task_resets_money_but_retains_rate_history(self):
        self.gov.run_tool("read_file", {}, self.runtime, cost=0.6)
        timestamps = self.gov.sandbox.action_timestamps[:]
        self.gov.finish_review(True)
        self.gov.start_review("PR-43")
        self.assertEqual(self.gov.sandbox.cumulative_cost, 0)
        self.assertEqual(self.gov.sandbox.action_timestamps, timestamps)
        self.assertEqual(self.gov.trust_scope, "argus:repo_review:PR-43")


if __name__ == "__main__":
    unittest.main()
