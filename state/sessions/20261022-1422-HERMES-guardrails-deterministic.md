# Session: 2026-10-22 — Guardrails (deterministic half) to TESTED (HERMES)

- **Agent:** HERMES (meituan/longcat-2.5-preview:free session)
- **Branch:** `feat/guardrails-deterministic`
- **Task:** Implement Phase 5A.2 of the implementation plan — deterministic output guardrails — to TESTED
- **Started:** 2026-10-22 14:22 UTC
- **Status:** Active

## Objective

1. Implement `guardrails` (deterministic half) at `catalog/guardrails/guardrails/` per `specifications/guardrails.md` and the Phase 5A.2 plan: `Validator` protocol, `ValidationResult`, `GuardrailPolicy`, `GuardrailOutcome`, deterministic validators (length, JSON schema, regex, allowlist, denylist, PII, one-line, valid-JSON).
2. Promote the taxonomy entry `guardrails` from `DECIDED` (DEFER) to `TESTED` (IMPLEMENT, ADR-0038).
3. Remove DW-016 from `docs/DEFERRED.md` (implemented — the register says delete the entry in the same change).
4. Rewrite `specifications/guardrails.md` from deferral spec to designed spec; update `research/guardrails/guardrails.md` to UNDERSTOOD with the IMPLEMENT decision.
5. Wire the new category into `validate_catalog.py` CATEGORIES, `ai_infrastructure/__init__.py`, import-linter `root_packages`/`source_modules`, and unified exports.
6. Update `docs/roadmap.md`, `state/DASHBOARD.md`, `docs/decisions/README.md`, `state/REGISTRY.md`.
7. Gates: `make check`, `make status`, `make ci`, and 100% diff coverage on changed lines.

## Claims

- `catalog/guardrails/`
- `specifications/guardrails.md`
- `research/guardrails/guardrails.md`
- `docs/decisions/0038-guardrails-deterministic.md`
- `docs/DEFERRED.md`
- `TAXONOMY.md` (guardrails entry)
- `ai_infrastructure/__init__.py`
- `scripts/validate_catalog.py`
- `pyproject.toml`
- `state/` (DASHBOARD.md, REGISTRY.md)

## Design answers (spec §Interfaces, pinned at DECIDED and now resolved)

1. **Policy shape** — `GuardrailPolicy(name, validators, on_error, on_warning)`; decision vocabulary is `PASS | FLAG | REJECT`. `REJECT` is the only blocking decision; re-generation stays the caller's choice (the spec's invariant).
2. **Validator set** — deterministic only: `LengthBoundValidator`, `JsonSchemaValidator`, `RegexMatchValidator`, `AllowlistValidator`, `DenylistValidator`, `PIIValidator`, `OneLineValidator`, `ValidJsonValidator`.
3. **Placement** — caller-invoked at the boundary; the guardrail returns a decision and the caller owns the rejection path. `Rails` holds input/output policies for pre/post-model placement.
4. **Reason reporting** — reasons name the rule and counts/offsets only; PII and regex matches never echo the matched content. Denylist/allowlist may name the configured term (config, not model content).
