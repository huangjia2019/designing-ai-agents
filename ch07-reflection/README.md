# Chapter 7 — Reflection

## Revised MEAP examples: start here

Start with [`current_edition/`](current_edition/README.md) for the revised
chapter's 20 executable listings, an offline demo, and 39 regression tests.
It implements bounded Generator-Critic review and Self-Heal recovery,
evidence-backed Skill Package admission and routing, and scoped Experience
Replay. Python 3.10+ is required; no API key or extra packages are needed.

```bash
python ch07-reflection/current_edition/demo.py
python -m unittest discover -s ch07-reflection/current_edition/tests -v
```

The commands above run from the repository root. They do not modify a real
workspace or contact a model provider.

## Earlier cumulative examples (compatibility)

The `argus/` and `patterns/` modules below are retained for readers of the
earlier chapter and the cumulative Argus demo. They are not substitutes for
the current edition's listing implementations.

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
