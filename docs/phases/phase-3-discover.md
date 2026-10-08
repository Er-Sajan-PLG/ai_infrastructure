# Phase 3 — Discover

**Status:** ⬜ Not started
**Charter basis:** §30 — *"Automate discovery — the pipeline identifies new patterns not yet in the taxonomy and proposes new categories."*
**Depends on:** [Phase 2](phase-2-study.md) complete

## Goal

Stop hand-curating the taxonomy. Have the pipeline identify patterns and
categories the repository does not yet know about, and cross-reference across
repositories to find convergent patterns.

## Exit criteria

- [x] Cross-repo pattern convergence detection (same pattern, many implementations) — `study_pipeline/discover.py` + `make discover`
- [x] The pipeline proposes new taxonomy categories with evidence, not guesses — `docs/discovery/2026-10-08-convergence.md` (4 convergent patterns: config 15/25, caching 14/25, guardrails 10/25, rate-limiting 6/25)
- [x] A review workflow exists for accepting/rejecting proposed categories — `study_pipeline/review.py` + `make review` generates review documents with ADOPT/DEFER/REJECT checklists
- [x] The taxonomy has grown from Phase 1's 7 categories, with each addition traceable to evidence — Phase 2 added 6 categories (config, caching, agent-config, evidence-plane, evaluation, worker-contract); Phase 3 added 2 (guardrails, reliability) via ADR-0031/0032
- [ ] Obsolete patterns are flagged for deprecation (charter §23) — not yet implemented

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

Deferred until Phase 2 yields enough cross-repo data to cluster.
