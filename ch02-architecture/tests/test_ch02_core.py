"""Offline source/import checks; no provider or model calls are made."""
import ast
import importlib.util
import inspect
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChapterTwoDeliveryTests(unittest.TestCase):
    def test_current_listing_sources_compile(self):
        for relative in ("argus/core.py", "demos/openai_argus.py", "demos/langgraph_argus.py"):
            with self.subTest(source=relative):
                source = ROOT / relative
                compile(source.read_text(), str(source), "exec")

    def test_review_interface_imports_without_initializing_a_provider(self):
        spec = importlib.util.spec_from_file_location("ch02_current_core", ROOT / "argus/core.py")
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        signature = inspect.signature(core.review_diff)
        self.assertEqual(tuple(signature.parameters), ("diff", "context"))
        self.assertEqual(signature.parameters["context"].default, "")

    def test_default_model_matches_current_listing(self):
        tree = ast.parse((ROOT / "argus/core.py").read_text())
        models = [keyword.value.value for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  for keyword in node.keywords
                  if keyword.arg == "model" and isinstance(keyword.value, ast.Constant)]
        self.assertEqual(models, ["claude-sonnet-4-6"])


if __name__ == "__main__":
    unittest.main()
