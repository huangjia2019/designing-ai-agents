"""Import-check every Python file in the repo.

Usage:
    python3 tools/smoke_test.py

For each .py file under chNN-*/, attempts to execute its module body.
Classifies each as:

    PASS          — imports cleanly
    CONCEPTUAL    — top-level `def f(self, ...)` method fragments (by design)
    NEEDS_CONTEXT — undefined name (the book expects DI or a parent class)
    MISSING_IMPORT — module not installed
    OTHER         — any other failure

Expected output on a clean checkout with requirements.txt installed:
    22 PASS + 1 CONCEPTUAL.
"""
from __future__ import annotations
import ast
import importlib.util
import io
import sys
import traceback
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

for ch in sorted(REPO.iterdir()):
    if ch.is_dir() and ch.name.startswith("ch"):
        sys.path.insert(0, str(ch))


def is_conceptual_fragment(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    top_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not top_defs:
        return False
    return any(fn.args.args and fn.args.args[0].arg == "self" for fn in top_defs)


def try_import(path: Path) -> tuple[str, str]:
    if is_conceptual_fragment(path):
        return "CONCEPTUAL", "top-level `def f(self, ...)` — method fragments"
    spec = importlib.util.spec_from_file_location(f"_t_{path.stem}_{id(path)}", path)
    if not spec or not spec.loader:
        return "OTHER", "could not load spec"
    mod = importlib.util.module_from_spec(spec)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            spec.loader.exec_module(mod)
        return "PASS", ""
    except ImportError as e:
        return "MISSING_IMPORT", f"{e.name or 'import'}"
    except NameError as e:
        return "NEEDS_CONTEXT", str(e)
    except Exception as e:
        tb = traceback.format_exc().splitlines()[-1]
        return "OTHER", f"{type(e).__name__}: {tb}"


def main() -> int:
    results = []
    for f in sorted(REPO.rglob("*.py")):
        if f.name == "__init__.py":
            continue
        if any(p in (".venv", "venv", "__pycache__", "tools") for p in f.parts):
            continue
        if not any(p.startswith("ch0") for p in f.parts):
            continue
        status, detail = try_import(f)
        results.append((f, status, detail))

    counts = Counter(r[1] for r in results)
    print("═══ Import test summary ═══")
    for status, n in counts.most_common():
        print(f"  {status:16s} {n}")
    print()
    print("═══ Details ═══")
    marker = {"PASS": "✓", "CONCEPTUAL": "◇",
              "NEEDS_CONTEXT": "⚠", "MISSING_IMPORT": "✗", "OTHER": "✗"}
    for f, status, detail in results:
        rel = f.relative_to(REPO)
        print(f"  {marker.get(status, '?')} [{status:15s}] {rel}")
        if detail and status != "PASS":
            print(f"       → {detail}")

    return 0 if all(s in ("PASS", "CONCEPTUAL") for _, s, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
