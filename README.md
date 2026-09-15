# ai_infrastructure

An independent, evolving **AI infrastructure laboratory**: research repository, architectural knowledge base, implementation library, interoperability layer, evaluation environment, and reusable engineering foundation for AI systems.

The goal is **not** to build another agent framework. The goal is to understand the major classes of AI infrastructure — how existing systems solve them, what the trade-offs are — and build independent, composable, verifiable versions where justified, so that many different AI systems can be assembled from these pieces.

> Read [`CHARTER.md`](CHARTER.md) first. It is the constitution of this repository.

## Quick orientation

| File / Directory | Purpose |
|---|---|
| [`CHARTER.md`](CHARTER.md) | Mission, rules, quality bar, session protocol (the source of truth) |
| [`TAXONOMY.md`](TAXONOMY.md) | Machine-readable map: what capabilities exist, their status, our implementations |
| [`AGENTS.md`](AGENTS.md) | Entry point for AI agent sessions (start-of-session checklist) |
| [`research/`](research/) | Study findings, organized by category |
| [`catalog/`](catalog/) | The implementation library — recreated infrastructure patterns |
| [`specifications/`](specifications/) | Designs before code (DESIGNED stage) |
| [`docs/decisions/`](docs/decisions/) | Architecture Decision Records (ADRs) |
| [`docs/registry/`](docs/registry/) | Research registry: external projects studied, licensing, attribution |
| [`docs/roadmap.md`](docs/roadmap.md) | Current phase, what's done, what's next |
| [`integrations/`](integrations/) | Compositions of catalog components into working systems |
| [`benchmarks/`](benchmarks/) | Benchmark methodology and results |
| [`study_pipeline/`](study_pipeline/) | Automated repository-study subsystem (Phase 2) |
| [`scripts/`](scripts/) | Maintenance/validation scripts |
| [`tests/`](tests/) | Cross-cutting test suites |

## Current status

**Phase 1 — Seed.** Repository skeleton established; taxonomy, registry, and decision-record standards in place. No capabilities implemented yet. See [`docs/roadmap.md`](docs/roadmap.md) for the seeded capability queue.

## Working on this repository

1. Check [`TAXONOMY.md`](TAXONOMY.md) for the highest-priority capability that isn't MATURE (priority reasoning is recorded in each entry, per charter §24).
2. Follow the Session Protocol (charter §25) and Agent Operating Procedure (§26).
3. Produce the Output Contract (§27). Keep status honest (§4).
4. Record decisions as ADRs (§12) in the same session they're made.

## License

Pending — see [`docs/decisions/0002-license-selection.md`](docs/decisions/0002-license-selection.md). Do not reuse code from this repository as if it carried a license until a license is chosen (human review gate, charter §22).
