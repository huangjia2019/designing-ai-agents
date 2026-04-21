# Chapter 4 — Memory

Four memory patterns: hierarchical tiers, RAG, progress tracking, failure journals.

```
ch04-memory/
├── argus/
│   └── memory.py                     # Listing 4.4 — Argus cross-session memory
└── patterns/
    ├── hierarchical_memory.py        # Listings 4.1-4.3 — three-tier memory
    ├── rag_pipeline.py               # Listing 4.5 — query rewrite + hybrid search
    ├── progress_tracker.py           # Listing 4.6 — crash-recoverable checkpoints
    └── failure_journal.py            # Listings 4.7-4.8 — append-only lessons
```

`progress_tracker.py` is pure Python. The other three expect an `llm`
and (for RAG/journal) a vector database — dependency injection, not
framework-coupled.

## Run

```bash
python patterns/progress_tracker.py  # pure-Python demo, no API key needed
```
