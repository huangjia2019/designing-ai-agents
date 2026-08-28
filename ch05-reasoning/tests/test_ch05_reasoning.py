from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from argus.reasoning import (
    ArgusReasoning,
    diff_metadata,
    routing_view,
    run_in_sandbox,
)
from patterns.chain_of_thought import (
    ChainOfThought,
    _confidence,
    parse_chain,
    verify_chain,
)
from patterns.complexity_routing import (
    Complexity,
    classify_complexity,
    route_and_reason,
)
from patterns.hypothesis_testing import HypothesisTester
from patterns.reasoning_trace import ReasoningTrace
from patterns.response_text import first_text
from patterns.tree_of_thoughts import ParallelReasoner, ThoughtNode


@dataclass
class Block:
    type: str
    text: str | None = None
    thinking: str | None = None


@dataclass
class Usage:
    input_tokens: int = 3
    output_tokens: int = 7


class Response:
    def __init__(self, *blocks, model="test-model"):
        self.content = list(blocks)
        self.model = model
        self.usage = Usage()


def text_response(text: str, model="test-model") -> Response:
    return Response(Block("text", text=text), model=model)


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("Unexpected model call")
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


class ResponseBoundaryTests(unittest.TestCase):
    def test_first_text_skips_non_text_blocks(self):
        response = Response(
            Block("thinking", thinking="private"),
            Block("text", text="visible"),
        )
        self.assertEqual(first_text(response), "visible")

    def test_confidence_contract(self):
        self.assertEqual(_confidence(None), 0.5)
        self.assertEqual(_confidence("72%"), 0.72)
        self.assertEqual(_confidence("0.72"), 0.72)
        self.assertEqual(_confidence("7.5"), 0.5)
        self.assertEqual(_confidence("-0.2"), 0.5)
        self.assertEqual(_confidence("200%"), 0.5)

    def test_parse_chain_retains_unknown_rating(self):
        chain = parse_chain(
            "Step 1 (0.90): inspect evidence\n"
            "Step 2 (7.5): reject invented scale\n"
            "ANSWER: stop"
        )
        self.assertEqual(len(chain.steps), 2)
        self.assertEqual(chain.steps[1].confidence, 0.5)
        self.assertEqual(chain.final_answer, "stop")


class TargetedVerificationTests(unittest.TestCase):
    def test_verifier_receives_only_target_plus_context(self):
        client = FakeClient([text_response("VERDICT: INVALID\nWHY: leap")])
        chain = ChainOfThought(source_question="Can this change ship?")
        first = chain.add_step("Tests passed", 0.9)
        second = chain.add_step("Therefore every caller is safe", 0.2)

        issues = verify_chain(client, chain, [second])

        self.assertEqual([item["step"] for item in issues], [2])
        self.assertEqual(len(client.messages.calls), 1)
        prompt = client.messages.calls[0]["messages"][0]["content"]
        self.assertIn("Can this change ship?", prompt)
        self.assertIn(first.content, prompt)
        self.assertIn(second.content, prompt)


class RoutingTests(unittest.TestCase):
    def test_ambiguous_or_empty_classifier_defaults_to_moderate(self):
        empty = FakeClient([text_response("")])
        ambiguous = FakeClient([text_response("UNCLEAR")])
        self.assertEqual(
            classify_complexity(empty, "x"),
            Complexity.MODERATE,
        )
        self.assertEqual(
            classify_complexity(ambiguous, "x"),
            Complexity.MODERATE,
        )

    def test_complex_route_uses_adaptive_thinking_and_effort(self):
        client = FakeClient([
            text_response("COMPLEX"),
            Response(
                Block("thinking", thinking="internal"),
                Block("text", text="answer"),
                model="claude-sonnet-4-6",
            ),
        ])
        result = route_and_reason(client, "debug this")
        kwargs = client.messages.calls[1]
        self.assertEqual(kwargs["thinking"], {"type": "adaptive"})
        self.assertEqual(kwargs["output_config"], {"effort": "high"})
        self.assertEqual(result["answer"], "answer")

    def test_deleted_file_metadata_reaches_consequence_gate(self):
        diff = """diff --git a/auth.py b/auth.py
deleted file mode 100644
--- a/auth.py
+++ /dev/null
@@ -1 +0,0 @@
-secret = True
"""
        metadata = diff_metadata(diff)
        self.assertEqual(metadata.deleted_files, ("auth.py",))
        self.assertIn("Deleted files: ['auth.py']", routing_view(diff))

        client = FakeClient([])
        result = ArgusReasoning(client=client).review(diff)
        self.assertTrue(result.governed)
        self.assertEqual(result.complexity, "governed")
        self.assertEqual(client.messages.calls, [])

    def test_moderate_argus_review_verifies_only_weakest_step(self):
        diff = """diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -1 +1 @@
-value = 1
+value = 2
"""
        client = FakeClient([
            text_response("MODERATE"),
            text_response(
                "Step 1 (0.90): read the change\n"
                "Step 2 (0.20): inspect callers\n"
                "ANSWER: review"
            ),
            text_response("VERDICT: SOUND\nWHY: follows"),
        ])
        result = ArgusReasoning(client=client).review(diff)
        verify_prompt = client.messages.calls[2]["messages"][0]["content"]
        self.assertIn("Step 2", verify_prompt)
        self.assertIn("read the change", verify_prompt)
        self.assertEqual(result.trace.reasoning_steps, 2)
        self.assertEqual(result.trace.backtracks, 0)


class ParallelExplorationTests(unittest.TestCase):
    def test_score_contract(self):
        self.assertEqual(
            ParallelReasoner._parse_score(text_response("SCORE: 80%")),
            0.8,
        )
        self.assertEqual(
            ParallelReasoner._parse_score(text_response("SCORE: 80")),
            0.5,
        )
        self.assertEqual(
            ParallelReasoner._parse_score(text_response("SCORE: -0.2")),
            0.5,
        )

    def test_branch_limit_is_enforced(self):
        reasoner = ParallelReasoner(FakeClient([]))
        root = ThoughtNode("n0", "problem")
        reasoner.nodes[root.id] = root
        response = text_response("- A\n- B\n- C\n- D")
        children = reasoner._parse_thoughts(response, root, 2)
        self.assertEqual([item.content for item in children], ["A", "B"])

    def test_barren_expansion_stops_without_random_choice(self):
        client = FakeClient([
            text_response("No usable bullet lines"),
            text_response("SCORE: 0.4"),
        ])
        path = ParallelReasoner(client).search("problem", n_iter=1)
        self.assertEqual(list(path), ["problem"])


class HypothesisTests(unittest.TestCase):
    def test_budget_exhaustion_returns_inconclusive_evidence_trail(self):
        client = FakeClient([
            text_response("rg -n TODO ."),
            text_response("- stale cache"),
            text_response(
                "ACTION: pytest -q\n"
                "IF_TRUE: failure repeats\n"
                "IF_FALSE: suite passes"
            ),
            text_response("VERDICT: INCONCLUSIVE\nWHY: mixed result"),
        ])
        actions = []

        def execute(command):
            actions.append(command)
            return "mixed result"

        result = HypothesisTester(
            client,
            execute,
            max_iterations=1,
        ).investigate("intermittent failure")

        self.assertEqual(result["outcome"], "inconclusive")
        self.assertEqual(result["verdict"], "inconclusive")
        self.assertEqual(len(result["observations"]), 2)
        self.assertEqual(actions, ["rg -n TODO .", "pytest -q"])


class BoundedRunnerTests(unittest.TestCase):
    def test_runner_denies_writes_shells_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("[refused]", run_in_sandbox("rm file", directory))
            self.assertIn(
                "[refused]",
                run_in_sandbox("python -c 'print(1)'", directory),
            )
            self.assertIn(
                "[refused]",
                run_in_sandbox("ls ; rm file", directory),
            )
            self.assertIn(
                "[refused]",
                run_in_sandbox("cat ../../etc/passwd", directory),
            )
            self.assertIn(
                "[refused]",
                run_in_sandbox("find . -delete", directory),
            )

    def test_runner_pins_working_directory_and_bounds_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.txt").write_text("x" * 5000)
            listing = run_in_sandbox("ls", directory)
            output = run_in_sandbox("cat large.txt", directory)
            self.assertIn("large.txt", listing)
            self.assertIn("[...truncated]", output)


class TelemetryTests(unittest.TestCase):
    def test_trace_metrics_are_wired_to_output_tokens(self):
        trace = ReasoningTrace(
            query_id="q1",
            classified_complexity="moderate",
            model_used="test",
            output_tokens=500,
            reasoning_steps=4,
            hypotheses_generated=2,
            hypotheses_refuted=1,
        )
        self.assertEqual(trace.steps_per_1k_output_tokens, 8.0)
        self.assertEqual(trace.hypothesis_refutation_rate, 0.5)


class CumulativeSnapshotTests(unittest.TestCase):
    def test_chapter_5_reasoning_files_match_later_argus_snapshots(self):
        repo = Path(__file__).resolve().parents[2]
        downstream = [
            "ch06-action",
            "ch07-reflection",
            "ch08-collaboration",
            "ch09-governance",
            "ch10-methodology",
        ]
        files = [
            "argus/reasoning.py",
            "patterns/chain_of_thought.py",
            "patterns/complexity_routing.py",
            "patterns/hypothesis_testing.py",
            "patterns/reasoning_trace.py",
            "patterns/response_text.py",
        ]
        for relative in files:
            canonical = (repo / "ch05-reasoning" / relative).read_bytes()
            for chapter in downstream:
                with self.subTest(chapter=chapter, file=relative):
                    self.assertEqual(
                        (repo / chapter / relative).read_bytes(),
                        canonical,
                    )


if __name__ == "__main__":
    unittest.main()
