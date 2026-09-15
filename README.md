# ai_infrastructure

An independent, evolving **AI infrastructure laboratory**: research repository, architectural knowledge base, implementation library, interoperability layer, evaluation environment, and reusable engineering foundation for AI systems.

The goal is **not** to build another agent framework. The goal is to understand the major classes of AI infrastructure — how existing systems solve them, what the trade-offs are — and build independent, composable, verifiable versions where justified, so that many different AI systems can be assembled from these pieces.

> Read [`CHARTER.md`](CHARTER.md) first. It is the constitution of this repository.

## Quick orientation

| File / Directory | Purpose |
|---|---|
| [`CHARTER.md`](CHARTER.md) | Mission, rules, quality bar, session protocol (the source of truth) |
| [`docs/standards.md`](docs/standards.md) | **Enforceable** engineering standards — every rule mapped to its check |
| [`docs/development.md`](docs/development.md) | Environment setup, toolchain, gates |
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

**Phase 1 — Seed.** Repository skeleton and enforced environment established: taxonomy, registry, ADR process, standards mapped to checks, and a drift detector that refuses to let status drift from reality. No capabilities implemented yet. See [`docs/roadmap.md`](docs/roadmap.md) for the seeded capability queue.

## Getting started

```bash
make setup            # create .venv, install pinned toolchain
make install-hooks    # enforce gates locally on every commit
make check            # lint + types + catalog contract + tests
make status           # detect taxonomy drift vs. artifacts on disk
```

See [`docs/development.md`](docs/development.md) for details.

## Working on this repository

1. Check [`TAXONOMY.md`](TAXONOMY.md) for the highest-priority capability that isn't MATURE (priority reasoning is recorded in each entry, per charter §24).
2. Follow the Session Protocol (charter §25) and Agent Operating Procedure (§26).
3. Produce the Output Contract (§27). Keep status honest (§4) — `make status` enforces this.
4. Record decisions as ADRs (§12) in the same session they're made.
5. Consult [`docs/standards.md`](docs/standards.md) for the rule you are about to satisfy and the check that proves it.

## License

[Apache-2.0](LICENSE) — see [`NOTICE`](NOTICE) and [ADR-0002](docs/decisions/0002-license-selection.md) for the reasoning, including why this license was chosen over MIT, AGPL, and BSL.

**External contributions are not currently accepted** — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the reason (it preserves the option to relicense future versions).
