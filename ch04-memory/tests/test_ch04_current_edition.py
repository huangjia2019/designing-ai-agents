"""Offline tests against the current Chapter 4 native modules."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

package_root = Path(__file__).resolve().parents[1] / "current_edition"
spec = importlib.util.spec_from_file_location(
    "ch04_current_edition", package_root / "__init__.py",
    submodule_search_locations=[str(package_root)],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)

from ch04_current_edition import (
    ArgusMemory, Chunk, FailureJournal, HierarchicalMemory,
    InMemoryIndex, MemoryTier, ProgressTracker, RAGPipeline, TaskStatus,
)
from ch04_current_edition.support import SearchResult


class FixedModel:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if prompt.startswith("Rewrite"):
            return "incident travel manager exemption"
        if "Generate 3-5 short tags" in prompt:
            return "python,dependency,import"
        if "candidate heuristic" in prompt:
            return "Check package ownership before changing imports."
        return prompt


class ChunkIndex:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def search(self, query, top_k=5):
        self.queries.append((query, top_k))
        return self.chunks[:top_k]


class RetentionTests(unittest.TestCase):
    def test_budget_evicts_lower_priority_entries_to_session(self):
        memory = HierarchicalMemory(InMemoryIndex(), working_budget=8)
        memory.add("current GraphQL project rule", "project_rule", 1.0)
        memory.add("old JSON API note that is long", "candidate", 0.1)
        self.assertTrue(memory.session)
        self.assertTrue(all(e.tier == MemoryTier.SESSION for e in memory.session))
        self.assertLessEqual(sum(e.token_count for e in memory.working), 8)
        memory.consolidate()
        memory.working.clear()
        memory.session.clear()
        self.assertIn(
            "current GraphQL project rule", memory.retrieve("GraphQL project")
        )

    def test_proposal_does_not_implicitly_consolidate_or_apply(self):
        index = InMemoryIndex()
        memory = HierarchicalMemory(index)
        argus = ArgusMemory(memory)
        argus.propose_after_review("check package ownership", "example-api")
        self.assertEqual(index._items, [])
        self.assertEqual(memory.working[0].source, "reflection_candidate")
        self.assertEqual(
            argus.retrieve_candidates_for_review("example-api", "package"), []
        )
        memory.consolidate()
        later = ArgusMemory(HierarchicalMemory(index))
        self.assertEqual(
            later.retrieve_candidates_for_review("example-api", "package"),
            ["[example-api] check package ownership"],
        )
        self.assertEqual(index._items[0].metadata["source"], "reflection_candidate")

    def test_retention_threshold_is_not_a_truth_or_authority_score(self):
        index = InMemoryIndex()
        memory = HierarchicalMemory(index)
        memory.add("ordinary low importance note", "tool", 0.2)
        memory.add("high importance candidate", "reflection_candidate", 0.8)
        memory.consolidate()
        self.assertEqual(len(index._items), 1)
        self.assertEqual(index._items[0].text, "high importance candidate")
        self.assertNotIn("approved", index._items[0].metadata)

    def test_retrieval_obeys_k_and_working_budget(self):
        index = InMemoryIndex()
        for word in ("alpha", "beta", "gamma", "delta"):
            index.upsert("shared query " + word)
        memory = HierarchicalMemory(index, working_budget=4)
        results = memory.retrieve("shared query", k=2)
        self.assertEqual(len(results), 2)
        self.assertLessEqual(sum(e.token_count for e in memory.working), 4)
        self.assertTrue(memory.session)


class RAGTests(unittest.TestCase):
    def test_hybrid_retrieval_uses_both_queries_and_preserves_sources(self):
        general = Chunk("Travel needs manager approval", "policy.md", "general", 0.9)
        exception = Chunk("Incident travel is exempt", "exceptions.md", "incident", 0.8)
        semantic = ChunkIndex([general])
        keyword = ChunkIndex([exception])
        model = FixedModel()
        pipeline = RAGPipeline(model, semantic, keyword)
        prompt = pipeline.query("incident travel approval")
        self.assertEqual(semantic.queries[0][0], "incident travel manager exemption")
        self.assertEqual(keyword.queries[0][0], "incident travel approval")
        self.assertIn("[Source: policy.md]", prompt)
        self.assertIn("[Source: exceptions.md]", prompt)

    def test_rank_fusion_deduplicates_the_same_chunk(self):
        first = Chunk("same policy text", "policy.md", "semantic", 0.9)
        duplicate = Chunk("same policy text", "policy.md", "keyword", 0.8)
        pipeline = RAGPipeline(FixedModel(), ChunkIndex([]), ChunkIndex([]))
        merged = pipeline._rrf_merge([first], [duplicate])
        self.assertEqual(len(merged), 1)
        self.assertIs(merged[0], first)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "progress.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_completed_work_reloads_from_json(self):
        first = ProgressTracker(str(self.path))
        first.create_plan(["inspect source", "review proposed fix"])
        first.complete(0, "source v3 checked", ["policy.md"])
        later = ProgressTracker(str(self.path))
        self.assertIs(later.items[0].status, TaskStatus.COMPLETED)
        self.assertEqual(later.items[0].result, "source v3 checked")
        self.assertEqual(later.items[0].files_modified, ["policy.md"])
        self.assertIn("review proposed fix", later.resumption_context())
        self.assertIn("Progress: 1/2", later.resumption_context())

    def test_failed_work_retains_error_for_resumption(self):
        first = ProgressTracker(str(self.path))
        first.create_plan(["inspect source"])
        first.fail(0, "source unavailable")
        later = ProgressTracker(str(self.path))
        self.assertIs(later.items[0].status, TaskStatus.FAILED)
        self.assertIn("source unavailable", later.resumption_context())

    def test_corrupt_snapshot_is_not_silently_treated_as_empty(self):
        self.path.write_text("{broken")
        with self.assertRaises(json.JSONDecodeError):
            ProgressTracker(str(self.path))


class FailureJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "failures.jsonl"
        self.index = InMemoryIndex()
        self.model = FixedModel()
        self.journal = FailureJournal(self.model, self.index, str(self.path))

    def tearDown(self):
        self.temp.cleanup()

    def record_one(self):
        return self.journal.record(
            "unexpected jwt import",
            "ImportError: wrong distribution",
            "inspect package metadata",
        )

    def test_record_preserves_source_failure_and_candidate_wording(self):
        entry = self.record_one()
        row = json.loads(self.path.read_text())
        self.assertEqual(row["context"], "unexpected jwt import")
        self.assertEqual(row["error_type"], "ImportError")
        self.assertEqual(row["fix"], "inspect package metadata")
        self.assertEqual(row["candidate_heuristic"], entry.candidate_heuristic)
        self.assertNotIn("heuristic", row)
        self.assertIn("Propose a candidate heuristic", self.model.prompts[0])

    def test_consultation_returns_candidate_material_for_review(self):
        self.record_one()
        entries = self.journal.consult_candidates(
            "jwt import distribution", min_score=0.0
        )
        self.assertEqual(len(entries), 1)
        self.assertIn("package ownership", entries[0].candidate_heuristic)
        self.assertEqual(entries[0].fix, "inspect package metadata")
        self.assertEqual(entries[0].error_message, "ImportError: wrong distribution")

    def test_consultation_threshold_is_strict_and_caller_supplied(self):
        class FixedResults:
            def search(self, query, top_k):
                return [
                    SearchResult("a | error | candidate A", 0.7),
                    SearchResult("b | error | candidate B", 0.8),
                ][:top_k]
        journal = FailureJournal(self.model, FixedResults(), str(self.path))
        entries = journal.consult_candidates("query", min_score=0.7, k=2)
        self.assertEqual([x.candidate_heuristic for x in entries], ["candidate B"])

    def test_second_failure_appends_without_rewriting_first(self):
        self.record_one()
        first_line = self.path.read_text().splitlines()[0]
        self.journal.record("second task", "TimeoutError: delayed", "retry later")
        lines = self.path.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], first_line)


if __name__ == "__main__":
    unittest.main()
