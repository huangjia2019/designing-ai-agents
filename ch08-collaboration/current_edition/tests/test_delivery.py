"""The published Chapter 8 entry point stays offline and reviewable."""

import importlib
import unittest

from current_edition.demo import run_demo


class DeliveryTests(unittest.TestCase):
    def test_demo_keeps_three_reports_and_a_human_decision(self):
        result = run_demo()
        self.assertEqual(result["specialists"], ["complexity", "security", "style"])
        self.assertTrue(result["separate_contexts"])
        self.assertEqual(result["shared_workspaces"], 1)
        self.assertTrue(result["human_decision_required"])
        self.assertEqual(result["open_security_claims"], [])
        self.assertIn("safe_parse", result["artifact"])

    def test_earlier_cumulative_api_still_imports(self):
        legacy = importlib.import_module("argus.collaboration")
        self.assertTrue(callable(legacy.ArgusCollaboration.parallel_review))


if __name__ == "__main__":
    unittest.main()
