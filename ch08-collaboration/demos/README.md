# Chapter 8 demos

Optional scripts. Nothing here is a book listing; the chapter's listings are in
`../patterns/` and `../argus/`.

- `adk_fan_out_gather.py` — the fan-out/gather topology expressed as framework
  primitives (ADK's `ParallelAgent` inside a `SequentialAgent`) rather than the
  hand-built thread pool in `../patterns/fan_out_gather.py`. Read the two side
  by side: the hand-built version owns the concurrency and the failure
  handling, the framework version inherits both. Requires
  `pip install google-adk`.

  It also emits deprecation warnings: google-adk 2.7 deprecates `ParallelAgent`
  and `SequentialAgent` in favour of a graph-based `Workflow` API. The file is
  kept as written because the churn is the point — the topology survives the
  primitive that spells it.
