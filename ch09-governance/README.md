# Chapter 9 — Governance

Four governance patterns and the Argus control plane: every action that
touches the world is classified, bounded, recorded, and — until Argus has
earned otherwise — put in front of a human.

```
ch09-governance/
├── argus/
│   └── governance.py                 # Listings 9.16-9.17 — the ArgusGovernance control plane
└── patterns/
    ├── approval_gate.py              # Listings 9.1-9.4 — classify risk, route allow/deny/ask
    ├── blast_radius.py               # Listings 9.5-9.7 — three nested containment layers
    ├── progressive_commitment.py     # Listings 9.8-9.11 — trust earned on evidence, lost on errors
    └── observability_harness.py      # Listings 9.12-9.15 — spans, metrics, dashboard, export
```

Carried over from earlier chapters (cumulative Argus needs them):
`action_trace.py`, `adversarial_review.py`, `chain_of_thought.py`,
`collaboration_trace.py`, `complexity_routing.py`, `experience_replay.py`,
`fan_out_gather.py`, `generator_critic.py`, `guardrail_sandwich.py`,
`handoff_chain.py`, `hierarchical_delegation.py`, `hierarchical_memory.py`,
`mcp_client.py`, `plan_and_execute.py`, `prompt_chain.py`,
`reflection_trace.py`, `self_heal_loop.py`, `skill_library.py`,
`tool_dispatch.py`.

The `argus/` package is the cumulative snapshot — everything from Ch2–Ch8
plus `governance.py`.

## Listing → file

Listings are fragments that concatenate in listing order to form each file.

| Listing | File | Adds |
|---|---|---|
| 9.1 | `patterns/approval_gate.py` | `RiskLevel`, `Decision`, `ToolAction`, `ApprovalRule` |
| 9.2 | `patterns/approval_gate.py` | `ApprovalGate`, `add_deny_rule`, `add_allow_rule` |
| 9.3 | `patterns/approval_gate.py` | `classify_risk`, `_matches` |
| 9.4 | `patterns/approval_gate.py` | `evaluate`, `_log` |
| 9.5 | `patterns/blast_radius.py` | `SandboxConfig` |
| 9.6 | `patterns/blast_radius.py` | `SandboxedExecutor`, `validate_path`, `check_rate_limit`, `check_budget` |
| 9.7 | `patterns/blast_radius.py` | `execute` — the layered gauntlet |
| 9.8 | `patterns/progressive_commitment.py` | `TrustLevel`, `TrustMetrics`, `EscalationThresholds` |
| 9.9 | `patterns/progressive_commitment.py` | `TrustManager`, `record_action` |
| 9.10 | `patterns/progressive_commitment.py` | `_check_escalation`, `_escalate`, `_demote` |
| 9.11 | `patterns/progressive_commitment.py` | `should_ask_human`, `get_status` |
| 9.12 | `patterns/observability_harness.py` | `Span`, `AgentObserver`, `start_trace`, `start_span` |
| 9.13 | `patterns/observability_harness.py` | `record_llm_call` |
| 9.14 | `patterns/observability_harness.py` | `record_tool_call`, `record_task_outcome` |
| 9.15 | `patterns/observability_harness.py` | `get_dashboard`, `export_traces` |
| 9.16 | `argus/governance.py` | `ArgusGovernance` — constructing the four patterns |
| 9.17 | `argus/governance.py` | `run_tool`, `finish_review` — the chokepoint |

The four pattern files are the book's code verbatim; the repo adds only
the imports and module headers the listings elide.

## The order is the design

`ArgusGovernance.run_tool()` runs the four patterns in a fixed order, and
the order carries the argument (§9.8):

```
gate.evaluate()        allow / deny / ask — cheapest check first, so a
                       deny returns before the sandbox is ever touched
trust.should_ask_human()   an 'ask' is not automatically a prompt: does
                           this risk still need a human at this level?
sandbox.execute()      whatever survives runs inside the tool allowlist,
                       path bounds, rate limit and budget cap
observer.record_*()    the call and its outcome become the evidence the
                       next decision is made on
```

## Trust levels decide what actually prompts

`run_command` classifies as HIGH risk. At the default `SUPERVISED` level a
HIGH-risk action needs a human, so with no approver the gate declines it —
that is the pattern working, not a bug. The same call runs unattended once
Argus reaches `AUTONOMOUS`, which is what makes the ladder worth climbing:

```python
from argus import review_diff, ArgusGovernance
from patterns.progressive_commitment import TrustLevel

# supply an approver...
review_diff(diff, project="x", memory=m,
            ask_human=lambda action, reason: True)

# ...or start higher up the ladder
review_diff(diff, project="x", memory=m,
            governance=ArgusGovernance(initial_trust=TrustLevel.AUTONOMOUS))
```

`review_diff` returns `gov_meta` as its sixth value: `allowed`,
`audit_entries`, `current_trust`, `promotions`, `demotions`, and the
Observability `dashboard`.

## Superseded files

`patterns/permission_gate.py`, `trust_levels.py`, `audit_log.py`,
`policy_engine.py`, `governance_trace.py` and `sandbox.py` implement an
earlier six-pattern draft of this chapter. **They are not in the book and
nothing in `argus/` imports them.** They remain only as runnable
references to a design the chapter no longer teaches; read the four files
in the table above for Ch9 as published.

## Run

```bash
python3 -c "import argus"          # cumulative Argus imports without a key
```

The four Ch9 pattern files are pure Python with no LLM dependency and no
`__main__` demo — they are libraries the control plane drives. Exercise
them through `argus/governance.py`:

```python
from argus.governance import ArgusGovernance

gov = ArgusGovernance()
gov.start_review("PR-42")
gov.run_tool("git_force_push", {}, execute_fn=lambda t, a: {})
# -> {'error': 'History rewrite is irreversible'}   (deny rule)
gov.run_tool("read_file", {"repo": "."}, execute_fn=lambda t, a: {"ok": True})
# -> {'ok': True}                                    (read_* allow rule)
print(gov.finish_review(success=True))               # dashboard
```
