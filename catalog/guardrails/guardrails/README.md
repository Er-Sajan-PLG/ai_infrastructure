# Guardrails

> **Status: `TESTED`.** Deterministic output validation. Zero runtime dependencies — standard library only; all model calls stay out of scope.

| | |
|---|---|
| **Capability** | [`guardrails`](../../../TAXONOMY.md) (category: guardrails) |
| **Specification** | [`specifications/guardrails.md`](../../../specifications/guardrails.md) |
| **Decision** | [ADR-0038](../../../docs/decisions/0038-guardrails-deterministic.md) — `IMPLEMENT` |
| **Research** | [`research/guardrails/guardrails.md`](../../../research/guardrails/guardrails.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — original |

## What it is

Composable output validation for AI systems: a `Validator` protocol, a
`ValidationResult` with a content-free reason, a `GuardrailPolicy` that turns
checks into one decision (`PASS` / `FLAG` / `REJECT`), caller-invoked `Rails`
for input/output placement, and deterministic validators (length, JSON schema,
regex, allowlist, denylist, PII patterns, one-line, valid-JSON). Model-backed
classifiers are deliberately out of scope (DW-015).

## How it works

```python
from guardrails import (
    DenylistValidator,
    GuardrailPolicy,
    PIIValidator,
    LengthBoundValidator,
)
from guardrails.validators import ValidJsonValidator

policy = GuardrailPolicy(
    name="output",
    validators=(
        LengthBoundValidator(max_chars=2000),
        ValidJsonValidator(),
        DenylistValidator(("secret", "password")),
        PIIValidator(),
    ),
)
outcome = policy.check(model_output)
if not outcome.allowed:
    # caller owns the rejection path
    print(outcome.reasons)
```

**Design decisions:**

- **Protocol-first** — `Validator` is a `Protocol`; implement without subclassing.
- **Run all validators** — `GuardrailPolicy.check` never short-circuits, so every
  reason is reported.
- **Content-free reasons** — PII and regex matches are reported by count and
  position, never echoed; a guardrail must not become a prompt-injection leak
  channel.
- **Caller owns rejection** — the guardrail returns a decision; it never
  rewrites or re-generates.
- **Compose, don't duplicate** — `JsonSchemaValidator` composes
  `tool_registry.schema` through its public interface.
- **Zero runtime dependencies** — stdlib only.

## Our implementations

| Implementation | Language | Notes |
|---|---|---|
| [`protocols.py`](protocols.py) | Python | `Validator`, `ValidationResult`, `Severity`, `GuardrailDecision`, `GuardrailOutcome` |
| [`policy.py`](policy.py) | Python | `GuardrailPolicy`, `Rails` |
| [`validators/deterministic.py`](validators/deterministic.py) | Python | Length, regex, allowlist, denylist, one-line, valid-JSON, JSON schema |
| [`validators/pii.py`](validators/pii.py) | Python | `PIIValidator`, `PiiKind` |

## References

- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) — rail concept
- [Llama Guard](https://github.com/meta-llama/PurpleLlama) — safety classifier (model-backed; out of scope here)
- [Presidio](https://github.com/microsoft/presidio) — PII detection patterns
