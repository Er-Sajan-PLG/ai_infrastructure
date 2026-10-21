# Examples

Small, runnable demonstrations of individual catalog capabilities and of minimal compositions. Examples are how a consumer judges whether a capability is useful without adopting the whole repository (charter §17, §31).

## Rules

- One directory per example, named for what it demonstrates.
- Each example has a short `README.md`: what it shows, the exact command to run it, and its prerequisites.
- Examples may depend on catalog entries only through their public interfaces.
- An example that no longer runs is a bug — delete or fix it rather than leaving it stale.
- Examples are not tests. Correctness evidence lives in each catalog entry's `tests/` and in `../tests/` (charter §18).

## Available Examples

- [`ai_infrastructure_quickstart/`](ai_infrastructure_quickstart/) — Complete, end-to-end runnable demonstration of the unified `ai_infrastructure` top-level package.
- `catalog/*/<entry>/examples/` — Granular, standalone demonstrations of each individual capability in isolation.

## Status

8 catalog entries across 8 categories, each with a runnable example, plus the unified `ai_infrastructure` package quickstart. All examples run with zero runtime dependencies and zero network calls.