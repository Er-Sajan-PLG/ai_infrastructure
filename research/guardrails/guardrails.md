# Research Record: Guardrails & Output Validation

- **Capability:** `guardrails` (category: guardrails)
- **Status:** `UNDERSTOOD` — deterministic half implemented per ADR-0038 (Phase 5A.2 of the implementation plan). Model-backed classifiers remain deferred (DW-015).
- **Date:** 2026-10-22
- **Decision:** see [ADR-0038](../../docs/decisions/0038-guardrails-deterministic.md) *(IMPLEMENT, deterministic half)*
- **Sources:** [ADR-0031](../../docs/decisions/0031-guardrails-category.md), [convergence report](../../docs/discovery/2026-10-08-convergence.md), study pipeline reports (`study_pipeline/studied_repos/`), [TAXONOMY.md](../../TAXONOMY.md) §4

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. Evidence from the study corpus

**FACT.** 10 of 25 studied repositories independently proposed `guardrails`
(40%) — named: `agno`, `ai`, `haystack`, `langfuse`, `litellm`, `mastra`,
`openai-python`, `phidata`, `semantic-kernel`, `SWE-agent`
([ADR-0031](../../docs/decisions/0031-guardrails-category.md),
[convergence report](../../docs/discovery/2026-10-08-convergence.md)).

**FACT.** The category was adopted because the classifier had nowhere to put
the pattern: `safety/ (+governance/)` covers governance, policy, and
guardrails for agent *actions*, while this is output-validation machinery
between a model response and its consumer.

**OBSERVATION.** The convergent surface spans two kinds of mechanism:
deterministic validation (schema, format, policy checks) and model-backed
classification (moderation/safety models). These have completely different
prerequisites — the second needs a metered model call path this repository
does not have.

## 2. The problem, stated without reference to any implementation

> Before model output reaches a user, a tool call, or another system, decide
> whether it is allowed — and say why when it is not.

**DESIGN OPINION.** The trust-boundary framing is load-bearing. A "guardrail"
applied in a context with no boundary (a test harness asserting on its own
fixtures) is not a guardrail; it is ceremony. This is why the deferral's
trigger is a boundary, not a feature.

## 3. What was not studied, and why that is acceptable here

**OBSERVATION.** No implementation's validation policy, rejection semantics,
or classifier integration was reviewed in depth.

**INFERENCE.** Not owed for a deferral: the validation policy (what to
reject, rewrite, or allow) must be derived from the first real boundary, and
there is none — model output in this repository is consumed only by tests,
benchmarks and examples, and no live model calls are made
([DW-016](../../docs/DEFERRED.md)). Inventing the policy now would be
guessing at requirements that do not exist.

**OBSERVATION.** The taxonomy entry's security note stands: a guardrail is a
trust boundary itself and must not become a bypass for prompt injection.

## 4. Why the decision is DEFER

See [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) §Decision 4.
Trigger: the first integration or entry where model output reaches a
user-facing boundary or triggers side effects (tool invocation, config
change) rather than test assertions.

**DESIGN OPINION.** When the trigger fires, the first design questions are
pinned in [the specification](../../specifications/guardrails.md): the
deterministic validators come first, modeled on the error taxonomies already
in the catalog; model-backed classifiers remain out of scope until a metered
call path exists (see [DW-015](../../docs/DEFERRED.md)).

## 5. References

- [Specification: guardrails](../../specifications/guardrails.md)
- [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [DW-016](../../docs/DEFERRED.md) — trigger and reversal
