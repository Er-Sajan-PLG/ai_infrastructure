# DASHBOARD — Executive Summary

> **Last Reconciled:** 2026-10-23 (session HERMES — stabilization pass merged (PR #22) + all sessions closed (PR #23); 13 TESTED; 1588 tests; `make check-strict` green)
> **Protocol:** MACP (Multi-Agent Coordination Protocol)

---

## Project: ai_infrastructure

An independent AI infrastructure laboratory — research repository, architectural knowledge base, implementation library, interoperability layer, evaluation environment, and reusable engineering foundation for AI systems.

## Current Status

| Field | Value |
|---|---|
| **Phase** | Phase 5 (Sustain) — Active; laboratory foundation and top-level package complete and production ready |
| **Branch** | `master` |
| **Tests** | 1588 passing, 3 deselected (verified via `make check-strict`, 2026-10-23) |
| **Coverage** | ≥85% floor enforced, green (>91%) |
| **ADRs** | 42 (0000–0041 contiguous, counted from disk) |
| **Capabilities** | 13 TESTED across 13 categories (verified via `make status`) |
| **Runtime deps** | Zero (stdlib only) |

## Active Agents

_(none — all sessions closed by maintainer directive 2026-10-23; claims released)_

## Critical Alerts

- All sessions closed 2026-10-23 (memory-framework, model-gateway, rate-limiting, stabilization). Next work starts on a new branch in a new session.
- Passkey not yet configured; close authorization recorded as maintainer directive 2026-10-23 (ADR-0030 marker). Configure passkey before next close cycle.
- `make review` regenerates `docs/discovery/review/*.md` wholesale — the WP5 decisions deliberately live in ADR-0035 + `docs/DEFERRED.md` instead, never in those generated files.

## Recently Completed

- Phase 0–4, 7 — stabilization pass (PR #22, 2026-10-23): reconciled repo truth (README/architecture/gap-analysis/BLOCKERS/INDEX), removed stale DW-017, corrected TAXONOMY `depends_on`, added `make doc-sync` + `make wheel-check` gates, widened SAST, ADR-0042/0043, baseline snapshot, external-consumer proof. 1588 tests, all gates green.
- Phase 5B.4 — `rate-limiting` → TESTED (PR #20, 2026-10-23): TokenBucket, RetryPolicy, ResilientExecutor; ADR-0041; 28 tests.
- Phase 5B.2 — `memory-framework` → TESTED (PR #18, 2026-10-23): InMemoryMemory composing VectorStore; ADR-0040; 25 tests.
- Phase 5B.1 — `model-gateway` → TESTED (PR #17, 2026-10-23): DefaultGateway with fallback/cooldown/cost; ADR-0039; 22 tests.
- All 2026-10-23 sessions closed (PR #23): memory-framework, model-gateway, rate-limiting; passkey not yet configured; close authorization recorded as maintainer directive.
- Phase 5A.2 — `guardrails` (deterministic half) → TESTED (HERMES, 2026-10-22): Validator protocol, GuardrailPolicy (PASS/FLAG/REJECT), Rails, deterministic validators (length, JSON schema, regex, allowlist, denylist, PII, one-line, valid-JSON); ADR-0038; DW-016 removed (10 TESTED capabilities)
- WP6 — `InfrastructureScanner` now honors an injected `model_provider` (threaded through `scan()` into `scan_with_llm`; defaults to `OpenAIProvider` only when `None`); DEBT-005 resolved, DEBT-004 moved to Resolved (`065b2a6`, 2026-10-16)
- WP5 — five discovered capabilities decided (ADR-0035): DEFER config-and-settings, response-cache, guardrails, rate-limiting (DW-014–017); DOCUMENT agent-instruction-files (`21e2f64`, 2026-10-16)
- WP4 — `basic-rag-pipeline` promoted to TESTED: research + spec + ADR-0034 + 42 tests (`385fcdd`, `c0666d2`, 2026-10-16)
- WP3 — Phase 4 closed: second monolithic baseline (`monolithic_rag`) + `make bench` now executes (`4802a84`, 2026-10-16)
- `make check` ↔ `check-strict` parity gap closed — master was red on `check_integrations` while remote CI stayed green; regression test added (`248f618`, 2026-10-16)
- Test hygiene: study-pipeline review test and three System B tests wrote artifacts into the repo tree; both now use `tmp_path` (2026-10-16)
- Reconciled phase docs/roadmap/state with reality: phase 1.5/3 statuses, missing `make deprecations` target added, charter's stale "Current phase" stamp replaced (2026-10-16)
- `vector-memory-store` → TESTED (ADR-0033; `catalog/memory/vector_store/`; 7th capability) — merged 2026-10-09 (PR #7)
- Phase 4 Systems A/B/C in `integrations/` (PRs #8–#10, 2026-10-09); benchmark harness + first monolithic baseline (`benchmarks/results.md`, PR #11)
- Phase 3 — Discover closed: convergence detection, review workflow, deprecation flagging; `guardrails` + `reliability` categories adopted (ADR-0031/0032)
- MACP protocol bootstrapped + trial-run (`state/`, AGENTS.md, STATE.md)
- `infrastructure-scanner` completed to TESTED (spec, research, ADR-0029)
- Repo-wide mypy repaired (226→0 errors; 313 suppressions removed)
- Study-pipeline stack/dependency extraction; integration consistency checker
- MACP amendments P1–P6 implemented (`docs/macp-protocol.md` canonical + `docs/macp-protocol-review.md` rationale, AGENTS.md repointed; P7 deferred)
- Phase 0 — Foundation (charter, taxonomy, registry, ADR process)
- Phase 1 — Seed (5 capabilities TESTED: tool-registry, model-provider-abstraction, react-agent-loop, mcp-client, execution-trace-recorder)
- Phase 1.5 — Hardening (all gates enforced, 601 tests, 90.03% coverage)
- Phase 2 — Study (25 repos studied, 18 trade-offs, 6 new categories: ADR-0022–0027)

## Next Up

1. WP7 shutdown: push WP1–WP6 commits, obtain maintainer `Close-Authorized-By` marker, then flip OC1 to Completed and release ownership
2. Maintainer: review dependabot PRs #1 and #3
3. State-rot prevention P7 (machine-checked drift): deferred until P1–P6 have run long enough to reveal residual failures
4. Deferred capabilities (config-and-settings, response-cache, guardrails, rate-limiting): revisit at `review_by` 2027-10-16 per `docs/DEFERRED.md`

## Key Files

| File | Purpose |
|---|---|
| [`state/REGISTRY.md`](REGISTRY.md) | Active agents and file ownership |
| [`state/INDEX.md`](INDEX.md) | Searchable log of all past sessions |
| [`state/ARCHITECTURE.md`](ARCHITECTURE.md) | Current system architecture |
| [`state/DECISIONS.md`](DECISIONS.md) | Architecture Decision Records |
| [`state/DEBT.md`](DEBT.md) | Technical debt tracker |
| [`state/BLOCKERS.md`](BLOCKERS.md) | Active blockers |
| [`CHARTER.md`](../CHARTER.md) | Repository constitution |
| [`TAXONOMY.md`](../TAXONOMY.md) | Capability registry |
| [`docs/roadmap.md`](../docs/roadmap.md) | Phase status and session notes |

<!-- AUTO-SYNC:START -->
> Branched reality check (auto-synced, git-derived — do not hand-edit):
> branch `fix/docs-reconcile-2026-10-23` at `7ac5fb6`; session commits not on master: 0 (see `git log master..HEAD --oneline`).
> working tree dirty at sync time — see `git status`.
<!-- AUTO-SYNC:END -->
