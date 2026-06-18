# argus/cli.py — End-to-end entry point for Ch3 Argus.
#
# Run:
#     python -m argus.cli <path-to-diff-file> [--repo /path/to/repo] [--budget 50000]
#
# Reads the diff from disk, runs the PRA loop with perception, and prints
# both the JSON review and the PerceptionTrace so the reader can see what
# the perception module actually decided.
import argparse
import json
import logging
import sys
from pathlib import Path

from . import review_diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="argus",
        description="Argus Ch3: PR review agent with perception.",
    )
    parser.add_argument("diff_file", help="path to a unified diff file")
    parser.add_argument(
        "--repo", default=".",
        help="path to the repository root (default: current directory)",
    )
    parser.add_argument(
        "--budget", type=int, default=50_000,
        help="token budget for perception (default: 50,000)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="emit perception logger info messages",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    diff_path = Path(args.diff_file)
    if not diff_path.exists():
        print(f"error: diff file not found: {diff_path}", file=sys.stderr)
        return 2
    diff = diff_path.read_text()

    review, trace = review_diff(diff, repo_root=args.repo, budget=args.budget)

    print("=== Perception trace ===")
    print(json.dumps({
        "files_discovered": trace.files_discovered,
        "files_selected":   trace.files_selected,
        "files_dropped":    trace.files_dropped,
        "selectivity":      round(trace.selectivity, 3),
        "tokens_considered": trace.tokens_considered,
        "tokens_selected":   trace.tokens_selected,
        "dropped_files":     trace.dropped_files,
    }, indent=2))
    print("\n=== Review ===")
    print(json.dumps(review, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
