# argus/action.py — Argus action layer, Ch6 snapshot. Book: Listing 6.13.
#
# Tracks §6.8 'Argus checkpoint' which promises this module wires five
# capabilities into Argus:
#   1. Run linter via tool dispatch
#   2. Run tests via prompt chain
#   3. Apply fixes via plan-and-execute
#   4. Safety gates on destructive operations (Guardrail Sandwich)
#   5. ActionTrace for every action taken
#
# This module is the facade. It does not re-implement the patterns — they
# live in patterns/. Argus composes them.
#
# LISTING MAP (reconciled 2026-07-17)
# -----------------------------------
# This file is printed by three listings, in file order:
#
#   Listing 6.12b  _run_lint, _run_tests, _apply_fix, default_policy
#   Listing 6.13   ArgusAction.__init__
#   Listing 6.13b  call_tool, _trace, run_lint, run_tests, apply_fix
#
# Earlier printings of 6.13 called a GuardrailSandwich API that Listing 6.11
# does not define — GuardrailSandwich(policy, human_approver=...) and
# .execute_safely(action_name=, tool=, fn=, **kwargs) -> ActionTrace, versus
# 6.11's GuardrailSandwich(policy, human_fn=None) and
# .execute_safely(tool_name, arguments, executor) -> dict. The two could not
# both be true of one class. The book now prints this file's real API: the
# sandwich follows Listing 6.11, and _trace adapts its verdict dict into the
# ActionTrace of Listing 6.1. No divergence remains between 6.12b/6.13/6.13b
# and the code below.
#
# Known gap, inherited from Listing 6.11 and NOT introduced here: on the
# approved-and-executed path, execute_safely returns only
# {executed, risk_level, output}, so human_decision does not survive into the
# trace. An approved action records success but not who approved it. A
# declined action keeps the field, because 6.11 spreads **verdict on the
# blocked path. Fixing this means changing 6.11's success return shape.
import subprocess
import time
from pathlib import Path

from patterns.tool_dispatch import Toolbox, Tool
from patterns.action_trace import ActionTrace
from patterns.guardrail_sandwich import (
    GuardrailSandwich, SafetyPolicy, RiskLevel,
)


def _run_lint(repo_root: str = ".") -> str:
    """Run the project's lint command. Wrapper for tool dispatch.

    Returns text: Layer 3 of the sandwich redacts sensitive patterns out of
    tool output, and redaction operates on text.
    """
    try:
        r = subprocess.run(
            ["ruff", "check", repo_root],
            capture_output=True, text=True, timeout=60,
        )
        return f"returncode={r.returncode}\n{r.stdout}{r.stderr}".strip()
    except FileNotFoundError:
        return "returncode=-1\nruff not installed"


def _run_tests(repo_root: str = ".") -> str:
    """Run pytest. Wrapper for tool dispatch."""
    try:
        r = subprocess.run(
            ["pytest", repo_root, "-x", "--tb=short"],
            capture_output=True, text=True, timeout=300,
        )
        return f"returncode={r.returncode}\n{r.stdout}{r.stderr}".strip()
    except FileNotFoundError:
        return "returncode=-1\npytest not installed"


def _apply_fix(file_path: str, old: str, new: str) -> str:
    """Apply a one-spot edit. Wrapper for tool dispatch (irreversible — gated)."""
    p = Path(file_path)
    if not p.exists():
        return f"not applied: file not found: {file_path}"
    text = p.read_text()
    if old not in text:
        return "not applied: old text not found"
    p.write_text(text.replace(old, new, 1))
    return f"applied: {file_path}"


def default_policy() -> SafetyPolicy:
    """The Ch6 demo policy: lint + test free; fix_apply needs human."""
    return SafetyPolicy(
        allowed_tools=["lint", "test", "fix_apply"],
        blocked_patterns=[r"/etc/", r"/usr/", r"\.ssh/"],
        auto_approve=[RiskLevel.LOW, RiskLevel.MEDIUM],
        require_human=[RiskLevel.HIGH, RiskLevel.CRITICAL],
        require_human_tools=["fix_apply"],
    )


class ArgusAction:
    """Argus's hands: dispatch tools through the guardrail sandwich, trace every call."""

    def __init__(self, policy: SafetyPolicy | None = None,
                 human_approver=None):
        self.policy = policy or default_policy()
        self.sandwich = GuardrailSandwich(
            self.policy, human_fn=human_approver,
        )
        self.toolbox = Toolbox([
            Tool(name="lint",
                 description="Run project linter and return stdout/stderr.",
                 fn=_run_lint),
            Tool(name="test",
                 description="Run project test suite and return result.",
                 fn=_run_tests),
            Tool(name="fix_apply",
                 description="Apply a one-spot text replacement to a file. IRREVERSIBLE.",
                 fn=_apply_fix),
        ])
        self.action_log: list[ActionTrace] = []
        self._seq = 0

    def call_tool(self, tool_name: str, **kwargs) -> ActionTrace:
        """Side-effecting tool invocation, guardrail-wrapped and traced.

        Single chokepoint — no bypass around the sandwich.
        """
        tool = self.toolbox.get(tool_name)
        t0 = time.perf_counter()
        verdict = self.sandwich.execute_safely(
            tool_name=tool_name,
            arguments=kwargs,
            executor=lambda name, args: tool.fn(**args),
        )
        wall_ms = int((time.perf_counter() - t0) * 1000)
        trace = self._trace(tool_name, kwargs, verdict, wall_ms)
        self.action_log.append(trace)
        return trace

    def _trace(self, tool_name: str, arguments: dict,
               verdict: dict, wall_ms: int) -> ActionTrace:
        """Turn the sandwich's verdict dict into the audit log's ActionTrace."""
        self._seq += 1
        executed = bool(verdict.get("executed"))
        gated = verdict.get("blocked_by") == "input_filter"
        decision = verdict.get("human_decision")
        return ActionTrace(
            action_id=f"a{self._seq}",
            tool_name=tool_name,
            risk_level=verdict.get("risk_level", RiskLevel.LOW.value),
            guardrail_blocked=gated,
            guardrail_reason=verdict.get("reason", "") if gated else "",
            awaiting_human_approval=False,  # resolved synchronously here
            human_decision=decision,
            success=executed,
            wall_time_ms=wall_ms,
            arguments=dict(arguments),
            output=verdict.get("output"),
            error=verdict.get("error"),
        )

    def run_lint(self, repo_root: str = ".") -> ActionTrace:
        return self.call_tool("lint", repo_root=repo_root)

    def run_tests(self, repo_root: str = ".") -> ActionTrace:
        return self.call_tool("test", repo_root=repo_root)

    def apply_fix(self, file_path: str, old: str, new: str) -> ActionTrace:
        return self.call_tool("fix_apply", file_path=file_path, old=old, new=new)
