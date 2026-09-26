"""Executable checks for the two Chapter 10 listings."""

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


EXAMPLES = Path(__file__).parents[1] / "examples" / "ch10"
sys.path.insert(0, str(EXAMPLES))

from argus_completion import Argus, Decision, Evidence  # noqa: E402
from composition_contracts import EvaluationReceipt, decide  # noqa: E402


class Perception:
    async def build(self, *, task, read_file):
        return await read_file("in-scope.txt")


class Memory:
    def __init__(self):
        self.records = []

    async def recall(self, task, context):
        return []

    async def record(self, **record):
        self.records.append(record)


class Reasoning:
    async def plan(self, task, context, memory):
        return SimpleNamespace(
            action="review",
            version="plan-v1",
            write_set=("report.md",),
        )


class Governance:
    def authorized_reader(self, task):
        async def read_file(path):
            assert path == "in-scope.txt"
            return "content"

        return read_file

    def authorize(self, **request):
        assert request["plan_version"] == "plan-v1"
        assert request["write_set"] == ("report.md",)
        return Decision(
            allowed=True,
            plan_version=request["plan_version"],
            write_set=request["write_set"],
        )

    def authorize_memory(self, **request):
        assert request["evidence"].passed
        return Decision(allowed=True)


class Action:
    async def execute(self, plan, decision):
        assert decision.plan_version == plan.version
        assert decision.write_set == plan.write_set
        return {"changed": True}


class Reflection:
    async def verify(self, task, effect):
        return Evidence(passed=True, detail="review passed")


class Task:
    async def acceptance_probe(self, effect):
        return Evidence(passed=True, detail="external probe passed")


class MissingReflection:
    async def verify(self, task, effect):
        return None


class FailedTask:
    async def acceptance_probe(self, effect):
        return Evidence(passed=False, detail="external probe failed")


class Chapter10ExamplesTest(unittest.TestCase):
    def test_composition_decision(self) -> None:
        accepted = EvaluationReceipt(
            decision_id="d-1",
            operating_point="model=m1;tools=t1;authority=a1",
            workload_version="w-1",
            evidence_refs=("run://baseline/1", "run://proposal/1"),
            baseline_failed=True,
            proposal_passed=True,
            seam_tests_passed=True,
            external_acceptance_passed=True,
            risk_gates_passed=True,
        )
        self.assertEqual(decide(accepted), "ACCEPT_PROVISIONALLY")

        unnecessary = EvaluationReceipt(
            decision_id="d-2",
            operating_point="model=m1;tools=t1;authority=a1",
            workload_version="w-1",
            evidence_refs=("run://baseline/2",),
            baseline_failed=False,
            proposal_passed=True,
            seam_tests_passed=True,
            external_acceptance_passed=True,
            risk_gates_passed=True,
        )
        self.assertTrue(decide(unnecessary).startswith("REJECT"))

        no_evidence = EvaluationReceipt(
            decision_id="d-3",
            operating_point="model=m1;tools=t1;authority=a1",
            workload_version="w-1",
            evidence_refs=(),
            baseline_failed=True,
            proposal_passed=True,
            seam_tests_passed=True,
            external_acceptance_passed=True,
            risk_gates_passed=True,
        )
        self.assertEqual(decide(no_evidence),
                         "REJECT: no evidence attached")

    def test_argus_records_only_accepted_work(self) -> None:
        memory = Memory()
        argus = Argus(
            Perception(),
            memory,
            Reasoning(),
            Governance(),
            Action(),
            Reflection(),
        )
        receipt = asyncio.run(argus.review(Task()))
        self.assertTrue(receipt.complete)
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(len(memory.records), 1)

    def test_missing_reflection_remains_incomplete(self) -> None:
        memory = Memory()
        argus = Argus(
            Perception(),
            memory,
            Reasoning(),
            Governance(),
            Action(),
            MissingReflection(),
        )
        receipt = asyncio.run(argus.review(Task()))
        self.assertFalse(receipt.complete)
        self.assertEqual(receipt.status, "INCOMPLETE")
        self.assertEqual(memory.records, [])

    def test_failed_external_probe_never_reaches_memory(self) -> None:
        memory = Memory()
        argus = Argus(
            Perception(),
            memory,
            Reasoning(),
            Governance(),
            Action(),
            Reflection(),
        )
        receipt = asyncio.run(argus.review(FailedTask()))
        self.assertFalse(receipt.complete)
        self.assertEqual(receipt.status, "INCOMPLETE")
        self.assertEqual(memory.records, [])


if __name__ == "__main__":
    unittest.main()
