# Designing AI Agents — Source Code

<a href="https://hubs.la/Q04hCsH10">
  <img src="./docs/manning-book-card.png" alt="Designing AI Agents — Manning" width="480">
</a>

**[*Designing AI Agents*](https://hubs.la/Q04hCsH10)** — the design-pattern catalogue for production AI agents. (Manning)

This repository is the official source code for the book. It contains two
tracks living side by side inside each chapter:

- **`argus/`** — Argus, the running-example PR-review agent, evolves
  **cumulatively** from Ch2 to Ch10. Each chapter adds **one cognitive
  module** and ships a self-contained snapshot that imports as
  `from argus import ...` so the reader runs the chapter's Argus directly:
  `python -m argus.cli <diff> --project <name>`.
- **`patterns/`** — independent pattern demos for everything the chapter
  introduces. Not every pattern integrates into Argus (Willem Jiang's Ch6/Ch7
  feedback). Those patterns live here as runnable references.

中文版：[README.zh-CN.md](README.zh-CN.md)

> Need a separate **pattern-only catalog organized by the two-axis matrix
> instead of by chapter?** See
> [**huangjia2019/agent-design-patterns**](https://github.com/huangjia2019/agent-design-patterns)
> (ADPS asset, not part of the book).

---

## Argus evolution at a glance

| Chapter | Argus += | Module added | What you can run |
|---------|----------|--------------|------------------|
| Ch2 architecture     | single-pass PRA loop                | `argus/core.py`           | (seed; one LLM call) |
| Ch3 perception       | + gather & triage code context      | `argus/perception.py`     | `python -m argus.cli <diff>` |
| Ch4 memory           | + cross-session memory (RAG)        | `argus/memory.py`         | `... --project myapp` |
| Ch5 reasoning        | + complexity-routed CoT             | `argus/reasoning.py`      | tier=simple/moderate/complex |
| Ch6 action           | + tool dispatch + Guardrail Sandwich | `argus/action.py`         | lint / test / fix_apply |
| Ch7 reflection       | + critic loop + skill library + experience | `argus/reflection.py` + `argus/self_heal.py` | refined verdict, fewer false positives |
| Ch8 collaboration    | + parallel sub-agents (security/style/complexity) | `argus/collaboration.py` | fan-out + synthesis |
| Ch9 governance       | + permission gate + audit log + trust | `argus/governance.py`    | tamper-evident audit chain |
| Ch10 capstone        | composition — orchestrator wires all 7 modules | `argus/orchestrator.py` | full review with every trace |

Each chapter's `argus/` directory is a **self-contained snapshot**: it
carries forward the previous chapter's modules so you can `cd ch07-reflection`
and `python -m argus.cli` without needing chapters 2-6 on the path. This
trades some duplication for pedagogical clarity.

---

## Quick start

```bash
# Run the capstone Argus on a real diff (offline-safe, no API key needed):
cd ch10-methodology
python3 demos/demo_end_to_end_review.py

# Token-waste story (Ch5): 81% savings from complexity routing
python3 demos/demo_token_waste_story.py

# Scope-creep story (Ch6): Guardrail Sandwich blocks 2/3 over-scoped fixes
python3 demos/demo_scope_creep_story.py

# Critic-loop story (Ch7): Argus PR #4287 — generator-critic 5→3 issues
python3 demos/demo_critic_loop_story.py
```

For real LLM responses, set `ANTHROPIC_API_KEY` and the demos transparently
switch from the offline shim to live Sonnet calls.

---

## Layout

```
designing-ai-agents/
├── ch01-paradigm-shift/     Ch1 — conceptual contrast (no API)
├── ch02-architecture/       Ch2 — Argus seed: 38-line PRA loop, cross-framework demos
├── ch03-perception/         Ch3 — Argus += eyes (perception triage under budget)
├── ch04-memory/             Ch4 — Argus += past (RAG over project history)
├── ch05-reasoning/          Ch5 — Argus += calibrated thinking (complexity routing)
├── ch06-action/             Ch6 — Argus += hands (tools through Guardrail Sandwich)
├── ch07-reflection/         Ch7 — Argus += self-improvement (critic + skills + replay)
├── ch08-collaboration/      Ch8 — Argus += parallel specialists (security/style/complexity)
├── ch09-governance/         Ch9 — Argus += trust accounting + audit chain
├── ch10-methodology/        Ch10 — capstone: orchestrator + 4 end-to-end demos
├── tools/smoke_test.py      Smoke test runner (import-clean across all chapters)
└── docs/                    Book card + blueprint + design notes
```

Inside every `chNN-*/`:

```
argus/        cumulative Argus snapshot for this chapter
patterns/     independent pattern demos (the rest of the chapter's listings)
demos/        optional cross-framework / story-driven scripts (Ch2, Ch10)
```

---

## Requirements

```bash
pip install -r requirements.txt
```

`anthropic` is the only hard dependency to run the cli/demos against a
live model. `patterns/hierarchical_memory.py` expects a `vector_db` argument
with `.search(query, top_k)` and `.upsert(text, metadata)` methods — the
demos ship a tiny `_Stub` so they run offline; in production swap with
`chromadb` / `qdrant` / `faiss`.

---

## Design principles in this repo

1. **Cumulative Argus**: each chapter's `argus/core.py` builds on the prior
   chapter. Reading `ch10/argus/orchestrator.py` you see the §10.10 promise
   "every method call maps to a working class from Ch3-Ch9" — cashed.
2. **Two tracks per chapter**: `argus/` (composition into Argus) and
   `patterns/` (independent demos). Not every pattern integrates into the
   coding-agent storyline — that's by design (Willem Jiang's feedback).
3. **Offline-safe**: every demo runs without an API key by falling back
   to deterministic shims; set `ANTHROPIC_API_KEY` to switch to live.
4. **Observable**: every cognitive module emits a `Trace` dataclass.
   Ch10's `OrchestrationResult` aggregates them — perception trace,
   action log, reflection meta, collaboration meta, governance meta.

See [`docs/BLUEPRINT-2026-06-17.md`](docs/BLUEPRINT-2026-06-17.md) for the
full design rationale and the Ch1→Ch10 evolution plan.
