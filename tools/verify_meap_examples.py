#!/usr/bin/env python3
"""Run the current MEAP examples and tests offline in isolated processes."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SUITES = (
    ('ch02-architecture', 'tests'),
    ('ch04-memory', 'tests'),
    ('ch05-reasoning', 'tests'),
    ('ch06-action', 'current_edition/tests'),
    ('ch07-reflection', 'current_edition/tests'),
    ('ch08-collaboration', 'current_edition/tests'),
    ('ch09-governance', 'tests'),
    ('ch10-methodology', 'tests'),
)
DEMOS = ('ch04-memory', 'ch06-action', 'ch07-reflection',
         'ch08-collaboration', 'ch09-governance')


def main() -> int:
    if sys.version_info < (3, 10):
        print('These examples require Python 3.10 or newer.', file=sys.stderr)
        return 2
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GOOGLE_API_KEY'):
        env.pop(key, None)
    failures = []
    for chapter, tests in SUITES:
        print(f'\nTesting {chapter}', flush=True)
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', tests, '-v'],
            cwd=ROOT / chapter, env=env, timeout=120,
        )
        if result.returncode:
            failures.append(chapter + ': tests')
    for chapter in DEMOS:
        print(f'\nRunning {chapter} offline demo', flush=True)
        # Each chapter has an independent current_edition package.
        command = [sys.executable, '-m', 'current_edition.demo']
        result = subprocess.run(command, cwd=ROOT / chapter, env=env, timeout=60)
        if result.returncode:
            failures.append(chapter + ': demo')
    if failures:
        print('\nFailed: ' + ', '.join(failures), file=sys.stderr)
        return 1
    print('\nAll current MEAP tests and offline demos passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
