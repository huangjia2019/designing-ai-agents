"""Verify the published entry point and revised listing surface."""

import importlib
from pathlib import Path
import unittest

from current_edition.demo import run_demo


class DeliverySmokeTests(unittest.TestCase):
    def test_offline_demo_confirms_one_call_and_rejects_changed_amount(self):
        result = run_demo()
        self.assertEqual(result["first_attempt"], "accepted")
        self.assertEqual(result["same_commit_repeated"], "unknown")
        self.assertEqual(result["changed_amount"], "rejected")
        self.assertEqual(result["provider_calls"], 1)

    def test_all_sixteen_listing_markers_are_present(self):
        action = importlib.import_module("current_edition.action")
        text = Path(action.__file__).read_text(encoding="utf-8")
        for number in range(1, 17):
            self.assertIn(f"# Listing 6.{number} ", text)

    def test_cumulative_compatibility_import_is_preserved(self):
        legacy = importlib.import_module("argus.action")
        self.assertTrue(callable(legacy.ArgusAction))
        self.assertIsNot(
            legacy.ArgusAction,
            importlib.import_module("current_edition.action").ArgusAction,
        )


if __name__ == "__main__":
    unittest.main()
