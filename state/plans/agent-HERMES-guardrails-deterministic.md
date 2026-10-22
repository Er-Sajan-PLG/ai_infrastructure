# Plan: agent-HERMES — Guardrails (deterministic half) to TESTED

## Objective

Deliver Phase 5A.2 of `docs/implementation-plan.md`: the deterministic half of
`guardrails`, to `TESTED`, with a recorded IMPLEMENT decision (ADR-0038) and a
DW-016 deferral removed because its trigger has fired (the implementation plan
brings the deterministic half into scope now).

## Scope

- `catalog/guardrails/` (new category README + `guardrails/` entry: protocols, policy, validators, examples, tests)
- `specifications/guardrails.md` (deferral spec → designed spec)
- `research/guardrails/guardrails.md` (RESEARCHED → UNDERSTOOD)
- `docs/decisions/0038-guardrails-deterministic.md`, `docs/decisions/README.md`
- `docs/DEFERRED.md` (remove DW-016)
- `TAXONOMY.md` (guardrails entry → TESTED)
- `ai_infrastructure/__init__.py`, `scripts/validate_catalog.py`, `pyproject.toml`
- `docs/roadmap.md`, `state/` (DASHBOARD.md, REGISTRY.md, sessions/, plans/)

## Approach

- Protocol-first, stdlib-only, zero runtime dependencies (charter §22).
- Deterministic validators first; model-backed classifiers stay out of scope (DW-015).
- Compose `tool_registry.schema.validate_arguments` through its public interface for schema checks.
- Reasons are content-free for model content (PII, regex matches); configured terms may be named.
- One test per validator on pass and reject paths; hostile fixtures for regex/allowlist/PII.
- Policy decision tests (PASS/FLAG/REJECT), "reasons carry no content" assertion, and a
  "validator chain cannot be skipped" test.

## Risks

- **Scope creep into model-backed classifiers** — out of scope by spec; no metered call path exists.
- **Duplicating evaluation-framework names in the unified package** — avoided by distinct names
  (`LengthBoundValidator`, `JsonSchemaValidator`).
- **Regex ReDoS on caller-supplied patterns** — patterns are caller config (trusted), documented;
  fixed patterns are used for PII.

## Rollback

Revert the branch. The capability is additive: no existing entry changes behaviour, and the
taxonomy entry returns to `DECIDED`/DEFER with DW-016 restored.

## Success criteria

- `make check`, `make status`, `make ci` exit 0.
- `make diff-coverage` 100% on changed lines.
- Taxonomy entry `guardrails` is TESTED with implementation + tests paths that exist.
- DW-016 absent from `docs/DEFERRED.md`; `make deferred` green.
