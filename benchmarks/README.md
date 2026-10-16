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

**Met — two monolithic baselines present.** `make bench` runs
[`bench_composition.py`](bench_composition.py) and regenerates
[`results.md`](results.md) (last run 2026-10-16). The baselines are
`monolithic` (bare single-call chain) and `monolithic_rag` (inlined retrieval
chain); they model the monolithic shapes in the study corpus rather than
installing third-party frameworks (zero-runtime-deps; ADR-0021 Decision 1), and
the report says so. Standing caveats, restated in the report itself: the
transport is scripted, so the numbers compare **composition overhead**, not
framework quality; token counts are **fixture values** that exercise each
system's usage-accounting path, not real tokenization.