# Chapter 8 — Collaboration

## Current MEAP examples

The September 2026 chapter's seven listings are implemented under
[`current_edition/`](current_edition/). A subagent receives a fresh
context and selected tools. Separate contexts can still share versioned
artifacts, a claim board and task receipts.

Use Python 3.10 or newer. The examples and tests need no API key, model
SDK or network access:

```bash
cd ch08-collaboration
python3 -m current_edition.demo
python3 -m unittest discover -s current_edition/tests -v
```

The demo preserves three specialist reports, lets the writer and security
reviewer exchange evidence, and returns a packet requiring a human
decision. It uses a scripted adapter, not a live model or a performance
benchmark. A cleared claim board does not authorize merging the change.

## Current listing map

Paths below are relative to `current_edition/`.

| Listing | Executable file | Responsibility |
|---|---|---|
| 8.1 | `patterns/collaboration_runtime.py` | Fresh context, selected tools and a shared versioned workspace |
| 8.2 | `patterns/handoff_chain.py` | Typed handoff, receiver checks and return to the owner |
| 8.3 | `patterns/fan_out_gather.py` | Independent branches; lead-driven repeated fan-out |
| 8.4 | `patterns/adversarial_review.py` | Writer/reviewer claims and a human review packet |
| 8.5 | `patterns/hierarchical_delegation.py` | Manager-owned delegation and task dependencies |
| 8.6 | `patterns/collaboration_trace.py` | Same-task baseline averages and observed comparison ratios |
| 8.7 | `argus/collaboration.py` | Three specialist reports plus selected-claim review |

The executable runtime supplies workspace record types and helper methods
omitted from the printed excerpts. It also verifies that a handoff's named
receiver matches the actual receiver before spawning it. This additional
identity check is tested alongside the chapter's artifact, evidence and
acceptance checks.

`AgentRuntime` is the integration seam for a real model's tool-calling
loop. `demo_runtime.py` provides the deterministic implementation used
by the offline examples. The in-memory workspace is not a production
permission system, durable database or cross-process transaction manager;
the host must supply those controls.

## What the tests establish

- Average baseline tokens, latency and quality, not a single convenient run.
- Return of incomplete or misaddressed handoffs to their owner.
- Fresh agent contexts with a common workspace.
- Result-driven follow-up fan-out and rejection of dependent branches.
- Writer/reviewer separation with a human decision at the end.
- Manager-owned dependent work.
- Retention of specialist artifacts and rejection of a partial worker set.

The scripted tests exercise these contracts. They do not establish live
model quality, benchmark speedup or production security.

## Earlier-edition compatibility

The top-level `argus/`, `patterns/` and `demos/` support the cumulative
coding-agent examples. They are not the current chapter's listing entry
points; start from `current_edition/` when following the MEAP.
