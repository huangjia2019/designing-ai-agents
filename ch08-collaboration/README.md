# Chapter 8 — Collaboration

Four collaboration patterns and the Argus collaboration layer: Argus stops
reviewing alone and delegates to specialist sub-agents, then reconciles
what they say.

```
ch08-collaboration/
├── argus/
│   └── collaboration.py              # Listing 8.15 — parallel review dispatch + synthesis
└── patterns/
    ├── collaboration_trace.py        # Listing 8.1 — token multiplier, handoff fidelity
    ├── handoff_chain.py              # Listings 8.2-8.3 — specialists in sequence
    ├── fan_out_gather.py             # Listings 8.4-8.7 — parallel workers, coordinated merge
    ├── adversarial_review.py         # Listings 8.8-8.10 — proponent vs reviewer, judged
    └── hierarchical_delegation.py    # Listings 8.11-8.14 — manager decomposes, workers execute
```

Carried over from earlier chapters (cumulative Argus needs them):
`action_trace.py`, `chain_of_thought.py`, `complexity_routing.py`,
`experience_replay.py`, `generator_critic.py`, `guardrail_sandwich.py`,
`hierarchical_memory.py`, `mcp_client.py`, `plan_and_execute.py`,
`prompt_chain.py`, `reflection_trace.py`, `self_heal_loop.py`,
`skill_library.py`, `tool_dispatch.py`.

The `argus/` package is the cumulative snapshot — everything from
Ch2–Ch7 plus `collaboration.py`.

## Listing → file

Listings are fragments that concatenate in listing order to form each file.

| Listing | File | Adds |
|---|---|---|
| 8.1 | `patterns/collaboration_trace.py` | `CollaborationTrace` |
| 8.2 | `patterns/handoff_chain.py` | `ChainAgent`, `HandoffContext` |
| 8.3 | `patterns/handoff_chain.py` | `HandoffChain` |
| 8.4 | `patterns/fan_out_gather.py` | `WorkerTask`, `FanOutGather.decompose` |
| 8.5 | `patterns/fan_out_gather.py` | `_execute_worker`, `fan_out` |
| 8.6 | `patterns/fan_out_gather.py` | `gather` |
| 8.7 | `patterns/fan_out_gather.py` | `execute` |
| 8.8 | `patterns/adversarial_review.py` | `DebateRound`, `DebateResult`, `AdversarialReview._call_agent` |
| 8.9 | `patterns/adversarial_review.py` | `debate` — setup and round loop |
| 8.10 | `patterns/adversarial_review.py` | judge verdict, parsed (continues inside `debate`) |
| 8.11 | `patterns/hierarchical_delegation.py` | `WorkerRole`, `Subtask`, `decompose` |
| 8.12 | `patterns/hierarchical_delegation.py` | `execute_worker` |
| 8.13 | `patterns/hierarchical_delegation.py` | `coordinate` |
| 8.14 | `patterns/hierarchical_delegation.py` | `_parse_subtasks`, `_build` |
| 8.15 | `argus/collaboration.py` | `ArgusCollaboration` |

Each file also carries a module docstring and a `__main__` demo that the
book omits for space.

## Run

```bash
python patterns/collaboration_trace.py   # pure Python, no API key needed

export ANTHROPIC_API_KEY=sk-...
python patterns/fan_out_gather.py
python patterns/adversarial_review.py
python patterns/hierarchical_delegation.py
python patterns/handoff_chain.py
```

The Ch8 pattern files follow the book and take a live `client: Anthropic`.
They lazy-import `anthropic`, so every module imports cleanly without the
SDK installed; a key is only needed when a demo actually calls the model.

`argus/collaboration.py` stays offline-safe: with no client supplied it
falls back to a stub that answers the same `messages.create(...)`
interface the patterns call, so the real `FanOutGather` and
`AdversarialReview` code paths still run without a key. Every sub-agent
(and the synthesizer, proponent, reviewer, and judge) is a pluggable
callable — pass LLM-backed ones in production:

```python
from argus import ArgusCollaboration

collab = ArgusCollaboration()          # stub sub-agents, no key needed
print(collab.parallel_review(diff))
collab.trace.log()                     # Listing 8.1 metrics
```
