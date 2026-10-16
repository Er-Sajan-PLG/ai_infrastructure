# DEBT — Technical Debt Tracker

> Known technical debt, deliberately deferred work, and accepted risks.

---

## Active Debt

None. (Debts are moved to the table below in the change that resolves them.)

## Resolved

| ID | Description | Resolution | Closed |
|---|---|---|---|
| DEBT-005 | `InfrastructureScanner.__init__` accepted a `model_provider` param but built its own `OpenAIProvider` internally — the passed provider was ignored | Honored, not removed (WP6): the provider is threaded from `__init__` through `scan()` into `scan_with_llm(provider=...)`, defaulting to `OpenAIProvider` only when `None`; two regression tests added (`catalog/deployment/scanner/tests/test_scanner.py`) | 2026-10-16 |
| DEBT-004 | `basic-rag-pipeline` capability was DISCOVERED, never researched | Promoted to TESTED via ADR-0034: `catalog/retrieval/basic_rag_pipeline/` + spec + research + taxonomy entry, 42 tests (WP4) | 2026-10-16 |
| DEBT-003 | `vector-memory-store` capability was DISCOVERED, never researched | Promoted to TESTED via ADR-0033: `catalog/memory/vector_store/` + spec + research + taxonomy entry on `master` (commit `3999dce`, PR #7); `make status` counts it TESTED | 2026-10-16 |
| DEBT-001 | Infrastructure scanner was uncommitted and lacked spec/research/ADR/taxonomy | Committed: `catalog/deployment/scanner/` + spec + research + ADR-0029 + TESTED taxonomy entry, all tracked on `master` (verified via `git ls-tree -r master`) | 2026-10-08 |
| DEBT-002 | Study pipeline enhancements (stack_detector, dependency_extractor) uncommitted | Committed: both files tracked on `master` and `HEAD`, working tree clean (verified via `git ls-tree -r` + `git status`) | 2026-10-08 |

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

## Resolved risks

| ID | Risk | Resolution | Closed |
|---|---|---|---|
| AR-005 | No remote — CI can't run | Remote added: `github.com/Er-Sajan-PLG/ai_infrastructure` (public), `master` pushed 2026-10-08; CI runs on push/branches from here on | 2026-10-08 |
