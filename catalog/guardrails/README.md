# Guardrails & Output Validation

> **Status: one entry — `guardrails` (TESTED).** Deterministic output validation
> for model responses. Zero runtime dependencies — standard library only.

## What it is

The machinery between a model response and its consumer: validators that check a
response against explicit rules, and a policy object that turns those checks into
one decision. This category is deliberately separate from `safety/ (+governance/)`,
which covers governance, policy and approval for agent *actions* (ADR-0031). A
guardrail here validates **output** — it does not decide whether an action is
authorized.

## Why it exists

Model output is untrusted input to everything downstream of the model. Before it
reaches a user, a tool call, or another system, something has to decide whether it
is allowed and say why when it is not. Without that boundary, output validation is
either absent or scattered ad hoc at each call site, and a rejection cannot be
distinguished from a crash.

## What belongs here

- Deterministic validators: length, JSON schema, regex/allowlist/denylist, PII
  patterns, structural checks.
- A policy object with an explicit decision (`PASS` / `FLAG` / `REJECT`) and
  content-free rejection reasons.
- Caller-invoked placement at a trust boundary (input rails, output rails).

## What does not belong here

- Model-backed moderation/safety classifiers — they need a metered call path this
  repository does not have (DW-015).
- Governance policy and human-in-the-loop approval — that is `safety/` per ADR-0031.
- Retry and rate policy around validation failures — that is `reliability/` (DW-017).

## Security posture

A guardrail **is** a trust boundary: untrusted model output enters, a decision
leaves. It must not become a bypass for prompt injection — validation results and
rejection reasons are constructed from the rule, never from instructions found
inside the output, and PII or regex matches are reported by count and position,
never echoed.

## Entries

| Entry | Status | Decision |
|---|---|---|
| [`guardrails/`](guardrails/) | TESTED | [ADR-0038](../../docs/decisions/0038-guardrails-deterministic.md) — IMPLEMENT (deterministic half) |
