# Phase 5 — Sustain

**Status:** ⬜ Not started
**Charter basis:** §23 (continuous ecosystem research), §30 — *"Community contributions, periodic re-study, deprecation of obsolete patterns, continuous ecosystem monitoring."*
**Depends on:** [Phases 1–4]

## Goal

Keep the repository alive and honest as the AI ecosystem moves. Anything static
becomes wrong; the job is to notice and correct.

## Standing activities

- **Re-study** — re-review studied repos as they evolve; refresh `last_reviewed` (charter §23)
- **Deprecate** — mark obsolete capabilities `DEPRECATED`; do not silently delete
- **Monitor** — track standards (MCP, OpenTelemetry, model interfaces) and adopt only on evidence
- **Re-benchmark** — refresh numbers; stale benchmarks are worse than none
- **Upgrade** — improve implementations against newly learned patterns
- **Accept contributions** — *only* once a CLA or DCO-with-relicense-grant is adopted (ADR-0002)

## Exit criteria

Ongoing, not terminal. Health is measured by:

- [ ] No capability older than N months without review
- [ ] Deprecated entries clearly marked, with the reason recorded
- [ ] The research registry reflects the current ecosystem, not a snapshot
- [ ] Documentation matches implementation
- [ ] The contribution policy is decided (ADR superseding ADR-0002's restriction)

## Risks

| Risk | Mitigation |
|---|---|
| Fossilisation | Scheduled re-study; `last_reviewed` is a required schema field |
| Chasing every new trend | Charter §24: rank by real demand and verifiability |
| Status decay — labels outliving artifacts | `make status` in CI, permanently |

## Next action

Deferred. Revisit when Phase 2 produces the first deprecation candidate.
