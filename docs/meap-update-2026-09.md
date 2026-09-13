# September 2026 MEAP code update

The `1st-review` branch contains the companion-code update prepared for the
next MEAP release. `main` continues to serve the earlier published MEAP.
Do not switch editions halfway through a chapter: some reviewed interfaces
have changed even when a class keeps its name.

## Start with the matching chapter

| Chapter | Revised code entry | How to find each listing |
|---|---|---|
| 4: Memory | `ch04-memory/current_edition/` | [Chapter 4 README](../ch04-memory/README.md) |
| 5: Reasoning | `ch05-reasoning/patterns/` and `argus/` | [Chapter 5 README](../ch05-reasoning/README.md) |
| 6: Action | `ch06-action/current_edition/` | [Chapter 6 README](../ch06-action/README.md) |
| 7: Reflection | `ch07-reflection/current_edition/` | [Chapter 7 README](../ch07-reflection/README.md) |
| 8: Collaboration | `ch08-collaboration/current_edition/` | [Chapter 8 README](../ch08-collaboration/README.md) |
| 9: Governance | `ch09-governance/current_edition/` | [Chapter 9 README](../ch09-governance/README.md) |

The `current_edition` packages assemble the reviewed chapter listings into
runnable modules. Chapter READMEs map the book's logical module names to
these files and explain the required adapters. Earlier `argus/` and
`patterns/` modules remain available for cumulative examples that depend on
their older interfaces; they are not replacements for the revised listing
maps above.

Follow the working directory stated in each chapter README, and use a fresh
Python process for each chapter. The chapter-local packages deliberately reuse names and
are not one globally installed application. Use Python 3.10 or newer for
the revised pure-Python examples. Offline examples do not require model
credentials; adapters for real models, storage, external effects and
operating-system isolation remain explicit integration work.

The first three chapters keep their existing entry points. Chapter 2's model
default and listing map are aligned with the revised text; no live provider
call is required by its tests. The reasoning
chapter retains its previously synchronized decision-record implementations.
This release does not revise the Chapter 10/11 material.

From the repository root, verify the revised examples without API keys:

```bash
python3 tools/verify_reviewed_examples.py
```

The runner launches each chapter in a fresh process and exercises the native
code, not an extracted manuscript or an external service. For the retained
cumulative snapshots, also run `python3 tools/smoke_test.py`.

## Release boundary

Before the new MEAP is published, use `1st-review` only when following the
revised chapters. Once publication is confirmed, the reviewed code can be
merged into `main` after checking any intervening changes and rerunning the
chapter tests. This is a normal reviewed merge, not a forced replacement
of repository history. The existing `book-1st-edition` tag and earlier
commits remain available for readers using the previous edition.
