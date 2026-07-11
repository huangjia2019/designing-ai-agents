# Chapter 7 — Reflection

Four reflection patterns and the Argus reflection layer: the agent
critiques its own output, heals failed fixes, and turns experience into
reusable skills.

```
ch07-reflection/
├── argus/
│   ├── reflection.py                 # Argus reflection module — §7.x checkpoint wiring
│   └── self_heal.py                  # Bounded retry with rollback after failed fixes
└── patterns/
    ├── reflection_trace.py           # Observability dataclass for reflection decisions
    ├── generator_critic.py           # Generator-Critic — propose, critique, revise
    ├── self_heal_loop.py             # Self-Heal Loop — bounded retry driven by test feedback
    ├── experience_replay.py          # Experience Replay — mine past runs for lessons
    └── skill_library.py              # Skill Library — package proven procedures for reuse
```

Carried over from earlier chapters (cumulative Argus needs them):
`action_trace.py`, `chain_of_thought.py`, `complexity_routing.py`,
`guardrail_sandwich.py`, `hierarchical_memory.py`, `mcp_client.py`,
`plan_and_execute.py`, `prompt_chain.py`, `tool_dispatch.py`.

The `argus/` package is the cumulative snapshot — everything from
Ch2–Ch6 plus `reflection.py` and `self_heal.py`.

## Run

```bash
export ANTHROPIC_API_KEY=sk-...
python patterns/generator_critic.py
python patterns/self_heal_loop.py
```

Pattern files lazy-import `anthropic`, so everything imports cleanly
without the SDK; a live key is only needed when a demo actually calls
the model.
