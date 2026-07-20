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
    ├── mcp_client.py                 # Minimal MCP client used by tool dispatch
    ├── plan_and_execute.py           # Plan-and-Execute — planner/executor split with DAG replanning
    └── guardrail_sandwich.py         # Guardrail Sandwich — input/execution/output validation layers
```

Carried over from earlier chapters (cumulative Argus needs them):
`chain_of_thought.py`, `complexity_routing.py`, `hierarchical_memory.py`.

The `argus/` package is the cumulative snapshot — Ch2's core plus
perception (Ch3), memory (Ch4), reasoning (Ch5), and now `action.py`.

## Run

```bash
export ANTHROPIC_API_KEY=sk-...
python patterns/prompt_chain.py
python patterns/tool_dispatch.py
```

Pattern files lazy-import `anthropic`, so everything imports cleanly
without the SDK; a live key is only needed when a demo actually calls
the model.
