# Chapter 10 — Composition methodology

Chapter 10 combines patterns across cognitive functions and evaluates the
result as an architecture hypothesis. The book presents the decision-bearing
parts of the two listings below; these files provide the complete, offline-safe
execution context.

## Listing map

| Listing | Executable source |
|---|---|
| 10.1 | `examples/ch10/composition_contracts.py` |
| 10.2 | `examples/ch10/argus_completion.py` |

Listing 10.1 separates the proposed composition from the evidence used to
admit it. Listing 10.2 closes one Argus review through scoped reading, action
authorization, internal critique, external acceptance, and a separately
authorized memory write.

## Run the listing tests

The tests use local fakes and make no model or network calls:

```bash
cd ch10-methodology
python3 -m unittest discover -s tests -v
```

They cover composition acceptance and rejection, missing evidence, successful
completion, missing reflection, failed external acceptance, and the rule that
only accepted work can reach durable memory.

## Cumulative Argus

The existing `argus/`, `patterns/`, and `demos/` directories retain the
cumulative code-review agent and its end-to-end demonstrations. Run the full
offline demonstration with:

```bash
cd ch10-methodology
python3 demos/demo_end_to_end_review.py
```

Chapter 11 has no additional numbered listings in this repository; it reuses
the implementations referenced in the chapter.
