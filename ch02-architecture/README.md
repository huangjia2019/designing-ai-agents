# Chapter 2 — Agent Architecture

The Perception-Reasoning-Action (PRA) loop, the Runtime VM, and cross-framework skeletons.

```
ch02-architecture/
├── argus/
│   ├── core.py                      # Listing 2.4 — PRA loop in 50 lines
│   ├── runtime.py                   # Listing 2.1 — Runtime VM (illustrative)
│   └── coding_agent_simplified.py   # Listing 2.2 — single-agent coding assistant
├── patterns/
│   └── openai_guardrails.py         # Listing 2.3 — OpenAI SDK guardrails
└── demos/
    ├── openai_argus.py              # Listing 2.5 — Argus with OpenAI Agents SDK
    ├── langgraph_argus.py           # Listing 2.6 — Argus with LangGraph
    └── adk_argus.py                 # repo extra — Argus with Google ADK
```

## Run

```bash
export ANTHROPIC_API_KEY=sk-...
python argus/core.py --help   # Argus PRA loop (the main demo)

export OPENAI_API_KEY=sk-...
python demos/openai_argus.py  # Same agent, OpenAI SDK

export GOOGLE_API_KEY=...
python demos/adk_argus.py     # Same agent, Google ADK
```

## Pedagogical files

- `argus/runtime.py` — architectural sketch; references classes that are
  never defined (RuntimeConfig, Sandbox, ...). Treat as structural
  pseudocode per the book.
- `patterns/openai_guardrails.py` — the four guardrail callbacks are
  placeholder stubs; swap them for real checks in production.
- `demos/adk_argus.py` — not a book listing. It exists so the same PRA loop
  can be read in a third framework; ADK keeps the agent declarative and puts
  the loop in a Runner. Requires `pip install google-adk`.
