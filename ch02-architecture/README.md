# Chapter 2 — Agent Architecture

The Perception-Reasoning-Action (PRA) loop, the Runtime VM, and cross-framework skeletons.

```
ch02-architecture/
├── argus/
│   ├── core.py                      # Listing 2.1 — one PRA pass
│   ├── runtime.py                   # repo extra — Runtime VM sketch
│   └── coding_agent_simplified.py   # repo extra — coding-assistant sketch
├── patterns/
│   └── openai_guardrails.py         # repo extra — SDK guardrail sketch
└── demos/
    ├── openai_argus.py              # Listing 2.2 — OpenAI Agents SDK
    ├── langgraph_argus.py           # Listing 2.3 — LangGraph skeleton
    └── adk_argus.py                 # repo extra — Argus with Google ADK
```

## Run

Run these commands from `ch02-architecture/`. The main example uses
`claude-sonnet-4-6`, matching the current chapter. Live examples require the
corresponding SDK and provider credentials; they incur normal API usage.

```bash
export ANTHROPIC_API_KEY=sk-...
python -m argus.core         # Argus PRA loop (the main demo)

export OPENAI_API_KEY=sk-...
python demos/openai_argus.py  # Same agent, OpenAI SDK

export GOOGLE_API_KEY=...
export GOOGLE_GENAI_USE_VERTEXAI=FALSE
python demos/adk_argus.py     # Same agent, Google ADK
```

The OpenAI example reads a `sample.diff` file from the working directory;
supply the diff you want to review. The LangGraph listing is a framework
skeleton: the host must supply `llm` before invoking the compiled graph.

The small delivery test only parses and imports local code and checks the
printed interface and model identifier. It makes no live API call:

```bash
python -m unittest discover -s tests -v
```

## Pedagogical files

- `argus/runtime.py` — architectural sketch; references classes that are
  never defined (RuntimeConfig, Sandbox, ...). Treat as structural
  pseudocode per the book.
- `patterns/openai_guardrails.py` — the four guardrail callbacks are
  placeholder stubs; swap them for real checks in production.
- `demos/adk_argus.py` — not a book listing. It exists so the same PRA loop
  can be read in a third framework; ADK keeps the agent declarative and puts
  the loop in a Runner. It is live-only and requires `pip install google-adk`,
  `GOOGLE_API_KEY`, and `GOOGLE_GENAI_USE_VERTEXAI=FALSE`.
