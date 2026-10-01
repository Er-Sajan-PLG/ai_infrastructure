# ADR-0029: Infrastructure Scanner

**Status:** Accepted
**Date:** 2026-10-01
**Deciders:** ai_infrastructure maintainers

---

## Context

The repository needs a way to automatically detect and classify infrastructure
components used by a software repository. This is needed for:
- AI agents that need infrastructure context before generating code
- Compliance audits comparing infrastructure across repositories
- The study pipeline's stack detection (currently a separate module)

Previous work (uncommitted) had built the scanner code but never completed
the required artifacts per charter §4/§8.

## Decision

**IMPLEMENT** a deterministic, multi-layer infrastructure scanner with:
- 12-layer taxonomy (identity, transaction, state, data, communication, delivery, observability, security, deployment, integration, UX, governance)
- Three detection layers: keyword scanning, config parsing, optional LLM
- Zero runtime dependencies (stdlib only)
- Confidence scoring and explicit detection method labeling

## Consequences

### Positive
- Works offline, no API keys required
- Deterministic and testable
- Composable — `InfraMap` can be consumed by other tools
- Extensible — new component types added to taxonomy without code changes

### Negative
- Heuristic — may miss novel patterns or produce false positives
- YAML parsing is regex-based (not a real YAML parser) — may fail on complex YAML
- LLM layer adds complexity and requires API key

### Neutral
- The 12-layer taxonomy is a synthesis, not a standard
- Confidence scores are heuristic, not calibrated

## Alternatives Considered

| Alternative | Why Not |
|---|---|
| Use `tree-sitter` for AST parsing | Adds runtime dependency; overkill for config parsing |
| Use `pyyaml` for YAML | Would be a runtime dependency; regex heuristics cover common cases |
| Use existing tool (e.g., `checkov`, `tfsec`) | External dependency; cloud-specific; doesn't cover all 12 layers |
| Build only a config parser | Misses keyword-only signals (e.g., `import redis` in code) |

## Compliance with Charter

- **§4 (Capability Lifecycle):** This ADR records the DECIDED stage. Code exists and is TESTED.
- **§8 (Decide Before Building):** Decision recorded before implementation continues.
- **§11 (Research):** Research record at `research/deployment/infrastructure-scanner.md`.
- **§12 (Decision Records):** This ADR.
- **§20 (Standards):** Zero runtime dependencies, deterministic, well-tested.
- **§22 (Human Review):** No licensing risk (`code_reused: false`), no major dependencies, no trust-boundary changes.

## Related

- Specification: `specifications/infrastructure-scanner.md`
- Research: `research/deployment/infrastructure-scanner.md`
- Implementation: `catalog/deployment/scanner/`
- Tests: `catalog/deployment/scanner/tests/`
