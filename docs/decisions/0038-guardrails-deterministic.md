# ADR-0038: Guardrails — Deterministic Half (IMPLEMENT)

**Status:** Accepted
**Date:** 2026-10-22
**Drivers:** Charter §18 (honest evaluation), Phase 5A.2 of the implementation plan, ADR-0031 (guardrails category), ADR-0035 (DEFER/DW-016)

## Context

The repository has a `guardrails` taxonomy entry (ADR-0031) at `DECIDED`/`DEFER`
(DW-016): no user-facing model-output boundary exists, so the capability was
deferred. Phase 5A.2 of the implementation plan brings the deterministic half
into scope now: model output is validated before it reaches a caller, and the
implementation plan's trigger is the plan itself rather than a live boundary.
The deferral's other half — model-backed classifiers — still needs a metered
call path that does not exist (DW-015), so it stays deferred.

## Decision

**IMPLEMENT** the deterministic half of `guardrails` as a stdlib-only capability:

1. **Protocol-first design** — `Validator` protocol, `ValidationResult`,
   `GuardrailOutcome`, `GuardrailDecision` (`PASS | FLAG | REJECT`).
2. **Policy composition** — `GuardrailPolicy` runs every validator it holds
   (never short-circuits) and aggregates into one decision.
3. **Caller-invoked placement** — `Rails` holds input/output policies; the
   guardrail returns a decision and the caller owns the rejection path. There
   is deliberately no `REGENERATE` decision.
4. **Deterministic validators first** — length, JSON schema, regex, allowlist,
   denylist, PII, one-line, valid-JSON. Zero model calls.
5. **Content-free reasons** — PII and regex matches reported by count and
   position, never echoed; a guardrail must not become a prompt-injection leak
   channel.
6. **Zero runtime dependencies** — stdlib only; `JsonSchemaValidator` composes
   `tool_registry.schema` through its public interface.

## Options Considered

| Option | Verdict | Reason |
|--------|---------|--------|
| **IMPLEMENT (deterministic half)** (selected) | ✅ | Delivers the validators that need no model calls; removes DW-016 |
| IMPLEMENT (full, incl. classifiers) | ❌ | Needs a metered call path (DW-015) |
| DEFER (keep DW-016) | ❌ | Phase 5A.2 of the implementation plan now in scope |
| ADAPT NeMo Guardrails / Llama Guard | ❌ | Heavy deps, model-backed, vendor lock-in |

## Consequences

### Positive

- Removes DW-016 (implemented) — deferral register no longer lists it.
- Provides a reusable trust boundary for any caller (RAG answer surface, agent
  loop final step, tool-call boundary).
- Composes `tool-registry`'s schema validation rather than duplicating it.
- Reasons are content-free, closing the leak channel.

### Negative

- No model-backed moderation yet (DW-015 remains).
- No auto-wired boundary: placement is caller-owned by design.

## Implementation Scope

**catalog/guardrails/** with:

- `guardrails/protocols.py` — `Validator`, `ValidationResult`, `Severity`,
  `GuardrailDecision`, `GuardrailOutcome`.
- `guardrails/policy.py` — `GuardrailPolicy`, `Rails`.
- `guardrails/validators/deterministic.py` — length, regex, allowlist,
  denylist, one-line, valid-JSON, JSON schema.
- `guardrails/validators/pii.py` — `PIIValidator`, `PiiKind`.
- `guardrails/examples/quickstart.py`
- `guardrails/tests/` — 40+ tests.

## Verification

- `make check` passes (lint, typecheck, catalog contract, tests).
- `make status` shows `guardrails` category with TESTED capability.
- Coverage ≥ 85% on changed lines (diff-coverage 100%).
- Import-linter contracts maintained (guardrails added to `source_modules`).
- DW-016 removed from `docs/DEFERRED.md`; `make deferred` green.
