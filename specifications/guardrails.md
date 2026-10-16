# Specification: `guardrails`

- **Capability id:** `guardrails`
- **Name:** Guardrails & Output Validation
- **Lifecycle status:** `DECIDED` — **DEFER** ([ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md), [DW-016](../docs/DEFERRED.md))
- **Date:** 2026-10-16

> **This is a deferral specification.** It exists because the lifecycle model
> requires a DESIGNED artifact before a DECIDE-stage claim, and because the
> deferral's trigger is only actionable if the design questions are already
> pinned. It deliberately does **not** design interfaces for consumers that
> do not exist (charter §24).

## Problem statement and who needs it

Before model output reaches a user, a tool call, or another system, something
must decide whether it is allowed — and say why when it is not. The consumer
is the first integration or entry where model output crosses a trust
boundary. Today no such boundary exists: model output is consumed only by
tests, benchmarks and examples, which is why the capability is deferred.

## Interfaces and data flow

**No interfaces are designed at this stage.** When the trigger fires, the
design must answer these questions first:

1. **Policy shape** — what does a policy object declare (rules, severity,
   actions), and is the decision vocabulary `pass / reject-with-reason /
   require re-generation`?
2. **Validator set** — which deterministic validators exist first (length,
   structural/schema checks, regex and allowlist checks), modeled on the
   error taxonomies already in the catalog?
3. **Placement** — where does validation sit relative to the caller
   (`basic-rag-pipeline`'s answer surface, an agent loop's final step, a
   tool-call boundary), and who owns the rejection path?
4. **Reason reporting** — required rejection reasons must be actionable
   without echoing the offending content (the leak problem is the same one
   `execution-trace-recorder` solved with its redaction posture).

Data flow (sketch, not a design): model output → validator chain → policy
decision → pass (forward) / reject (reason to caller) / regenerate (caller's
choice, not the guardrail's).

## Invariants and failure modes

- A guardrail validates; it never silently rewrites. Rewriting model output
  invisibly is a traceability violation.
- Rejection reasons never embed the rejected content (a guardrail must not
  become a leak channel).
- Deterministic first: a validator that cannot be exercised without a live
  model call is a later stage, not the first implementation.
- Failure modes to design against: validation bypass (a path around the
  guardrail), policy drift between the two kinds of mechanism (deterministic
  vs classifier), and rejection reasons that are content-free but useless.

## Security implications and trust boundaries

The guardrail **is** a trust boundary (taxonomy security note): untrusted
model output enters, a policy decision leaves. It must not become a bypass
for prompt injection — specifically, validation results and rejection
reasons must never be constructed from instructions found inside model
output.

## Dependencies and standards

- `depends_on`: none.
- Standards: none claimed. JSON-Schema-style validation is the natural
  deterministic starting point given `tool-registry`'s schema posture, but
  no format standard is adopted in this deferral.

## Testing strategy (§18) and benchmark plan (§19)

When built:

- One test per validator on pass and reject paths; hostile fixtures for regex
  and allowlist checks.
- Policy decision tests: pass / reject-with-reason / regenerate, including
  the "reason carries no content" assertion.
- Placement tests: a request through the composed path cannot skip the
  validator chain.
- Benchmark: only meaningful once a live call path exists (shared with
  [DW-015](../docs/DEFERRED.md)); deterministic validators are cheap and
  need correctness evidence, not throughput evidence.

## Out of scope

- Model-backed moderation/safety classifiers (needs a metered call path —
  [DW-015](../docs/DEFERRED.md)).
- Governance policy and human-in-the-loop approval (that is `safety/` per
  ADR-0031).
- Retry and rate policy around validation failures (that is `reliability/`, DW-017).

## References

- [Research record](../research/guardrails/guardrails.md)
- [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [ADR-0031](../docs/decisions/0031-guardrails-category.md) — taxonomy category
