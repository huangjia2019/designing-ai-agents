# September 2026 MEAP code guide

This guide maps the September 2026 MEAP update of *Designing AI Agents* to
the repository's runnable source files.

## Start with the matching chapter

| Chapter | Code entry | How to find each listing |
|---|---|---|
| 2: Architecture | `ch02-architecture/` | [Chapter 2 README](../ch02-architecture/README.md) |
| 3: Perception | `ch03-perception/` | [Chapter 3 README](../ch03-perception/README.md) |
| 4: Memory | `ch04-memory/current_edition/` | [Chapter 4 README](../ch04-memory/README.md) |
| 5: Reasoning | `ch05-reasoning/patterns/` and `argus/` | [Chapter 5 README](../ch05-reasoning/README.md) |
| 6: Action | `ch06-action/current_edition/` | [Chapter 6 README](../ch06-action/README.md) |
| 7: Reflection | `ch07-reflection/current_edition/` | [Chapter 7 README](../ch07-reflection/README.md) |
| 8: Collaboration | `ch08-collaboration/current_edition/` | [Chapter 8 README](../ch08-collaboration/README.md) |
| 9: Governance | `ch09-governance/current_edition/` | [Chapter 9 README](../ch09-governance/README.md) |
| 10: Composition | `ch10-methodology/examples/ch10/` | [Chapter 10 README](../ch10-methodology/README.md) |

Chapter READMEs map the book's logical module names to executable files and
explain any required adapters. For chapters that contain a `current_edition/`
package, that package is the entry point for the September 2026 MEAP text.

Follow the working directory stated in each chapter README, and use a fresh
Python process for each chapter. The chapter-local packages deliberately reuse
names and are not one globally installed application. Use Python 3.10 or newer
for the current pure-Python examples. Offline examples do not require model
credentials; adapters for real models, storage, external effects, and
operating-system isolation remain explicit integration work.

From the repository root, verify the MEAP examples without API keys:

```bash
python3 tools/verify_meap_examples.py
```

The runner launches each chapter in a fresh process. Run the repository-wide
syntax and import checks as well:

```bash
python3 tools/smoke_test.py
```

## Edition boundary

The default branch follows the current MEAP. Stable tags preserve earlier
published snapshots.
