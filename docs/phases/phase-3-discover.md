# Phase 3 — Discover

**Status:** ✅ Complete (work landed 2026-10-08/09 via PRs #5–#6 and the taxonomy-expansion commits; reconciled 2026-10-16 in session OC1 — this document was stale, all criteria below verified against artifacts)
**Charter basis:** §30 — *"Automate discovery — the pipeline identifies new patterns not yet in the taxonomy and proposes new categories."*
**Depends on:** [Phase 2](phase-2-study.md) complete

## Goal

Stop hand-curating the taxonomy. Have the pipeline identify patterns and
categories the repository does not yet know about, and cross-reference across
repositories to find convergent patterns.

## Exit criteria

- [x] Cross-repo pattern convergence detection (same pattern, many implementations) — `study_pipeline/discover.py` + `make discover`
- [x] The pipeline proposes new taxonomy categories with evidence, not guesses — `docs/discovery/2026-10-08-convergence.md` (4 convergent patterns: config 15/25, caching 14/25, guardrails 10/25, rate-limiting 6/25)
- [x] A review workflow exists for accepting/rejecting proposed categories — `study_pipeline/review.py` + `make review` (7 tests, 2026-10-08); per-pattern ADOPT/DEFER/REJECT checklists in `docs/discovery/review/`; adoption requires an ADR (ADR-0021 Decision 2)
- [x] The taxonomy has grown, with each addition traceable to evidence — Phase 2 added `config` (ADR-0022), `caching` (ADR-0023), `agent-config` (ADR-0024), `evidence-plane` (ADR-0025), `evaluation` (ADR-0026), `worker-contract` (ADR-0027); Phase 3 added `guardrails` (ADR-0031) and `reliability` (ADR-0032) from convergence evidence
- [x] Obsolete patterns are flagged for deprecation (charter §23) — `study_pipeline/deprecation.py` (10 tests) + `make deprecations`; run on 2026-10-16: 13 patterns observed, 0 deprecation candidates (all tracked categories well-represented)

## Method

- Cluster pattern candidates across studied repos by behavior, not naming.
- Rank by convergence (how many independent systems solved it) and by gap (is it missing here?).
- Propose as `DISCOVERED` entries; a human decides whether to promote.
- Flag existing entries whose reference projects have moved on.

## Risks

| Risk | Mitigation |
|---|---|
| Taxonomy bloat — every pattern becomes a category | Charter §2: categories are for navigation. Require convergence evidence before adding one. |
| Automation proposes garbage | Proposals are `DISCOVERED` and human-reviewed; never auto-promoted. |
| Chasing novelty over depth | Rank by real demand (charter §24.2), not by interestingness. |

## Next action

Phase closed. The review documents in `docs/discovery/review/` (4 convergent
patterns) remain open proposals (ADOPT/DEFER/REJECT); resolving them — and the
taxonomy's 6 `DISCOVERED` capabilities — is later work, not Phase 3 machinery.
Machinery follow-ups (if any) belong in `state/DEBT.md`.
