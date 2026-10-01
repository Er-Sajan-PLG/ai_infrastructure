# DEBT — Technical Debt Tracker

> Known technical debt, deliberately deferred work, and accepted risks.

---

## Active Debt

| ID | Description | Impact | Trigger to Resolve | Status |
|---|---|---|---|---|
| DEBT-001 | Infrastructure scanner (`catalog/infrastructure/scanner/`) is uncommitted and lacks spec/research/ADR/taxonomy | Medium — code exists but can't be trusted per charter §4 | Decide to continue or discard | Open |
| DEBT-002 | Study pipeline enhancements (stack_detector, dependency_extractor) uncommitted | Low — additive features, no breakage | Commit or discard | Open |
| DEBT-003 | `vector-memory-store` capability is DISCOVERED, never researched | Low — blocked by priority | When Phase 1 queue resumes | Open |
| DEBT-004 | `basic-rag-pipeline` capability is DISCOVERED, never researched | Low — blocked by vector-memory-store | After vector-memory-store | Open |
| DEBT-005 | `InfrastructureScanner.__init__` accepts `model_provider` param but builds its own `OpenAIProvider` internally — the passed provider is ignored | Low — cosmetic API wart, documented behavior works | Cleanup pass on scanner API | Open |

## Deliberately Deferred (see docs/DEFERRED.md)

| ID | Item | Reason | Reversal Condition |
|---|---|---|---|
| DEF-001 | SBOM generation | Nothing published yet | First publication |
| DEF-002 | Provenance/attestation | Nothing published yet | First publication |
| DEF-003 | Containerization | No service exists | First service deployed |
| DEF-004 | Mutation testing | Coverage not plateaued | Coverage stable >90% |
| DEF-005 | osv-scanner, trivy | pip-audit covers known vulns | Supply-chain incident |
| DEF-006 | Complexity budget | mypy strict is clean | Debt appears |
| DEF-007 | Coverage service (Codecov) | Local coverage sufficient | Team grows |
| DEF-008 | Node toolchain | Python-only project | JS/TS added |
| DEF-009 | Branch protection as code | Single maintainer | Team grows |
| DEF-010 | Workspace governance coupling | Single repo | Multi-repo workspace |
| DEF-011 | Reminder workflow | No remote; GitHub disables after 60d inactivity | Remote added |
| DEF-012 | Doc-fact inlining | Manual verification sufficient | Docs drift detected |

## Accepted Risks (see docs/risks/)

| ID | Risk | Accepted | Review By | Rationale |
|---|---|---|---|---|
| AR-001 | Bandit per-plugin skips don't apply to nested test dirs | 2026-09-17 | 2027-03-17 | Documented with reasoning |
| AR-002 | Path-scoping reduces SAST coverage of tests | 2026-09-17 | 2027-03-17 | Tests are fixtures, not attack surface |
| AR-003 | Commit-msg checker differs from commitlint | 2026-09-17 | 2027-03-17 | Header-only is the subset used |
| AR-004 | import-linter independence (not forbidden) | 2026-09-17 | 2027-03-17 | Forbidding fails on correct code |
| AR-005 | No remote — CI can't run | 2026-09-17 | 2027-03-17 | Local gates are comprehensive |
