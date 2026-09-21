# Architecture of this Repository

How `ai_infrastructure` itself is organized and why. Provisional (charter §13) — change with an ADR when evidence shows a better structure.

## Planes

The repository separates **knowledge** from **code**:

```text
Knowledge plane (no executable code)
├── research/          Findings per category (what we studied, what we learned)
├── specifications/    Designs before code (DESIGNED stage artifacts)
├── TAXONOMY.md        Machine-readable capability registry
├── docs/decisions/    ADRs — why decisions were taken
└── docs/registry/     Research registry — external projects, licensing, attribution

Code plane
├── catalog/           Independent implementations, organized by category
│   └── <category>/<id>/  README.md, PROVENANCE.md, implementation, examples/, tests/
├── integrations/      Compositions of catalog components into working systems
├── benchmarks/        Benchmark methodology + results
├── examples/          Standalone demos
└── tests/             Cross-cutting test suites

Machinery
├── study_pipeline/    Automated repo-study subsystem (Phase 2, charter §29)
└── scripts/           Validation and maintenance scripts
```

## Design rules

1. **Knowledge before code.** A capability appears in `TAXONOMY.md` before it has a directory in `catalog/`, and research/specification artifacts exist before implementation starts (charter §26).
2. **One capability, one directory.** Each `catalog/<category>/<id>/` is self-contained: README, PROVENANCE, implementation, examples, tests (charter §13 Category Documentation Standard).
3. **Catalog entries are peers.** A component never imports from an unrelated catalog entry unless the taxonomy records the dependency (`depends_on`).
4. **Composition lives in `integrations/`.** Combining components into systems is a distinct artifact class, not something baked into components (charter §17).
5. **Primitives/src-level reuse** goes in `catalog/primitives/` or `catalog/runtime/` and itself follows all entry rules.

## Status

5 catalog entries across 5 of 20 declared categories (see `TAXONOMY.md`). 1 end-to-end integration. 5 specifications, 5 research records. The repository is past skeleton — see `docs/roadmap.md` for the current phase and queue.
