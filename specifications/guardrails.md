# Specification: `guardrails`

- **Capability id:** `guardrails`
- **Name:** Guardrails & Output Validation
- **Lifecycle status:** `TESTED` — **IMPLEMENT** ([ADR-0038](../docs/decisions/0038-guardrails-deterministic.md))
- **Date:** 2026-10-22

## Problem statement and who needs it

Before model output reaches a user, a tool call, or another system, something
must decide whether it is allowed — and say why when it is not. The consumer
is any caller that sits at a trust boundary; today the capability ships as a
library the caller invokes (there is no auto-wired boundary yet). Model-backed
classifiers remain out of scope ([DW-015](../docs/DEFERRED.md)).

## Interfaces and data flow

```
model output (str)
  -> Validator.validate(output) -> ValidationResult
  -> GuardrailPolicy.check(output) -> GuardrailOutcome
       decision in {PASS, FLAG, REJECT}
       reasons: content-free tuple[str, ...]
  -> caller owns the rejection path
```

Key types:

- `Severity` — `WARNING | ERROR`.
- `GuardrailDecision` — `PASS | FLAG | REJECT`. There is deliberately no
  `REGENERATE`: re-generation is a caller choice, not a guardrail action.
- `ValidationResult(validator, passed, severity, reason, metadata)` — `reason`
  is required on failure and forbidden on pass; it never carries the rejected
  content.
- `Validator` — `Protocol` with `name: str` and `validate(text: str)`.
- `GuardrailOutcome(policy, decision, results)` — `allowed`, `failures`,
  `reasons`.
- `GuardrailPolicy(name, validators, on_error=REJECT, on_warning=FLAG)` — runs
  every validator (never short-circuits).
- `Rails(input_policy=None, output_policy=None)` — caller-invoked placement at
  a boundary; at least one rail required.

Deterministic validators (stdlib only):

- `LengthBoundValidator(min_chars, max_chars, severity)` — inclusive bounds.
- `JsonSchemaValidator(schema)` — composes `tool_registry.schema` (`check_schema`
  at construction, `validate_arguments` at runtime).
- `RegexMatchValidator(pattern, mode="deny"|"allow")` — deny fails on match,
  allow fails on no match.
- `AllowlistValidator(terms, case_sensitive)` — fails when no term present.
- `DenylistValidator(terms, case_sensitive)` — fails when any term present; the
  configured term may be named (configuration, not model content).
- `PIIValidator(kinds)` — email, phone, SSN, credit card (Luhn-checked), API
  key; reports kinds and counts only.
- `OneLineValidator(max_lines)` — structural.
- `ValidJsonValidator()` — structural.

### Design answers (pinned at DECIDED, resolved here)

1. **Policy shape** — `GuardrailPolicy(validators, on_error, on_warning)`; decision
   vocabulary is `PASS | FLAG | REJECT`. `REJECT` is the only blocking decision.
2. **Validator set** — deterministic first (list above); model-backed classifiers
   stay out of scope.
3. **Placement** — caller-invoked at the boundary; the guardrail returns a
   decision and the caller owns the rejection path. `Rails` holds input/output
   policies for pre/post-model placement.
4. **Reason reporting** — reasons name the rule and counts/positions only; PII
   and regex matches never echo the matched content. Denylist/allowlist may name
   the configured term.

Data flow: model output → validator chain → policy decision → pass (forward) /
reject (reason to caller) / flag (caller's choice).

## Invariants and failure modes

- A guardrail validates; it never silently rewrites. Rewriting model output
  invisibly is a traceability violation.
- Rejection reasons never embed the rejected content (a guardrail must not
  become a leak channel).
- Deterministic first: a validator that cannot be exercised without a live
  model call is a later stage, not the first implementation.
- `GuardrailPolicy.check` runs every validator — no short-circuit — so a caller
  sees all reasons at once.
- Validation results and rejection reasons are constructed from the rule, never
  from instructions found inside model output (prompt-injection safety).
- Failure modes to design against: validation bypass (a path around the
  guardrail), policy drift between deterministic and classifier mechanisms, and
  rejection reasons that are content-free but useless.

## Security implications and trust boundaries

The guardrail **is** a trust boundary: untrusted model output enters, a policy
decision leaves. It must not become a bypass for prompt injection — validation
results and rejection reasons are constructed from the rule, never from
instructions found inside the output, and PII or regex matches are reported by
count and position, never echoed.

## Dependencies and standards

- `depends_on`: `tool-registry` (JSON Schema validation via public interface).
- Standards: JSON Schema 2020-12 subset (tool-registry's supported subset).

## Testing strategy (§18) and benchmark plan (§19)

- One test per validator on pass and reject paths; hostile fixtures for regex,
  allowlist and PII.
- Policy decision tests: PASS / FLAG / REJECT, including the "reason carries no
  content" assertion.
- Chain test: a request through the composed policy runs every validator.
- Benchmark: deterministic validators are cheap; correctness evidence, not
  throughput evidence.

## Out of scope

- Model-backed moderation/safety classifiers (needs a metered call path —
  [DW-015](../docs/DEFERRED.md)).
- Governance policy and human-in-the-loop approval (that is `safety/` per
  ADR-0031).
- Retry and rate policy around validation failures (that is `reliability/`, DW-017).

## References

- [Research record](../research/guardrails/guardrails.md)
- [ADR-0038](../docs/decisions/0038-guardrails-deterministic.md) — decision
- [ADR-0031](../docs/decisions/0031-guardrails-category.md) — taxonomy category
