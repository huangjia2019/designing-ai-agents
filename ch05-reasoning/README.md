# Chapter 5 — Reasoning

Four reasoning patterns and observability for the reasoning step.

```
ch05-reasoning/
├── argus/
│   └── reasoning.py                  # Listings 5.2b, 5.3b, 5.5c — conceptual
└── patterns/
    ├── reasoning_trace.py            # Listing 5.1 — observability dataclass
    ├── chain_of_thought.py           # Listing 5.2 — CoT + weak-link verification
    ├── complexity_routing.py         # Listing 5.3 — three-tier router
    ├── tree_of_thoughts.py           # Listings 5.4-5.4b — ToT + UCT/MCTS
    └── hypothesis_testing.py         # Listings 5.5-5.5b — scientific-method loop
```

`argus/reasoning.py` contains three Argus *method fragments* (Listings
5.2b, 5.3b, 5.5c) that belong inside an `Argus` class. It is a conceptual
reference, not standalone runnable. For working reasoning patterns see
`patterns/`.

## Run

```bash
export ANTHROPIC_API_KEY=sk-...
python patterns/chain_of_thought.py
python patterns/complexity_routing.py
```
