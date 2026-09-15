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

Empty. No implementation exists to benchmark. Benchmarks require a working implementation plus a registered external baseline (see [`../docs/registry/RESEARCH_REGISTRY.md`](../docs/registry/RESEARCH_REGISTRY.md)).