# DECISIONS — Architecture Decision Records

> Summary of ADRs. Full text in `docs/decisions/`.

---

## ADR-0000: Repository Purpose
**Decision:** AI infrastructure laboratory, not an agent framework.
**Status:** Accepted

## ADR-0001: Primary Language
**Decision:** Python, type-hinted, ruff-linted, black-formatted.
**Status:** Accepted

## ADR-0002: License Selection
**Decision:** Apache-2.0 (over MIT, AGPL, BSL). Permissive favours optionality.
**Status:** Accepted

## ADR-0003: Toolchain
**Decision:** ruff lints, black formats, mypy strict, pytest tests.
**Status:** Accepted

## ADR-0004: Testing Enforcement
**Decision:** Empty tests/ is an error; testpaths includes catalog/.
**Status:** Accepted

## ADR-0005: Phase 0 Foundation
**Decision:** Sessions 1-5 recorded as Phase 0 (foundation before capabilities).
**Status:** Accepted

## ADR-0006: Tool Registry
**Decision:** IMPLEMENT — standalone JSON-Schema-native registry, zero runtime deps.
**Status:** Accepted

## ADR-0007: Model Provider Abstraction
**Decision:** IMPLEMENT — shape-owning, transport-injected, zero runtime deps.
**Status:** Accepted

## ADR-0008: ReAct Agent Loop
**Decision:** IMPLEMENT — bounded dispatcher, injected protocols, sync-only.
**Status:** Accepted

## ADR-0009: MCP Client
**Decision:** COMPATIBILITY — legacy era only; approval seam before every dispatch.
**Status:** Accepted

## ADR-0010: Execution Trace Recorder
**Decision:** IMPLEMENT — flat JSONL, content capture off by default.
**Status:** Accepted

## ADR-0011: Phase 1.5 Hardening
**Decision:** Name the hardening work Phase 1.5 (adds no capability).
**Status:** Accepted

## ADR-0012: Gate Architecture
**Decision:** Makefile is single source of truth; CI invokes it.
**Status:** Accepted

## ADR-0013: Verification Breadth
**Decision:** Which checks exist, with per-item reversal conditions.
**Status:** Accepted

## ADR-0014: Governance Drift
**Decision:** Accepted-risk register with review date that fails build when lapsed.
**Status:** Accepted

## ADR-0015: Makefile Shell Hardening
**Decision:** .ONESHELL, -eu -o pipefail, .DELETE_ON_ERROR.
**Status:** Accepted

## ADR-0016: Coverage Policy
**Decision:** Floor 85 (integer with margin), not displayed 90.
**Status:** Accepted

## ADR-0017: Structural Checks
**Decision:** import-linter for independence, check_collectability.py for tests.
**Status:** Accepted

## ADR-0018: Security Tooling
**Decision:** bandit + ruff S, pip-audit (2 sources), licence allow-list.
**Status:** Accepted

## ADR-0019: Commit Message Validation
**Decision:** Header-only validation via commit-msg hook.
**Status:** Accepted

## ADR-0020: Deferral Register
**Decision:** docs/DEFERRED.md with fact, trigger, reversal per item.
**Status:** Accepted

## ADR-0021: Study Pipeline Architecture
**Decision:** Never executes studied code; writes Markdown only.
**Status:** Accepted

## ADR-0022: Configuration Taxonomy Category
**Decision:** Add config/ category (15/25 repos).
**Status:** Accepted

## ADR-0023: Caching Taxonomy Category
**Decision:** Add caching/ category (14/25 repos).
**Status:** Accepted

## ADR-0024: Agent Repository Configuration
**Decision:** Add agent-config/ category (AGENTS.md in 18/25 repos).
**Status:** Accepted

## ADR-0025: Execution Evidence Plane
**Decision:** Add evidence-plane/ category.
**Status:** Accepted

## ADR-0026: Evaluator-Verifier Separation
**Decision:** Add evaluation/ category.
**Status:** Accepted

## ADR-0027: Worker Contract
**Decision:** Add worker-contract/ category.
**Status:** Accepted

## ADR-0028: LLM HTTP Transport
**Decision:** Guarded stdlib HTTP transport for integrations.
**Status:** Accepted
