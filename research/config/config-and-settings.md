# Research Record: Configuration & Settings Infrastructure

- **Capability:** `config-and-settings` (category: config)
- **Status:** `RESEARCHED` — convergence-level evidence only; no deep per-implementation study (§3 explains why that is sufficient for a deferral)
- **Date:** 2026-10-16
- **Decision:** see [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) *(DEFER, DW-014)*
- **Sources:** [ADR-0022](../../docs/decisions/0022-configuration-taxonomy-category.md), [convergence report](../../docs/discovery/2026-10-08-convergence.md), study pipeline reports (`study_pipeline/studied_repos/`), [TAXONOMY.md](../../TAXONOMY.md) §4

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. Evidence from the study corpus

**FACT.** 15 of 25 studied repositories proposed `config` — the single most
common proposal in Phase 2 Track 2B ([convergence report](../../docs/discovery/2026-10-08-convergence.md)).
Named in the report: `OpenHands`, `SWE-agent`, `agno`, `ai`, `autogen`, plus
10 more.

**FACT.** The study pipeline's classifier found no existing taxonomy category
to map the pattern onto, which is what triggered the category ADR (ADR-0022).

**OBSERVATION.** The reports' recurring surface is settings *resolution*:
environment loading, precedence between sources, per-environment profiles,
and secret *referencing* — not secret storage.

**OBSERVATION.** Ubiquity is partly a language-ecosystem convention (a
`config.py` / `settings.py` module appears in most Python packaging layouts)
rather than a signal specific to AI infrastructure. The ADR recording the
category said the same and marked the capability priority `low`.

## 2. The problem, stated without reference to any implementation

> Resolve a program's configuration from several sources with a defined,
> inspectable precedence — without ever logging a resolved secret.

Stated that way, the capability decomposes into four concerns.
**DESIGN OPINION.**

| # | Concern | Question it answers |
|---|---|---|
| 1 | **Sources** | Where can a value come from (constructor, env, file, default)? |
| 2 | **Precedence** | Which source wins, and is that order visible in one place? |
| 3 | **Validation** | When is a resolved settings object checked, and how does it fail? |
| 4 | **Secrets** | How are secret *references* resolved without the value entering logs? |

## 3. What was not studied, and why that is acceptable here

**OBSERVATION.** This record aggregates convergent evidence; it does not
review any single implementation's precedence semantics, validation approach,
or secret handling in depth.

**INFERENCE.** That depth is not owed for this decision, because the decision
is DEFER. The repository has no consumer of layered resolution: every catalog
entry takes explicit constructor arguments, and the only environment read in
`catalog/` is the scanner's opt-in example. A deep study would produce design
input for a consumer that does not exist — the exact inversion charter §24
warns against.

## 4. Why the decision is DEFER

See [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) §Decision 1.
The measurable current fact: no catalog entry resolves configuration at
runtime ([DW-014](../../docs/DEFERRED.md)). The trigger: the first entry or
integration that needs layered resolution (`defaults < file < environment`)
or an environment-variable contract beyond constructor injection.

**DESIGN OPINION.** When the trigger fires, the first design questions are
already pinned in [the specification](../../specifications/config-and-settings.md):
precedence order, validation timing, and the never-log-a-secret invariant.

## 5. References

- [Specification: config-and-settings](../../specifications/config-and-settings.md)
- [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [DW-014](../../docs/DEFERRED.md) — trigger and reversal
