"""Argus Chapter 5 reasoning layer.

Difficulty selects a reasoning path. Consequence is evaluated first and may
route a deceptively simple change to human review. The returned result carries
an observable reasoning trace; it does not claim access to private model
reasoning.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from patterns.chain_of_thought import (
    ChainOfThought,
    reason_with_cot,
    verify_chain,
)
from patterns.complexity_routing import (
    ROUTING_TABLE,
    Complexity,
    classify_complexity,
)
from patterns.hypothesis_testing import HypothesisTester
from patterns.reasoning_trace import ReasoningTrace
from patterns.response_text import first_text


REVISE_STEP_PROMPT = """A verifier flagged one represented step as invalid.
Rewrite only that step. Leave every other step unchanged.

Steps already accepted:
{prior}

Flawed step {step_number} (confidence {confidence:.2f}):
{content}

Verifier objection:
{issue}

Reply in exactly this format:
REVISED: <the corrected step>
CONFIDENCE: <0.0-1.0>
"""

REDERIVE_ANSWER_PROMPT = """A represented reasoning chain was repaired.
Restate the conclusion so it follows from the steps as they now stand.

{steps}

Previous conclusion:
{old_answer}

Reply with the conclusion only.
"""

_ALLOWED_COMMANDS = frozenset({
    "cat",
    "find",
    "git",
    "grep",
    "head",
    "ls",
    "pytest",
    "python",
    "python3",
    "rg",
    "tail",
    "wc",
})
_ALLOWED_GIT_SUBCOMMANDS = frozenset({
    "blame",
    "diff",
    "grep",
    "log",
    "show",
    "status",
})
_FORBIDDEN_FIND_OPTIONS = frozenset({
    "-delete",
    "-exec",
    "-execdir",
    "-fprint",
    "-fprintf",
    "-fls",
    "-ok",
    "-okdir",
})
_SHELL_OPERATORS = frozenset({";", "|", "||", "&&", ">", ">>", "<"})
_MAX_OUTPUT_CHARS = 4000


@dataclass(frozen=True)
class DiffMetadata:
    files: tuple[str, ...]
    added_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    renamed_files: tuple[tuple[str, str], ...]
    hunks: int


def _normalize_diff_path(raw: str) -> str:
    value = raw.split("\t", 1)[0].strip().strip('"')
    if value in {"/dev/null", "dev/null"}:
        return "/dev/null"
    if value.startswith(("a/", "b/")):
        return value[2:]
    return value


def diff_metadata(diff: str) -> DiffMetadata:
    """Extract path changes without losing ``/dev/null`` semantics."""
    files: set[str] = set()
    added: set[str] = set()
    deleted: set[str] = set()
    renamed: set[tuple[str, str]] = set()
    lines = diff.splitlines()
    old_path: str | None = None
    rename_from: str | None = None

    for line in lines:
        if line.startswith("diff --git "):
            parts = shlex.split(line)
            if len(parts) >= 4:
                for item in parts[2:4]:
                    path = _normalize_diff_path(item)
                    if path != "/dev/null":
                        files.add(path)
        elif line.startswith("--- "):
            old_path = _normalize_diff_path(line[4:])
        elif line.startswith("+++ ") and old_path is not None:
            new_path = _normalize_diff_path(line[4:])
            if old_path == "/dev/null" and new_path != "/dev/null":
                added.add(new_path)
                files.add(new_path)
            elif new_path == "/dev/null" and old_path != "/dev/null":
                deleted.add(old_path)
                files.add(old_path)
            else:
                if old_path != "/dev/null":
                    files.add(old_path)
                if new_path != "/dev/null":
                    files.add(new_path)
            old_path = None
        elif line.startswith("rename from "):
            rename_from = _normalize_diff_path(line[len("rename from "):])
        elif line.startswith("rename to ") and rename_from is not None:
            rename_to = _normalize_diff_path(line[len("rename to "):])
            renamed.add((rename_from, rename_to))
            files.update((rename_from, rename_to))
            rename_from = None

    return DiffMetadata(
        files=tuple(sorted(files)),
        added_files=tuple(sorted(added)),
        deleted_files=tuple(sorted(deleted)),
        renamed_files=tuple(sorted(renamed)),
        hunks=sum(line.startswith("@@") for line in lines),
    )


def routing_view(diff: str) -> str:
    """Build a bounded input for consequence policy and difficulty routing."""
    metadata = diff_metadata(diff)
    return (
        f"Files: {list(metadata.files)}\n"
        f"Added files: {list(metadata.added_files)}\n"
        f"Deleted files: {list(metadata.deleted_files)}\n"
        f"Renamed files: {list(metadata.renamed_files)}\n"
        f"Hunks: {metadata.hunks}\n"
        f"Diff excerpt:\n{diff[:4000]}"
    )


class DefaultReviewPolicy:
    """Small teaching policy for consequence-first routing."""

    high_impact_markers = (
        "async",
        "auth",
        "billing",
        "credential",
        "generated",
        "lock",
        "migration",
        "openapi",
        "payment",
        "permission",
        "production",
        "security",
        "thread",
        "token",
    )

    def requires_governed_review(self, view: str) -> bool:
        metadata_prefix = view.split("Diff excerpt:", 1)[0]
        deleted_line = next(
            (
                line
                for line in metadata_prefix.splitlines()
                if line.startswith("Deleted files:")
            ),
            "Deleted files: []",
        )
        if deleted_line != "Deleted files: []":
            return True
        lowered = view.lower()
        return any(marker in lowered for marker in self.high_impact_markers)


@dataclass
class ReviewResult:
    verdict: str
    reasoning_steps: list = field(default_factory=list)
    complexity: str = "simple"
    confidence: float = 1.0
    trace: ReasoningTrace | None = None
    governed: bool = False
    routing_view: str = ""


def _usage_output_tokens(response) -> int:
    usage = getattr(response, "usage", None)
    value = getattr(usage, "output_tokens", 0)
    return value if isinstance(value, int) else 0


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _new_query_id() -> str:
    return uuid.uuid4().hex[:12]


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def run_in_sandbox(
    cmd: str,
    repo_path: str,
    timeout: int = 30,
) -> str:
    """Run one bounded, read-oriented check without invoking a shell.

    This is a teaching guardrail, not process or network isolation. Running a
    repository's tests still executes repository code. Chapter 9 supplies the
    stronger containment boundary.
    """
    try:
        root = Path(repo_path).resolve(strict=True)
    except OSError as exc:
        return f"[refused] invalid repository path: {exc}"
    if not root.is_dir():
        return "[refused] repository path is not a directory"

    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return f"[refused] unparseable command: {exc}"
    if not argv:
        return "[refused] empty command"
    if any(
        token in _SHELL_OPERATORS or "$(" in token or "`" in token
        for token in argv
    ):
        return "[refused] shell operators are not permitted"

    head = os.path.basename(argv[0])
    if head not in _ALLOWED_COMMANDS:
        return f"[refused] {head!r} is not on the allowlist"
    if head == "git":
        subcommand = argv[1] if len(argv) > 1 else ""
        if subcommand not in _ALLOWED_GIT_SUBCOMMANDS:
            return f"[refused] git {subcommand!r} may write"
    if head == "find" and any(
        token in _FORBIDDEN_FIND_OPTIONS for token in argv[1:]
    ):
        return "[refused] this find option may write or execute"
    if head in {"python", "python3"} and argv[1:3] != ["-m", "pytest"]:
        return "[refused] Python is limited to 'python -m pytest'"

    for token in argv[1:]:
        if token.startswith("-"):
            continue
        if "/" not in token and not token.startswith("."):
            continue
        candidate = Path(token)
        if ".." in candidate.parts:
            return "[refused] path traversal is not permitted"
        if candidate.is_absolute() and not _path_is_within(
            candidate.resolve(), root
        ):
            return "[refused] absolute path leaves the repository"

    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=max(1, timeout),
            shell=False,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return f"[timeout] no result after {max(1, timeout)}s"
    except OSError as exc:
        return f"[error] {exc}"

    output = (completed.stdout + completed.stderr).strip()
    if len(output) > _MAX_OUTPUT_CHARS:
        output = f"{output[:_MAX_OUTPUT_CHARS]}\n[...truncated]"
    if not output:
        return f"[exit {completed.returncode}] (no output)"
    return f"[exit {completed.returncode}]\n{output}"


def _parse_revision(text: str) -> tuple[str | None, float | None]:
    match = re.search(
        r"REVISED:\s*(.+?)(?=\nCONFIDENCE:|\Z)",
        text,
        re.DOTALL,
    )
    if not match:
        return None, None
    content = match.group(1).strip() or None
    confidence = None
    confidence_match = re.search(
        r"CONFIDENCE:\s*([+-]?[0-9]*\.?[0-9]+)",
        text,
    )
    if confidence_match:
        value = float(confidence_match.group(1))
        if 0.0 <= value <= 1.0:
            confidence = value
    return content, confidence


class ArgusReasoning:
    def __init__(self, client=None, review_policy=None):
        self._client = client
        self.review_policy = review_policy or DefaultReviewPolicy()
        self._last_backtracks = 0

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def review(self, diff: str) -> ReviewResult:
        started = time.perf_counter()
        view = routing_view(diff)
        if self.review_policy.requires_governed_review(view):
            return self.request_human_review(diff, view, started)

        complexity = classify_complexity(
            self.client,
            f"Code review task:\n{view}",
        )
        if complexity == Complexity.SIMPLE:
            return self.quick_review(diff, view, started)
        if complexity == Complexity.MODERATE:
            return self.review_with_reasoning(
                diff,
                complexity,
                view,
                started,
            )
        return self.deep_review(diff, view, started)

    def request_human_review(
        self,
        diff: str,
        view: str = "",
        started: float | None = None,
    ) -> ReviewResult:
        started = started if started is not None else time.perf_counter()
        trace = ReasoningTrace(
            query_id=_new_query_id(),
            classified_complexity="governed",
            model_used="human-review-gate",
            wall_time_ms=_elapsed_ms(started),
        )
        return ReviewResult(
            verdict="Human review required before model-depth routing.",
            complexity="governed",
            confidence=0.0,
            trace=trace,
            governed=True,
            routing_view=view or routing_view(diff),
        )

    def quick_review(
        self,
        diff: str,
        view: str = "",
        started: float | None = None,
    ) -> ReviewResult:
        started = started if started is not None else time.perf_counter()
        config = ROUTING_TABLE[Complexity.SIMPLE]
        response = self.client.messages.create(
            model=config["model"],
            max_tokens=config["max_tokens"],
            messages=[{
                "role": "user",
                "content": (
                    f"Quick code review:\n{diff}\n\n"
                    "List up to three severity-tagged issues."
                ),
            }],
        )
        confidence = 0.8
        trace = ReasoningTrace(
            query_id=_new_query_id(),
            classified_complexity=Complexity.SIMPLE.value,
            model_used=config["model"],
            output_tokens=_usage_output_tokens(response),
            final_confidence=confidence,
            wall_time_ms=_elapsed_ms(started),
        )
        return ReviewResult(
            verdict=first_text(response),
            complexity=Complexity.SIMPLE.value,
            confidence=confidence,
            trace=trace,
            routing_view=view,
        )

    def review_with_reasoning(
        self,
        diff: str,
        complexity: Complexity,
        view: str = "",
        started: float | None = None,
    ) -> ReviewResult:
        started = started if started is not None else time.perf_counter()
        chain = reason_with_cot(
            self.client,
            "Review this code diff for bugs, security issues, "
            f"and style problems:\n{diff}",
        )
        self._last_backtracks = 0
        weakest = chain.weakest_step
        if weakest is not None:
            issues = verify_chain(self.client, chain, [weakest])
            if issues:
                chain = self.revise_chain(chain, issues)
        confidence = (
            min(step.confidence for step in chain.steps)
            if chain.steps
            else 0.5
        )
        model = ROUTING_TABLE[complexity]["model"]
        trace = ReasoningTrace(
            query_id=_new_query_id(),
            classified_complexity=complexity.value,
            model_used=model,
            reasoning_steps=len(chain.steps),
            backtracks=self._last_backtracks,
            final_confidence=confidence,
            wall_time_ms=_elapsed_ms(started),
        )
        return ReviewResult(
            verdict=chain.final_answer,
            reasoning_steps=chain.steps,
            complexity=complexity.value,
            confidence=confidence,
            trace=trace,
            routing_view=view,
        )

    def revise_chain(
        self,
        chain: ChainOfThought,
        issues: list[dict],
    ) -> ChainOfThought:
        flagged: dict[int, list[str]] = {}
        for issue in issues:
            flagged.setdefault(issue["step"], []).append(issue["issue"])
        by_number = {step.step_number: step for step in chain.steps}
        revised = 0
        for number in sorted(flagged):
            step = by_number.get(number)
            if step is None:
                continue
            prior = "\n".join(
                f"Step {item.step_number}: {item.content}"
                for item in chain.steps
                if item.step_number < number
            )
            response = self.client.messages.create(
                model=ROUTING_TABLE[Complexity.MODERATE]["model"],
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": REVISE_STEP_PROMPT.format(
                        prior=prior or "(none)",
                        step_number=number,
                        confidence=step.confidence,
                        content=step.content,
                        issue="\n".join(flagged[number]),
                    ),
                }],
            )
            content, confidence = _parse_revision(first_text(response))
            if content is None:
                continue
            step.content = content
            if confidence is not None:
                step.confidence = confidence
            revised += 1
        if revised:
            chain.final_answer = self._rederive_answer(chain)
        self._last_backtracks += revised
        return chain

    def _rederive_answer(self, chain: ChainOfThought) -> str:
        steps = "\n".join(
            f"Step {step.step_number} "
            f"(confidence {step.confidence:.2f}): {step.content}"
            for step in chain.steps
        )
        response = self.client.messages.create(
            model=ROUTING_TABLE[Complexity.MODERATE]["model"],
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": REDERIVE_ANSWER_PROMPT.format(
                    steps=steps,
                    old_answer=chain.final_answer or "(none)",
                ),
            }],
        )
        return first_text(response).strip()

    def deep_review(
        self,
        diff: str,
        view: str = "",
        started: float | None = None,
    ) -> ReviewResult:
        started = started if started is not None else time.perf_counter()
        config = ROUTING_TABLE[Complexity.COMPLEX]
        kwargs = {
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "messages": [{
                "role": "user",
                "content": f"Deep code review with explicit evidence:\n{diff}",
            }],
        }
        if config["thinking"]:
            kwargs["thinking"] = config["thinking"]
        if config["effort"]:
            kwargs["output_config"] = {"effort": config["effort"]}
        response = self.client.messages.create(**kwargs)
        confidence = 0.5
        trace = ReasoningTrace(
            query_id=_new_query_id(),
            classified_complexity=Complexity.COMPLEX.value,
            model_used=config["model"],
            output_tokens=_usage_output_tokens(response),
            final_confidence=confidence,
            wall_time_ms=_elapsed_ms(started),
        )
        return ReviewResult(
            verdict=first_text(response),
            complexity=Complexity.COMPLEX.value,
            confidence=confidence,
            trace=trace,
            routing_view=view,
        )

    def verify_bug(self, suspicion: str, repo_path: str) -> dict:
        tester = HypothesisTester(
            client=self.client,
            execute_fn=lambda command: run_in_sandbox(
                command,
                repo_path,
            ),
            max_iterations=5,
        )
        return tester.investigate(
            f"Verify whether this is a real bug: {suspicion}"
        )
