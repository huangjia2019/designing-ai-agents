# Chapter 4 — Memory

**Use `current_edition/` for the current chapter's eight listings.**
The code separates retaining information, retrieving candidate evidence,
resuming work, and admitting a lesson for future use. Python 3.10 or newer
is required; the offline demo and tests need no API key or external package.

The existing `argus/` and `patterns/` directories remain the earlier cumulative
snapshot for compatibility. Their `before_review()`, `after_review()`, and
`consult()` interfaces are not the current chapter's candidate-oriented
interfaces. Keep the two implementations separate.

## Run

From this directory:

```bash
python3 -m current_edition.demo
python3 -m unittest discover -s tests -v
```

From the repository root:

```bash
python3 -m unittest discover -s ch04-memory/tests -v
```

The demo proposes a review-memory candidate, explicitly consolidates it,
reopens a JSON progress snapshot, and retrieves failure candidates for review.
It uses fixed model responses and a deterministic in-memory index. No external
model call or business action occurs.

Two adapter instances share that index within the demo process; this is not
a claim that the index survives a process restart. Only the JSON progress
snapshot and append-only failure file demonstrate filesystem persistence.

## Listing → executable module

The chapter's logical `patterns/` and `argus/` paths map to the executable
files below:

| Listing | Current executable file | Purpose |
|---|---|---|
| 4.1 | `current_edition/hierarchical_memory.py` | Memory tiers, records, and working-memory insertion |
| 4.2 | `current_edition/hierarchical_memory.py` | Retrieval into working context |
| 4.3 | `current_edition/hierarchical_memory.py` | Budget-based eviction and selective consolidation |
| 4.4 | `current_edition/memory.py` | Propose review candidates and retrieve them for validation |
| 4.5 | `current_edition/rag_pipeline.py` | Query rewriting, hybrid retrieval, rank fusion, and answer context |
| 4.6 | `current_edition/progress_tracker.py` | JSON task snapshots and resumption context |
| 4.7 | `current_edition/failure_journal.py` | Append failure evidence and propose a candidate heuristic |
| 4.8 | `current_edition/failure_journal.py` | Similarity-based candidate consultation and journal helpers |

`current_edition/support.py` provides a small test index, not a vector database.
The current listing adapter receives a `HierarchicalMemory` instance:

```python
from current_edition import ArgusMemory, HierarchicalMemory, InMemoryIndex

index = InMemoryIndex()
memory = HierarchicalMemory(index)
argus = ArgusMemory(memory)

argus.propose_after_review(
    "Check which package owns an unexpected import", "example-api"
)
# The host separately decides when to retain selected entries.
memory.consolidate()

candidates = argus.retrieve_candidates_for_review(
    "example-api", "unexpected import"
)
```

`propose_after_review()` does not automatically consolidate. The returned
strings are candidate evidence for independent validation, not instructions
that automatically govern the next action. Consolidation chooses what is
stored; it is not an approval or truth test.

## Candidate consultation is not admission

`FailureEntry.candidate_heuristic` and
`FailureJournal.consult_candidates(context, min_score, k)` make the current
contract explicit. The caller supplies the similarity threshold. The journal
does not validate causal transfer, admit advice, grant tool permissions, or
apply a retrieved lesson.

The printed consultation code assumes a dedicated candidate index. It filters
by similarity, not by an enforced status or access-control field. A mixed store
needs host-side status, provenance, scope, version, and authorization filters
before material can enter an admitted-use path. Renaming a method does not
create that security boundary.

## What the tests cover

The native tests check working-budget eviction; selective retention; explicit
consolidation; candidate retrieval; hybrid-query inputs and source labels;
rank-fusion deduplication; JSON resumption; retained failure context;
append-only journal behavior; and caller-supplied consultation thresholds.

## Production limits

- The token estimate and retention score are teaching heuristics. Use the
  model's tokenizer and task-specific evidence in a real budget policy.
- The supplied index is in memory. It has no durable storage, access control,
  tenant separation, or admission workflow.
- RAG context assembly does not authenticate a source, resolve policy versions,
  filter entitlements, or prove that an answer follows the evidence.
- The progress snapshot is a direct, non-atomic JSON write. It does not provide
  transactional checkpoints, side-effect receipts, concurrent-writer handling,
  or exactly-once execution. The caller must provide an existing parent
  directory for snapshot and journal paths.
- Journal retrieval reconstructs candidate records from a compact text/index
  representation. Production systems should retain stable record identifiers
  and structured provenance rather than treating this format as lossless.
- Keep current policies, approvals, hard limits, and confirmed effects in the
  authoritative control plane. Memory can retain their history and references;
  a retrieved candidate cannot override them.

## Earlier cumulative snapshot

The previous files remain unchanged under `argus/` and `patterns/` so earlier
examples continue to run. For the current chapter use `current_edition`; the
older interfaces do not express the same candidate/admission boundary.
