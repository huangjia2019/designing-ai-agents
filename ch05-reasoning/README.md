# Chapter 5 — Reasoning

Chapter 5 implements four independent reasoning controls: represented
decision chains, difficulty routing, parallel exploration, and bounded
hypothesis testing. It also keeps consequence policy separate from difficulty
and returns an observable `ReasoningTrace` from Argus reviews.

## Files

```text
ch05-reasoning/
├── argus/
│   └── reasoning.py
├── patterns/
│   ├── response_text.py
│   ├── reasoning_trace.py
│   ├── chain_of_thought.py
│   ├── complexity_routing.py
│   ├── tree_of_thoughts.py
│   └── hypothesis_testing.py
└── tests/
    └── test_ch05_reasoning.py
```

## Listing map

| Listing | Executable source |
|---|---|
| 5.1 | `patterns/reasoning_trace.py` |
| 5.2–5.4 | `patterns/chain_of_thought.py` |
| 5.5 | `argus/reasoning.py` (`review_with_reasoning`) |
| 5.6–5.7 | `patterns/complexity_routing.py` |
| 5.8 | `argus/reasoning.py` (`routing_view`, `review`) |
| 5.9–5.11 | `patterns/tree_of_thoughts.py` |
| 5.12–5.13 | `patterns/hypothesis_testing.py` |
| 5.14 | `argus/reasoning.py` (`verify_bug`, `run_in_sandbox`) |

The book prints the decision-bearing portions. These files add the parser,
response normalization, MCTS bookkeeping, evidence summarization, review
policy, and bounded command runner needed to execute those excerpts.

## Run the offline checks

The behavior suite uses fake model responses and makes no network calls:

```bash
cd ch05-reasoning
python -m unittest discover -s tests -v
python -m compileall -q argus patterns tests
```

Live model paths require `ANTHROPIC_API_KEY` and the root repository
requirements. The tests do not.

## Important boundaries

- A represented chain is an application-owned decision record, not a claim to
  expose a model's private reasoning.
- Difficulty chooses capacity. Consequence may require evidence or human review
  before difficulty routing runs.
- `run_in_sandbox` uses an allowlist, no shell, a fixed working directory, a
  timeout, and bounded output. It is a teaching guardrail, not full isolation;
  test code still executes repository code.
- Branch and investigation budgets may end without convergence. The explicit
  result is then `inconclusive`.
