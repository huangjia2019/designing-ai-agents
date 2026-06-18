"""Sandbox — bounded execution environment for tool calls.

Production sandboxes: containers (Docker), VMs (Firecracker, Manus), or
language-level (Pyodide, Deno). This module exposes the SHAPE: timeout,
filesystem root jail, network policy. Plug a real backend in deployment.
"""
import os, signal, subprocess
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SandboxConfig:
    timeout_sec: int = 30
    fs_root: str = "."
    network_allowed: bool = False
    env_passthrough: list[str] = field(default_factory=lambda: ["PATH", "HOME"])


class Sandbox:
    """Minimal subprocess-based sandbox. Production: swap for container runtime."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()

    def run(self, command: list[str], stdin: str = "") -> dict:
        """Run a command with timeout + jailed cwd + minimal env."""
        env = {k: os.environ.get(k, "") for k in self.config.env_passthrough}
        try:
            r = subprocess.run(
                command,
                cwd=self.config.fs_root,
                env=env,
                input=stdin,
                capture_output=True, text=True,
                timeout=self.config.timeout_sec,
            )
            return {
                "returncode": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "",
                    "timed_out": True}
