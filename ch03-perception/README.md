# Chapter 3 — Perception

Four perception patterns and their integration into Argus.

```
ch03-perception/
├── argus/
│   └── perception.py                 # Listings 3.5a-e — Argus perception pipeline
└── patterns/
    ├── context_triage.py             # Listing 3.1 — priority-based window allocation
    ├── semantic_compaction.py        # Listing 3.2 — compress context, protect errors
    ├── progressive_discovery.py      # Listing 3.3 — three-phase broad-to-deep search
    └── multimodal_fusion.py          # Listing 3.4 — normalize mixed inputs
```

All pattern files accept a pluggable `llm` object; any class exposing
`.generate(prompt) -> str` works. `argus/perception.py` is pure Python,
no LLM required at import time.

## Run

```bash
python patterns/context_triage.py    # pure-Python demo, no API key needed
```
