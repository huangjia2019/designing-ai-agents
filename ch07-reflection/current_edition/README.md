# Current Chapter 7: executable listings

This directory contains the code from the revised Reflection chapter, kept
together so its records, policy functions, and injected adapters are easy to
run. Start here when reading the current MEAP chapter. The older `argus/` and
`patterns/` directories remain available as cumulative compatibility demos;
their APIs are not the current chapter's listing implementation.

## Run without an API key

Use Python 3.10 or newer. These examples use only the standard library.
From the repository root:

```bash
python --version
python ch07-reflection/current_edition/demo.py
python -m unittest discover -s ch07-reflection/current_edition/tests -v
```

The offline demo runs an arithmetic artifact through a bounded review,
demonstrates verified recovery in an in-memory workspace, admits a capability
through three evidence gates, and recalls a scoped lesson for a repeated task.
Its model and infrastructure callbacks are deterministic stand-ins.

## Listing map

All 20 listings are in [`reflection.py`](reflection.py), with their listing
numbers beside the corresponding definitions. Word callout markers are omitted
because they do not affect execution.

| Listings | Definitions and responsibility |
| --- | --- |
| 7.1–7.4 | `EvidenceItem`, `ReviewContract`, `review_once`, `generator_critic`: review the exact artifact and stop within a budget |
| 7.5–7.6 | Recovery policy, repair and verification records; capture a restorable baseline |
| 7.7–7.9 | `repair_allowed`, `apply_and_verify`, `self_heal`: constrain repair scope, verify, roll back, or hand off |
| 7.10–7.11 | `SkillVersion`, `admit_skill`: isolated, coexistence, and trial evidence before activation |
| 7.12–7.13 | `hard_allowed`, `route_skill`: filter permissions, conditions, dependencies, and risk before selection; permit abstention |
| 7.14 | `withdraw_skill`: evidence-backed, reversible withdrawal through a trusted registry |
| 7.15–7.16 | Lesson records and admission: retain source traces, scope, causal or repeated-case support, and conflicts |
| 7.17–7.18 | `recall_phase`, `recall_experience`: trigger replay only when needed; enforce status, scope, versions, and limits |
| 7.19 | `ReflectionCoordinator`: a changed artifact must not inherit the prior version's accepted review |
| 7.20 | `decide_release`: distinguish hard blocking signals from advisory measurements |

## What the tests establish

The 39 deterministic tests cover review limits, exact-version evidence,
protected-path and tool rejection, failed-repair rollback, regression and
no-progress handoff, evidence-backed skill admission, conditional coexistence,
router abstention, canonical registry objects, protected withdrawal approval,
lesson provenance and conflict checks, replay triggers and budgets, and release
decisions after recovery.

These are decision-boundary tests, not proofs of a production sandbox or
model quality. The recovery workspace must resolve symbolic links, enforce
permissions at the actual write, protect its verifier, and provide real
snapshot/restore behavior. The skill registry must validate evidence and
approval identities and implement its own atomic updates. Dependency checks,
domain matching, repeated-case thresholds, and ranking are injected policies.
An application must supply and test those adapters before using the code
against external systems.

The acceptance callbacks are trusted interfaces, not adversarial parsers.
For example, `generator_critic` relies on a valid `Critique` verdict and a
domain-backed `select_best`, while `decide_release` relies on its caller's
validated signal records. Those contracts should be enforced at the boundary
where model or external data enters the application.
