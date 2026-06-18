#!/usr/bin/env python3
"""Smoke test — verify every chapter's Argus + patterns is sane.

Two tiers (post-cumulative-refactor on 2026-06-17):

  1. AST parse on every .py file (catches syntax errors).
  2. `import argus` from each chNN-*/ directory (catches dependency
     / wiring errors in the cumulative chain).

Pass criteria:
  * All .py files parse cleanly.
  * All chapters with an argus/ package import cleanly (Ch2 through Ch10).

For pattern-level smoke (individual pattern imports in isolation),
each chapter ships its own demo scripts under demos/.
"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_check(path: Path) -> tuple[bool, str]:
    try:
        ast.parse(path.read_text())
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError {e.lineno}: {e.msg}"


def import_check(chapter_dir: Path) -> tuple[bool, str]:
    """Run `python -c "import argus"` with chapter dir as cwd."""
    if not (chapter_dir / "argus").exists():
        return True, "(no argus/)"
    result = subprocess.run(
        [sys.executable, "-c", "import argus; print('OK')"],
        cwd=chapter_dir,
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return True, ""
    err = (result.stderr.strip().splitlines() or ["unknown failure"])[-1]
    return False, err


def main() -> int:
    chapters = sorted(d for d in ROOT.iterdir()
                      if d.is_dir() and d.name.startswith("ch"))
    parse_ok = parse_fail = 0
    import_ok = import_fail = 0
    failures = []

    print(f"Smoke test in {ROOT}\n")
    print("--- AST parse (every .py file) ---")
    for ch in chapters:
        for f in ch.rglob("*.py"):
            ok, err = parse_check(f)
            if ok:
                parse_ok += 1
            else:
                parse_fail += 1
                failures.append(f"PARSE  {f.relative_to(ROOT)}: {err}")
    print(f"  {parse_ok} ok / {parse_fail} fail")

    print("\n--- Argus import (cd chNN-* && python -c 'import argus') ---")
    for ch in chapters:
        ok, err = import_check(ch)
        if ok:
            import_ok += 1
            print(f"  [OK]   {ch.name:28} {err}")
        else:
            import_fail += 1
            failures.append(f"IMPORT {ch.name}: {err}")
            print(f"  [FAIL] {ch.name:28} {err}")

    print()
    print(f"Summary: parse {parse_ok}/{parse_ok+parse_fail} clean, "
          f"argus import {import_ok}/{import_ok+import_fail} clean")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
