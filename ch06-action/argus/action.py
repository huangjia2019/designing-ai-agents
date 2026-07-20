# argus/action.py — Argus action layer, Ch6 snapshot.
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
import subprocess
from dataclasses import dataclass, field

from patterns.tool_dispatch import Toolbox, Tool, dispatch
from patterns.action_trace import ActionTrace
from patterns.guardrail_sandwich import GuardrailSandwich, SafetyPolicy


def _run_lint(repo_root: str = ".") -> dict:
    """Run the project's lint command. Wrapper for tool dispatch."""
    try:
        r = subprocess.run(
            ["ruff", "check", repo_root],
            capture_output=True, text=True, timeout=60,
        )
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except FileNotFoundError:
        return {"returncode": -1, "stdout": "", "stderr": "ruff not installed"}


def _run_tests(repo_root: str = ".") -> dict:
    """Run pytest. Wrapper for tool dispatch."""
    try:
        r = subprocess.run(
            ["pytest", repo_root, "-x", "--tb=short"],
            capture_output=True, text=True, timeout=300,
        )
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except FileNotFoundError:
        return {"returncode": -1, "stdout": "", "stderr": "pytest not installed"}


def _apply_fix(file_path: str, old: str, new: str) -> dict:
    """Apply a one-spot edit. Wrapper for tool dispatch (irreversible — gated)."""
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        return {"applied": False, "reason": f"file not found: {file_path}"}
    text = p.read_text()
    if old not in text:
        return {"applied": False, "reason": "old text not found"}
    p.write_text(text.replace(old, new, 1))
    return {"applied": True, "file": file_path}


def default_policy() -> SafetyPolicy:
    """The Ch6 demo policy: lint + test free; fix_apply needs human."""
    return SafetyPolicy(
        allowed_tools={"lint", "test", "fix_apply"},
        forbidden_path_prefixes=["/etc", "/usr", "~/.ssh"],
        require_human_for={"fix_apply"},
        max_output_bytes=100_000,
    )


class ArgusAction:
    """Argus's hands: dispatch tools through the guardrail sandwich, trace every call."""

    def __init__(self, policy: SafetyPolicy | None = None,
                 human_approver=None):
        self.policy = policy or default_policy()
        self.sandwich = GuardrailSandwich(self.policy, human_approver=human_approver)
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

    def call_tool(self, tool_name: str, **kwargs) -> ActionTrace:
        """Side-effecting tool invocation, guardrail-wrapped and traced."""
        tool = self.toolbox.get(tool_name)
        trace = self.sandwich.execute_safely(
            action_name=tool_name,
            tool=tool_name,
            fn=tool.fn,
            **kwargs,
        )
        self.action_log.append(trace)
        return trace

    def run_lint(self, repo_root: str = ".") -> ActionTrace:
        return self.call_tool("lint", repo_root=repo_root)

    def run_tests(self, repo_root: str = ".") -> ActionTrace:
        return self.call_tool("test", repo_root=repo_root)

    def apply_fix(self, file_path: str, old: str, new: str) -> ActionTrace:
        return self.call_tool("fix_apply", file_path=file_path, old=old, new=new)
