# Benchmarks

Benchmark methodology and results (charter §19). The objective is **not** to beat every existing project — it is to answer honestly:

```text
WHERE ARE WE BETTER?      WHERE ARE WE WORSE?
WHERE ARE WE SIMPLER?     WHERE ARE WE MORE GENERAL?
WHERE ARE WE MORE CONSTRAINED?   WHERE ARE WE MORE MAINTAINABLE?
```

## Rules

- Every benchmark records its **methodology and environment** (hardware, versions, dataset, model, commit studied) so results are reproducible.
- A benchmark that can only confirm the choice already made is not being run correctly (charter §19). Include the baseline and report unfavorable results.
- Report what is measured in explicit terms: correctness, latency, throughput, memory, tokens, cost, reliability/recovery, scalability, ergonomics.
- Never present a benchmark as an evaluation of correctness (charter §18).

## Status

**Partial.** One baseline exists — a hand-written `monolithic` implementation
(single LLM call, no tools, no memory) — measured against Systems A/B/C in
[`results.md`](results.md) (2026-10-09 run; scripted transport, no network). The
Phase 4 exit criterion asks for **≥2 monolithic frameworks**; the second
baseline is the open item. Current results are composition-cost comparisons,
not framework comparisons: the baseline shares the scripted transport, so only
per-layer overhead is visible (latency means 0.02–0.11 ms), and token counts
read 0 because the scripted transport returns no usage — both are properties
of the fixture, stated so the numbers are not over-read.