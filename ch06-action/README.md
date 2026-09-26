# Chapter 6 — Action

## Current MEAP examples

Chapter 6 teaches action as a bounded, verifiable state change. Its sixteen
listings are assembled in
[`current_edition/action.py`](current_edition/action.py), in book order.
The shared contract and evidence types stay in one module so readers can
run the complete examples without resolving cross-listing imports.

Use Python 3.10 or newer. No third-party package, model key, or payment
provider is needed for these examples:

```bash
cd ch06-action
python3 -m current_edition.demo
python3 -m unittest discover -s current_edition/tests -v
```

The offline payroll demo prints an accepted first attempt, an unknown
repeat requiring verification, and a rejected changed amount. The
simulated provider is called exactly once. No money moves. An unknown
result is not permission to retry a write blindly.

The test suite also checks unapproved amounts, cross-entity and stale
arguments, commit identity, guarded outcomes, plan dependencies,
checkpoint round-trips and bounded replanning.

## Current listing map

All entries below refer to `current_edition/action.py`; each listing has
a numbered comment marking its start.

| Listing | Mechanism |
|---|---|
| 6.1 | `ActionContract`, `ActionAttempt` |
| 6.2 | `Artifact`, `GateResult`, `ChainStep` |
| 6.3 | `run_chain`: stop rejected artifacts from propagating |
| 6.4 | `verified_patch_gate`: bind evidence to the patch |
| 6.5 | `TrustedValue`, `ToolSpec`, `DispatchContext`, `ToolIntent` |
| 6.6 | `ToolRegistry`: eligible capability surface |
| 6.7 | `CommitStore`, argument binding, request digest and admission |
| 6.8 | `dispatch`: one executable entry point |
| 6.9 | Versioned plan, step and evidence records |
| 6.10 | Plan validation, ready work and accepting a completed step |
| 6.11 | Atomic local checkpoint and reload |
| 6.12 | Bounded local replan |
| 6.13 | Guarded runner and execution contracts |
| 6.14 | `run_guarded`: preconditions, execution and postconditions |
| 6.15 | Payroll receipt evidence and pre/postcondition checks |
| 6.16 | `ArgusAction`: registered guards around admitted calls |

Host applications still supply trusted state, runners, independent
verifiers and production storage. The in-memory commit store demonstrates
the admission contract; it is not a distributed transaction coordinator.
A local checkpoint does not roll back a remote side effect. The examples
do not provide operating-system isolation or a real payment integration.

## Earlier-edition compatibility

The existing `argus/` and `patterns/` directories support the cumulative
coding-agent demo; they are **not the listing map for the current chapter**.
In particular, the no-argument `argus.action.ArgusAction` and
`current_edition.action.ArgusAction(registry, guarded, commits)`
are different interfaces.

The earlier cumulative CLI remains available:

```bash
python3 -m argus.cli --diff-file some.diff --project demo
```

That CLI's live model path needs `ANTHROPIC_API_KEY` and its
dependencies. Its optional MCP example requires the MCP SDK. None of
those dependencies is needed for `current_edition`.
