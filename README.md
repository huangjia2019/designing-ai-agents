# Designing AI Agents — Source Code

<a href="https://hubs.la/Q04hCsH10">
  <img src="./docs/manning-book-card.png" alt="Designing AI Agents — Manning" width="480">
</a>

**[*Designing AI Agents*](https://hubs.la/Q04hCsH10)** — the design-pattern catalogue for production AI agents. (Manning)

This repository is the official source code for the book — every listing,
organized by chapter, verified to import cleanly on Python 3.12.

中文版：[README.zh-CN.md](README.zh-CN.md)

> **Looking for individual patterns, organized by the two-axis matrix
> rather than by chapter?** See the companion catalog
> [**huangjia2019/agent-design-patterns**](https://github.com/huangjia2019/agent-design-patterns)
> — 28 patterns, each placed at a coordinate in the 7 × 6 framework,
> each self-contained and runnable in isolation. This repo follows the
> book's chapter-by-chapter narrative (Argus grows module by module);
> that repo is the pattern reference you can drop into a project today.

---

## Layout

```
designing-ai-agents/
├── ch01-paradigm-shift/     Chapter 1 — conceptual contrast (no API)
├── ch02-architecture/       Chapter 2 — PRA loop, Runtime VM, cross-framework
├── ch03-perception/         Chapter 3 — 4 perception patterns + Argus integration
├── ch04-memory/             Chapter 4 — 4 memory patterns + Argus integration
└── ch05-reasoning/          Chapter 5 — 4 reasoning patterns + Argus integration
```

Each chapter is independent. Inside, two sibling directories:

- **`patterns/`** — one pattern per file, no framework coupling. Accepts a
  pluggable `llm` / `vector_db` via the constructor.
- **`argus/`** — cumulative snapshot of *Argus*, the running-example code
  reviewer that grows module by module from Ch2 to Ch10.

## Install

```bash
git clone https://github.com/huangjia2019/designing-ai-agents
cd designing-ai-agents
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your ANTHROPIC_API_KEY / OPENAI_API_KEY
```

Requires Python **3.10+** (the book uses 3.12).

## Run

Most pattern files are self-contained. Change into a chapter and run:

```bash
cd ch03-perception
python patterns/context_triage.py    # pure-Python, no API key
```

Files that call an LLM look for `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`
for the OpenAI-SDK demos). They will import cleanly without the key, but
`main()` execution needs one.

## How the book maps to the code

| Book chapter | Repo directory | Listings |
|--------------|----------------|----------|
| 1. Paradigm shift | `ch01-paradigm-shift/` | illustrative only |
| 2. Agent architecture | `ch02-architecture/` | 2.1 – 2.6 |
| 3. Perception | `ch03-perception/` | 3.1 – 3.5e |
| 4. Memory | `ch04-memory/` | 4.1 – 4.8 |
| 5. Reasoning | `ch05-reasoning/` | 5.1 – 5.5c |

Per-chapter READMEs map each listing to its file. Chapters 6-10 will land
as the manuscript completes review.

## A few files are deliberately *not* runnable

The book includes some architectural sketches and method-fragment snippets
that do not stand alone:

- `ch02-architecture/argus/runtime.py` — references supporting classes
  (`RuntimeConfig`, `Sandbox`, `MCPHost`, ...) that the book never
  defines. Treat as structural pseudocode.
- `ch05-reasoning/argus/reasoning.py` — three snippets (Listings 5.2b,
  5.3b, 5.5c) that belong inside an `Argus` class. Conceptual reference.

Both files have a docstring header marking them as such. The other 21
Python files in Ch1-5 import cleanly with no side effects.

## Verification

All Python files are tested at extraction time:

- syntax check (AST parse)
- import check (module body executes without error)
- `[CA]` typesetter-continuation markers stripped automatically

Status: **22 runnable / 23 total** (one conceptual by design). Run the
smoke test yourself:

```bash
python3 tools/smoke_test.py
```

## License

MIT. See [LICENSE](LICENSE).

## Citation

If this code helps your work, cite the book:

> Huang, Jia. *Designing AI Agents*. Manning Publications, forthcoming 2027.

## Contact

- Book errata & discussion: [Manning liveBook forum](https://livebook.manning.com/) (after MEAP launch)
- Repo issues: GitHub Issues on this repository
- Author: [@huangjia2019](https://github.com/huangjia2019)
