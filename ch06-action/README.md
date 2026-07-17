# Chapter 6 — Action

Four action patterns and the Argus action layer: how an agent's decisions
become tool calls, plans, and guarded side effects.

```
ch06-action/
├── argus/
│   └── action.py                     # Argus action layer — wires the five §6.8 checkpoint capabilities
└── patterns/
    ├── action_trace.py               # Observability dataclass for every tool call
    ├── prompt_chain.py               # Prompt Chaining — pipeline steps with quality gates
    ├── tool_dispatch.py              # Tool Dispatch — capability bus + semantic routing
    ├── mcp_client.py                 # MCP tool discovery over the real mcp SDK
    ├── plan_and_execute.py           # Plan-and-Execute — planner/executor split with DAG replanning
    └── guardrail_sandwich.py         # Guardrail Sandwich — input/execution/output validation layers
```

## Listing map

| Listing | File | Contents |
|---|---|---|
| 6.1 | `patterns/action_trace.py` | `ActionTrace` + `log()` |
| 6.2 | `patterns/prompt_chain.py` | `StepResult`, `PipelineStep` |
| 6.3 | `patterns/prompt_chain.py` | `PromptChain` (`add_step`, `run`) |
| 6.4 | `patterns/tool_dispatch.py` | `ToolDefinition`, `ToolResult`, `ToolDispatcher.select_tools` |
| 6.5 | `patterns/tool_dispatch.py` | `ToolDispatcher.execute`, `_repair_args` |
| 6.5b | `patterns/tool_dispatch.py` | `Tool`, `Toolbox` — the registry without the routing |
| 6.6 | `patterns/mcp_client.py` | `connect_mcp_server` — MCP tool discovery |
| 6.7 | `patterns/plan_and_execute.py` | `TaskStatus`, `Task`, `Plan.ready_tasks` |
| 6.8 | `patterns/plan_and_execute.py` | `PlanAndExecuteAgent.create_plan`, `execute_task` |
| 6.9 | `patterns/plan_and_execute.py` | `PlanAndExecuteAgent.run` |
| 6.10 | `patterns/guardrail_sandwich.py` | `RiskLevel`, `SafetyPolicy` |
| 6.11 | `patterns/guardrail_sandwich.py` | `GuardrailSandwich.execute_safely` |
| 6.12 | `patterns/guardrail_sandwich.py` | `_classify_risk`, `_filter_output` |
| 6.12b | `argus/action.py` | `_run_lint`, `_run_tests`, `_apply_fix`, `default_policy` |
| 6.13 | `argus/action.py` | `ArgusAction.__init__` — the facade |
| 6.13b | `argus/action.py` | `call_tool`, `_trace`, and the three named actions |

Listings that share a file concatenate in listing-number order. Two helpers
the chapter calls but never prints are implemented alongside them and marked
in the source: `_filter_input` (called by Listing 6.11) and `_parse_plan`
(called by Listing 6.8).

**Listing 6.13 reconciled (2026-07-17).** Earlier printings of 6.13 called a
`GuardrailSandwich` API that Listing 6.11 does not define
(`human_approver=`, `execute_safely(action_name=, tool=, fn=, **kwargs) ->
ActionTrace`). The book now prints this file's real API against 6.11's
`human_fn=` / `execute_safely(tool_name, arguments, executor) -> dict`, with
`_trace` adapting the verdict dict into an `ActionTrace`. No divergence
remains. Everything 6.12b/6.13/6.13b print is defined in the book: `Tool` and
`Toolbox` in 6.5b, `ActionTrace`'s payload fields in 6.1, and
`SafetyPolicy.require_human_tools` in 6.10.

**Known gap, inherited from Listing 6.11.** On the approved-and-executed
path, `execute_safely` returns only `{executed, risk_level, output}`, so
`human_decision` does not reach the trace: an approved action records that it
succeeded but not that a human waved it through. Declined actions keep the
field, because 6.11 spreads `**verdict` on the blocked path. Closing this
means changing 6.11's success return shape, which is a book change, not a
repo one.

Carried over from earlier chapters (cumulative Argus needs them):
`chain_of_thought.py`, `complexity_routing.py`, `hierarchical_memory.py`.

The `argus/` package is the cumulative snapshot — Ch2's core plus
perception (Ch3), memory (Ch4), reasoning (Ch5), and now `action.py`.

## Run

```bash
export ANTHROPIC_API_KEY=sk-...
python -m argus.cli --diff-file some.diff --project demo
```

The pattern modules guard their `anthropic` import, and `mcp_client.py` guards
its `mcp` import the same way, so everything imports cleanly without either
SDK; a live key is only needed when a pattern actually calls the model, and
`connect_mcp_server` opens no connection until it is awaited. `ArgusAction`
runs without a key — its tools are `ruff`, `pytest`, and a file edit, all
gated by the sandwich.

Listing 6.6 needs the MCP SDK, which is not in `requirements.txt`:

```bash
pip install mcp        # only for Listing 6.6
```
