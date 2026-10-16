# Specification: `config-and-settings`

- **Capability id:** `config-and-settings`
- **Name:** Configuration & Settings Infrastructure
- **Lifecycle status:** `DECIDED` — **DEFER** ([ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md), [DW-014](../docs/DEFERRED.md))
- **Date:** 2026-10-16

> **This is a deferral specification.** It exists because the lifecycle model
> requires a DESIGNED artifact before a DECIDE-stage claim, and because the
> deferral's trigger is only actionable if the design questions are already
> pinned. It deliberately does **not** design interfaces for consumers that
> do not exist (charter §24).

## Problem statement and who needs it

Every service eventually needs configuration resolved from several sources
with a defined precedence. Hand-rolled environment lookups scattered through
a codebase make failure modes untraceable — the classic ones being wrong
precedence and resolved secrets in logs. The consumer is the first catalog
entry or integration that needs layered resolution; today there is none
(every entry takes explicit constructor arguments), which is why the
capability is deferred.

## Interfaces and data flow

**No interfaces are designed at this stage.** When the trigger fires, the
design must answer these questions first:

1. **Sources and precedence** — is the chain `constructor > environment >
   file > defaults`, and where is it declared (one visible table, not
   dispersed lookups)?
2. **Validation timing** — is the settings object validated at construction
   (fail fast) or lazily per field (fail at use)? One answer, applied
   consistently.
3. **Missing values** — is a missing required setting a startup error, and
   what does the error message contain (name, not value)?
4. **Secret references** — how is a secret *reference* resolved at use
   without the resolved value ever entering a `repr`, a log line, or an
   exception message?

Data flow (sketch, not a design): sources → precedence merge → validation →
settings object consumed by exactly the entries that declared the need.

## Invariants and failure modes

- Resolved secret values never appear in logs, exceptions, or `repr`
  (taxonomy security note; the same posture as
  [`execution-trace-recorder`](execution-trace-recorder.md) content capture).
- Precedence is deterministic and stated in one place — two sources never
  race silently.
- A setting read is a pure function of the merged sources: no hidden global
  state, no read-time side effects.
- Failure modes to design against: wrong precedence (silently reading a
  stale default), partial validation (some fields checked, some not), and
  secret leakage through error paths.

## Security implications and trust boundaries

Referencing a secret is in scope; storing or rotating one is not. The trust
boundary is the logging/trace surface: configuration is where credentials
enter a process, so the configuration layer is the first place they could
leak. This invariant is non-negotiable when the capability is built.

## Dependencies and standards

- `depends_on`: none.
- Standards: the twelve-factor `config` principle (environment-based
  configuration) is the relevant reference; no format standards are adopted
  or claimed.

## Testing strategy (§18) and benchmark plan (§19)

When built:

- Precedence tests: one test per adjacent pair in the chain, plus the full
  chain.
- Validation tests: missing required value, wrong type, valid object.
- **Secret-leak tests:** assert that `repr`, `str`, log capture, and raised
  exceptions never contain a resolved secret value — the hostile-input class
  already used for trace redaction.
- Benchmark: not meaningful at this size; revisit only if resolution enters
  a per-request path.

## Out of scope

- Secret storage, rotation, or a secrets manager integration.
- Per-environment profile files and hot reload (until a second consumer
  needs them — see [DW-014](../docs/DEFERRED.md)).
- Feature-flag evaluation services.

## References

- [Research record](../research/config/config-and-settings.md)
- [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [ADR-0022](../docs/decisions/0022-configuration-taxonomy-category.md) — taxonomy category
