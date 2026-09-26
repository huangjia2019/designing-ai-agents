"""Behavior checks for the executable examples in revised Chapter 6."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


from current_edition import action

NS = vars(action)


class ToolDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 27, 9, tzinfo=timezone.utc)
        self.commits = NS["CommitStore"]()
        self.registry = NS["ToolRegistry"]()

        def validate(arguments: dict[str, object]) -> None:
            amount = arguments.get("amount_cents")
            if type(amount) is not int or amount <= 0:
                raise ValueError("amount must be positive cents")

        spec = NS["ToolSpec"](
            name="transfer_salary",
            description="Transfer one approved salary",
            effect="payroll.transfer",
            roles=frozenset({"payroll_operator"}),
            stages=frozenset({"payment"}),
            validate_arguments=validate,
            target_arg="employee_id",
            protected_args=frozenset(
                {"employee_id", "amount_cents"}
            ),
            state_arg="employee_id",
            max_state_age_seconds=60,
            mutates_state=True,
        )
        self.registry.register(spec)
        self.context = self.context_for("E0007")

    def context_for(
        self,
        employee_id: str,
        *,
        approved_amount_cents: int = 125_00,
        read_at: datetime | None = None,
        commit_id: str | None = "pay:2026-08:E0007",
    ) -> object:
        employee = NS["TrustedValue"](
            value=employee_id,
            source_ref=f"payroll://{employee_id}",
            state_version="payroll:v17",
            read_at=read_at or self.now,
        )
        amount = NS["TrustedValue"](
            value=approved_amount_cents,
            source_ref=f"payroll://{employee_id}/approved-amount",
            state_version="payroll:v17",
            read_at=read_at or self.now,
        )
        return NS["DispatchContext"](
            role="payroll_operator",
            stage="payment",
            granted_effects=frozenset({"payroll.transfer"}),
            trusted_values={
                "employee_id": employee,
                "amount_cents": amount,
            },
            now=self.now,
            commit_id=commit_id,
        )

    def intent(
        self,
        *,
        employee_id: str = "E0007",
        amount_cents: object = 125_00,
    ) -> object:
        return NS["ToolIntent"](
            tool_name="transfer_salary",
            arguments={
                "employee_id": employee_id,
                "amount_cents": amount_cents,
            },
        )

    def guarded_argus(
        self,
        receipt_status: str = "settled",
        *,
        include_receipt: bool = True,
    ) -> tuple:
        state = NS["PayrollEvidence"](
            approved_amounts={"E0007": 125_00},
            current_version="payroll:v17",
            commits=self.commits,
            payment_attempts=[],
            provider_receipts={},
            payroll_status={},
        )
        calls: list[dict[str, object]] = []

        def runner(
            contract: object,
            arguments: dict[str, object],
        ) -> dict[str, str]:
            calls.append(dict(arguments))
            commit_id = contract.commit_id
            attempt = {
                "commit_id": commit_id,
                "employee_id": arguments["employee_id"],
                "amount_cents": arguments["amount_cents"],
                "state_version": "payroll:v17",
            }
            state.payment_attempts.append(attempt)
            if include_receipt:
                state.provider_receipts[commit_id] = NS["PaymentReceipt"](
                    receipt_id="receipt-1",
                    commit_id=commit_id,
                    employee_id=str(arguments["employee_id"]),
                    amount_cents=int(arguments["amount_cents"]),
                    state_version="payroll:v17",
                    status=receipt_status,
                )
            state.payroll_status[str(arguments["employee_id"])] = "PAID"
            return {"provider_receipt": "receipt-1"}

        guarded = NS["GuardedTool"](
            name="transfer_salary",
            pre_checks=(NS["make_payroll_pre"](state),),
            runner=runner,
            post_checks=(NS["make_payroll_post"](state),),
        )
        argus = NS["ArgusAction"](
            self.registry,
            {"transfer_salary": guarded},
            self.commits,
        )
        return argus, calls

    def test_valid_call_runs_once_and_repeat_requires_verification(self) -> None:
        argus, calls = self.guarded_argus()
        first = argus.execute(self.intent(), self.context)
        second = argus.execute(self.intent(), self.context)
        self.assertEqual(first.status, "accepted")
        self.assertEqual(second.status, "unknown")
        self.assertEqual(len(calls), 1)

    def test_commit_id_cannot_change_arguments(self) -> None:
        argus, calls = self.guarded_argus()
        argus.execute(self.intent(), self.context)
        changed = self.intent(amount_cents=130_00)
        attempt = argus.execute(changed, self.context)
        self.assertEqual(attempt.status, "rejected")
        self.assertEqual(len(calls), 1)

    def test_invalid_and_cross_entity_arguments_are_rejected(self) -> None:
        argus, calls = self.guarded_argus()
        invalid = argus.execute(
            self.intent(amount_cents="not-a-number"),
            self.context,
        )
        crossed = argus.execute(
            self.intent(employee_id="E0012"),
            self.context,
        )
        self.assertEqual(invalid.status, "rejected")
        self.assertEqual(crossed.status, "rejected")
        self.assertEqual(calls, [])

    def test_boolean_is_not_accepted_as_one_cent(self) -> None:
        argus, calls = self.guarded_argus()
        attempt = argus.execute(
            self.intent(amount_cents=True),
            self.context,
        )
        self.assertEqual(attempt.status, "rejected")
        self.assertEqual(calls, [])

    def test_unapproved_positive_amount_never_reaches_runner(self) -> None:
        argus, calls = self.guarded_argus()
        attempt = argus.execute(
            self.intent(amount_cents=99_999_999),
            self.context,
        )
        self.assertEqual(attempt.status, "rejected")
        self.assertEqual(calls, [])

    def test_mutation_requires_runtime_commit_identity(self) -> None:
        argus, calls = self.guarded_argus()
        context = self.context_for("E0007", commit_id=None)
        attempt = argus.execute(self.intent(), context)
        self.assertEqual(attempt.status, "rejected")
        self.assertEqual(calls, [])

    def test_stale_and_naive_state_return_rejections(self) -> None:
        argus, calls = self.guarded_argus()
        stale = self.context_for(
            "E0007",
            read_at=self.now - timedelta(seconds=61),
        )
        naive = self.context_for(
            "E0007",
            read_at=datetime(2026, 8, 27, 9),
        )
        self.assertEqual(argus.execute(self.intent(), stale).status, "rejected")
        self.assertEqual(argus.execute(self.intent(), naive).status, "rejected")
        self.assertEqual(calls, [])

    def test_admission_snapshots_arguments(self) -> None:
        arguments = {"employee_id": "E0007", "amount_cents": 125_00}
        intent = NS["ToolIntent"](
            "transfer_salary",
            arguments,
        )
        call = NS["admit"](self.registry, intent, self.context)
        arguments["amount_cents"] = 999_00
        self.assertEqual(call.arguments()["amount_cents"], 125_00)

    def test_commit_fingerprint_binds_tool_and_effect(self) -> None:
        def validate(arguments: dict[str, object]) -> None:
            if type(arguments.get("amount_cents")) is not int:
                raise ValueError("amount must be cents")

        alternate = NS["ToolSpec"](
            name="reverse_salary",
            description="Reverse one salary",
            effect="payroll.reverse",
            roles=frozenset({"payroll_operator"}),
            stages=frozenset({"payment"}),
            validate_arguments=validate,
            target_arg="employee_id",
            protected_args=frozenset(
                {"employee_id", "amount_cents"}
            ),
            state_arg="employee_id",
            max_state_age_seconds=60,
            mutates_state=True,
        )
        self.registry.register(alternate)
        context = NS["DispatchContext"](
            role=self.context.role,
            stage=self.context.stage,
            granted_effects=frozenset(
                {"payroll.transfer", "payroll.reverse"}
            ),
            trusted_values=self.context.trusted_values,
            now=self.context.now,
            commit_id=self.context.commit_id,
        )
        first = NS["admit"](self.registry, self.intent(), context)
        second_intent = NS["ToolIntent"](
            "reverse_salary",
            dict(self.intent().arguments),
        )
        second = NS["admit"](self.registry, second_intent, context)
        self.assertNotEqual(
            first.contract.request_digest,
            second.contract.request_digest,
        )
        self.commits.reserve(
            first.contract.commit_id,
            first.contract.request_digest,
        )
        with self.assertRaises(NS["AdmissionError"]):
            self.commits.reserve(
                second.contract.commit_id,
                second.contract.request_digest,
            )

    def test_rejected_provider_receipt_is_not_accepted(self) -> None:
        argus, _ = self.guarded_argus(receipt_status="rejected")
        attempt = argus.execute(self.intent(), self.context)
        self.assertEqual(attempt.status, "failed")
        self.assertTrue(attempt.evidence["compensation_required"])

    def test_missing_provider_receipt_stays_unknown(self) -> None:
        argus, _ = self.guarded_argus(include_receipt=False)
        attempt = argus.execute(self.intent(), self.context)
        self.assertEqual(attempt.status, "unknown")
        self.assertTrue(attempt.evidence["recovery_required"])


class GuardExceptionTests(unittest.TestCase):
    def test_gate_result_requires_real_booleans(self) -> None:
        with self.assertRaises(TypeError):
            NS["GateResult"]("false")
        with self.assertRaises(TypeError):
            NS["GateResult"](True, conclusive="false")

    def test_post_check_crash_after_runner_is_unknown(self) -> None:
        effects: list[str] = []

        def accepted(*_args: object) -> object:
            return NS["GateResult"](True)

        def runner(
            _contract: object,
            _arguments: object,
        ) -> dict[str, bool]:
            effects.append("effect")
            return {"ok": True}

        def crashing_post(*_args: object) -> object:
            raise RuntimeError("verifier unavailable")

        tool = NS["GuardedTool"](
            "effect",
            (accepted,),
            runner,
            (crashing_post,),
        )
        contract = NS["ActionContract"](
            "effect",
            "target",
            "v1",
            "commit-1",
            "digest-1",
            ("postcondition",),
        )
        attempt = NS["run_guarded"](tool, contract, {"target": "target"})
        self.assertEqual(effects, ["effect"])
        self.assertEqual(attempt.status, "unknown")
        self.assertTrue(attempt.evidence["recovery_required"])

    def test_malformed_post_result_is_unknown(self) -> None:
        effects: list[str] = []

        def accepted(*_args: object) -> object:
            return NS["GateResult"](True)

        def runner(
            _contract: object,
            _arguments: object,
        ) -> dict[str, bool]:
            effects.append("effect")
            return {"ok": True}

        def malformed(*_args: object) -> None:
            return None

        tool = NS["GuardedTool"](
            "effect",
            (accepted,),
            runner,
            (malformed,),
        )
        contract = NS["ActionContract"](
            "effect",
            "target",
            "v1",
            "commit-2",
            "digest-2",
            ("postcondition",),
        )
        attempt = NS["run_guarded"](tool, contract, {"target": "target"})
        self.assertEqual(effects, ["effect"])
        self.assertEqual(attempt.status, "unknown")
        self.assertTrue(attempt.evidence["recovery_required"])


class PlanTests(unittest.TestCase):
    def plan(self) -> object:
        steps = {
            "snapshot": NS["PlanStep"](
                "snapshot",
                "snapshot",
                "customer-index",
            ),
            "backfill": NS["PlanStep"](
                "backfill",
                "backfill",
                "customer-index",
                ("snapshot",),
            ),
        }
        return NS["ExecutionPlan"](
            goal="migrate customer index",
            scope=frozenset({"customer-index"}),
            allowed_actions=frozenset({"snapshot", "backfill"}),
            invariants=("no mixed-version reads",),
            version=1,
            steps=steps,
        )

    def test_evidence_must_be_accepted_and_referenced(self) -> None:
        with self.assertRaises(TypeError):
            NS["EvidenceRecord"]("receipt", "r-1", "false")

        plan = self.plan()
        step = plan.steps["snapshot"]
        step.required_evidence = ("receipt",)
        step.status = NS["StepStatus"].VERIFYING
        for record in (
            NS["EvidenceRecord"]("receipt", "", True),
            NS["EvidenceRecord"]("receipt", "r-1", False),
        ):
            def verify_rejected(
                _step: object,
                _candidate: object,
                record: object = record,
            ) -> dict[str, object]:
                return {"receipt": record}

            with self.assertRaises(ValueError):
                NS["accept_step"](
                    plan,
                    "snapshot",
                    {},
                    verify_rejected,
                )
        accepted = NS["EvidenceRecord"]("receipt", "r-1", True)

        def verify_accepted(
            _step: object,
            _candidate: object,
        ) -> dict[str, object]:
            return {"receipt": accepted}

        NS["accept_step"](
            plan,
            "snapshot",
            {},
            verify_accepted,
        )
        self.assertEqual(step.status, NS["StepStatus"].DONE)

    def test_evidence_kind_must_match_required_key(self) -> None:
        plan = self.plan()
        step = plan.steps["snapshot"]
        step.required_evidence = ("receipt",)
        step.status = NS["StepStatus"].VERIFYING

        def wrong_kind(
            _step: object,
            _candidate: object,
        ) -> dict[str, object]:
            record = NS["EvidenceRecord"]("model_claim", "r-1", True)
            return {"receipt": record}

        with self.assertRaises(ValueError):
            NS["accept_step"](plan, "snapshot", {}, wrong_kind)

    def test_step_cannot_finish_before_dependencies(self) -> None:
        plan = self.plan()
        step = plan.steps["backfill"]
        step.required_evidence = ("receipt",)
        step.status = NS["StepStatus"].VERIFYING

        def accepted(
            _step: object,
            _candidate: object,
        ) -> dict[str, object]:
            record = NS["EvidenceRecord"]("receipt", "r-1", True)
            return {"receipt": record}

        with self.assertRaises(ValueError):
            NS["accept_step"](plan, "backfill", {}, accepted)
        step.status = NS["StepStatus"].DONE
        step.evidence["receipt"] = NS["EvidenceRecord"](
            "receipt",
            "r-1",
            True,
        )
        with self.assertRaises(ValueError):
            NS["validate_plan"](plan)

    def test_plan_rejects_cycles_scope_and_unauthorized_actions(self) -> None:
        cycle = self.plan()
        cycle.steps["snapshot"].dependencies = ("backfill",)
        with self.assertRaises(ValueError):
            NS["validate_plan"](cycle)

        outside = self.plan()
        outside.steps["snapshot"].target_ref = "other-index"
        with self.assertRaises(ValueError):
            NS["validate_plan"](outside)

        unauthorized = self.plan()
        unauthorized.steps["snapshot"].action = "delete_all"
        with self.assertRaises(ValueError):
            NS["validate_plan"](unauthorized)

    def test_failed_replan_does_not_mutate_plan(self) -> None:
        plan = self.plan()
        replacement = NS["PlanStep"](
            "backfill",
            "backfill",
            "customer-index",
            ("backfill",),
        )
        with self.assertRaises(ValueError):
            NS["apply_replan"](
                plan,
                frozenset({"backfill"}),
                {"backfill": replacement},
            )
        self.assertEqual(plan.version, 1)
        self.assertEqual(plan.steps["backfill"].dependencies, ("snapshot",))

    def test_only_pending_or_failed_steps_can_be_replanned(self) -> None:
        for status in (
            NS["StepStatus"].RUNNING,
            NS["StepStatus"].VERIFYING,
            NS["StepStatus"].DONE,
            NS["StepStatus"].BLOCKED,
        ):
            plan = self.plan()
            plan.steps["backfill"].status = status
            replacement = NS["PlanStep"](
                "backfill",
                "backfill",
                "customer-index",
                ("snapshot",),
            )
            with self.assertRaises(ValueError):
                NS["apply_replan"](
                    plan,
                    frozenset({"backfill"}),
                    {"backfill": replacement},
                )

    def test_replan_cannot_launder_a_done_dependency(self) -> None:
        plan = self.plan()
        plan.steps["snapshot"].status = NS["StepStatus"].DONE
        plan.steps["backfill"].status = NS["StepStatus"].FAILED
        replacement = NS["PlanStep"](
            "backfill",
            "backfill",
            "customer-index",
        )
        with self.assertRaises(ValueError):
            NS["apply_replan"](
                plan,
                frozenset({"snapshot", "backfill"}),
                {"backfill": replacement},
            )
        self.assertEqual(plan.version, 1)
        self.assertEqual(
            plan.steps["backfill"].dependencies,
            ("snapshot",),
        )

    def test_valid_local_replan_updates_once(self) -> None:
        plan = self.plan()
        plan.steps["backfill"].status = NS["StepStatus"].FAILED
        plan.steps["backfill"].required_evidence = ("receipt",)
        plan.steps["backfill"].attempt_ids = ["attempt-1"]
        plan.steps["backfill"].evidence = {
            "diagnostic": NS["EvidenceRecord"](
                "diagnostic",
                "log-1",
                True,
            )
        }
        replacement = NS["PlanStep"](
            "backfill",
            "backfill",
            "customer-index",
            ("snapshot",),
            ("receipt",),
        )
        NS["apply_replan"](
            plan,
            frozenset({"backfill"}),
            {"backfill": replacement},
        )
        self.assertEqual(plan.version, 2)
        self.assertEqual(
            plan.steps["backfill"].required_evidence,
            ("receipt",),
        )
        self.assertEqual(
            plan.steps["backfill"].attempt_ids,
            ["attempt-1"],
        )
        self.assertIn("diagnostic", plan.steps["backfill"].evidence)

    def test_checkpoint_round_trip_preserves_plan(self) -> None:
        plan = self.plan()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "plan.json"
            NS["checkpoint"](plan, target)
            loaded = NS["load_checkpoint"](target)
        self.assertEqual(loaded.goal, plan.goal)
        self.assertEqual(loaded.scope, plan.scope)
        self.assertEqual(
            [item.step_id for item in NS["ready_steps"](loaded)],
            ["snapshot"],
        )


if __name__ == "__main__":
    unittest.main()
