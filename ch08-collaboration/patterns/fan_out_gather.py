"""Fan-Out/Gather — parallel sub-agents, single synthesizer.

A lead agent dispatches the same task (or N parallel sub-tasks) to N
specialized agents in parallel. Each works on bounded context. Lead
collects all responses and synthesizes a final answer.

Used in Argus to: dispatch security review, style review, and complexity
review in parallel, then synthesize a final verdict.
"""
from dataclasses import dataclass, field
from typing import Callable
import concurrent.futures


@dataclass
class SubAgent:
    name: str
    role: str  # 'security', 'style', 'complexity', ...
    invoke: Callable[[str], str]


def fan_out_gather(subagents: list[SubAgent], task: str,
                   max_workers: int = 4) -> dict[str, str]:
    """Run all sub-agents in parallel, return name -> response dict."""
    results: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(s.invoke, task): s.name for s in subagents}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                results[name] = f"[error: {type(e).__name__}: {e}]"
    return results


def synthesize(lead_invoke: Callable[[str], str],
               task: str, sub_results: dict[str, str]) -> str:
    """Lead agent receives all sub-results and produces a final answer."""
    parts = ["# Sub-agent findings:"]
    for name, resp in sub_results.items():
        parts.append(f"## {name}\n{resp}")
    parts.append(f"\n# Lead synthesis task:\n{task}")
    return lead_invoke("\n\n".join(parts))
