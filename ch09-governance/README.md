# Chapter 9 — Governance

**Start with `current_edition/` for the current chapter listings.** It contains
the four governance patterns and their `ArgusGovernance` composition, including
approval packets, protected evidence references, and task-budget handling.
Use Python 3.10 or newer; these modules need no API key or third-party package.

The existing `argus/` and `patterns/` directories remain the older cumulative
snapshot so earlier examples keep working. They are **not** the current
chapter implementation. In particular, the current approval callback takes
one review packet and returns a reviewer identifier; the older facade takes
`(action, reason)` and expects a Boolean. Do not mix these contracts.

## Run the current examples

From this directory:

```bash
python3 -m current_edition.demo
python3 -m unittest discover -s tests -v
```

The demo records a denied action, an allowed read, and an action requiring
human review. Its executor is an offline stub: it does not run a shell command,
change a repository, send a message, or call a provider.

From the repository root, run the tests with:

```bash
python3 -m unittest discover -s ch09-governance/tests -v
```

## Listing → executable module

The chapter uses logical paths such as `patterns/approval_gate.py` and
`argus/governance.py`. Their executable implementations are under
`current_edition/`. Listings concatenate in order within each module; ordinary
assembly imports are added to the governance facade.

| Listing | Current executable file | Adds |
|---|---|---|
| 9.1 | `current_edition/approval_gate.py` | Risk levels, decisions, action and rule records |
| 9.2 | `current_edition/approval_gate.py` | Rule registration and audit storage |
| 9.3 | `current_edition/approval_gate.py` | Risk classification and tool-name matching |
| 9.4 | `current_edition/approval_gate.py` | Deny/allow/ask routing and copied audit arguments |
| 9.5 | `current_edition/blast_radius.py` | Policy and runtime configuration |
| 9.6 | `current_edition/blast_radius.py` | Resolved paths, rolling rate checks, finite USD budget checks |
| 9.7 | `current_edition/blast_radius.py` | Policy checks before invoking a supplied executor |
| 9.8 | `current_edition/progressive_commitment.py` | Trust levels, metrics, and thresholds |
| 9.9 | `current_edition/progressive_commitment.py` | Recording outcomes and overrides |
| 9.10 | `current_edition/progressive_commitment.py` | Promotion, demotion, and evidence reset |
| 9.11 | `current_edition/progressive_commitment.py` | Risk-sensitive human review and trust status |
| 9.12 | `current_edition/observability_harness.py` | Spans and an explicit task lifecycle |
| 9.13 | `current_edition/observability_harness.py` | Model-call metrics and message/output evidence references |
| 9.14 | `current_edition/observability_harness.py` | Decision, tool, and task-outcome records |
| 9.15 | `current_edition/observability_harness.py` | Dashboard summaries and teaching JSON export |
| 9.16 | `current_edition/governance.py` | Composing the patterns and opening a scoped review |
| 9.17 | `current_edition/governance.py` | Approval packets, checked execution, outcomes, and review completion |

## The decision path

`ArgusGovernance.run_tool()` first records the gate's allow/deny/ask decision.
An explicit deny stops execution at every trust level. An ask either requires
a human or is explicitly recorded as waived under the current trust level;
critical external effects always require human review. The remaining proposal
passes through the policy envelope before the executor is called.

For a human-review path, the host provides five context fields:

```python
from current_edition import ArgusGovernance

gov = ArgusGovernance()
gov.start_review("PR-42")

result = gov.run_tool(
    "run_command",
    {"command": "run focused regression checks"},
    execute_fn=lambda tool, args: {"ok": True, "mode": "stub"},
    ask_human=lambda packet: "reviewer-42",
    review_context={
        "objective": "Verify the proposed change",
        "target": "repository/example",
        "change": "Run the focused test suite",
        "evidence_ref": "evidence:approval-packet-42",
        "policy_version": "policy-1",
    },
)
dashboard = gov.finish_review(success="error" not in result)
```

The host retains the exact proposal and supporting records in a protected
evidence store before review. `evidence_ref` identifies that retained packet.
A real approval adapter displays the packet and authenticates the person
returning the reviewer ID. The lambda above only demonstrates the interface.
A Boolean or blank identifier is rejected; the string check is not an
authentication mechanism.

The proposal and packet are copied so changes to the caller's arguments or
the displayed packet cannot silently change the arguments that execute.
General observation traces carry evidence references and selected metadata,
not the proposal's raw arguments. The gate's local `audit_log` does retain
arguments and must be treated as protected evidence.

`start_review()` resets the monetary estimate for the new task while retaining
the rolling action-rate history. Finish the current review before opening
the next one. The flat observer is a teaching implementation, not a concurrent
trace service.

## What the regression tests cover

The native tests exercise deny precedence; critical-risk review at every
trust level; input and audit snapshots; refusal of incomplete approval
packets and invalid reviewer IDs; explicit waived approvals; path and symlink
boundaries; tool allowlists; invalid and cumulative cost estimates; rate
windows; trust promotion/demotion; evidence references; and per-task counters.

All executor callbacks are stubs. Passing these tests does not certify an
operating-system sandbox or provider integration.

## Production boundaries

- Tool-name matching illustrates routing. A shell adapter must inspect
  normalized arguments, resolved paths, redirections, and the execution
  environment; a permissive name does not establish a safe command.
- `SandboxedExecutor` checks a host-side policy envelope. Its supplied runtime
  must enforce filesystem and network isolation, execution time, and memory
  limits. Merely setting the configuration fields does not implement those
  controls or prevent filesystem race conditions.
- Rate and cost counters are local to one object. Production enforcement
  requires shared, atomic state, trusted estimates, and settlement against
  actual charges.
- The task-history spending example in the chapter requires an additional
  authoritative ledger rule with atomic check-and-reserve. The generic
  tool-name gate does not implement that business policy.
- Trust evidence must remain scoped to the relevant identity, task family,
  tools, and environment. A logged scope string is not a persistence or
  access-control implementation.
- Store message sequences, model outputs, source records, and approval
  packets with appropriate redaction, retention, and access controls.
  `AgentObserver.export_traces()` emits teaching JSON, not OTLP.

## Earlier cumulative snapshot

`argus/` and `patterns/` support the cumulative coding-agent demo. For the
current chapter listings, import from `current_edition` as shown above.
