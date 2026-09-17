# ADR-0023 — Caching Infrastructure (new taxonomy category)

- **Status:** Accepted
- **Date:** 2026-09-17
- **Supersedes:** —
- **Superseded by:** —

## Context

Phase 2 Track 2B studied 25 AI infrastructure repositories at pinned commits
([ADR-0021](0021-study-pipeline-architecture.md)). The pipeline proposed
`caching` in **14 of 25**, and the classifier found no taxonomy category to map
it onto.

Verified against charter §2's own scoping text, not the category-name list:
`data` covers *"ingestion, transformation, datasets + versioning, validation"*;
`retrieval` covers *"RAG, hybrid/vector/lexical/graph retrieval"*; `observability`
covers *"token/latency/cost accounting"*. Caching — reusing a computed result to
avoid recomputing it — is none of these. It is a distinct concern that several
categories would otherwise each reinvent.

**A correction this ADR records.** An earlier version of the pipeline's caching
rule matched a bare `store` fragment and reported `vector_stores/` and
`graph_stores/` as caching layers. That was a false positive: a vector store is
a retrieval index, not a cache. The rule now matches `cache`/`memoize` only, and
the 14-repository figure is from reports generated **after** that fix. This
matters because the count is the ADR's evidence.

## Decision

Add **`caching/` — Caching Infrastructure** as a taxonomy category, and record
the evidence as a `DISCOVERED` capability entry.

The category covers: response/embedding/result caches, cache-key derivation,
eviction policy, TTL and invalidation, persistent vs in-process caches, and
cache-aware cost control (avoiding a re-billed model call).

**Out of scope:** semantic caching of model responses as a *quality* technique
(that is an evaluation concern), and CDN/HTTP caching (`deployment`).

## Options considered and rejected

1. **Treat caching as part of `retrieval`.** Rejected: retrieval caching is one
   instance; `litellm` caches provider *responses* and `langfuse` caches
   *scores*, neither of which is retrieval. Filing it under retrieval would
   force two non-retrieval capabilities into the wrong category.
2. **Treat caching as part of `observability`.** Rejected: observability
   measures cost; caching reduces it. Conflating the measurement with the
   remedy would hide that they are separately adoptable.
3. **Treat caching as `primitives`.** Rejected for the same reason as
   [ADR-0022](0022-configuration-taxonomy-category.md): `primitives` is a
   `catalog/`-only container in this repository, not a subject area.
4. **Skip it as "not AI-specific".** Rejected, but this was the closest call.
   Caching is general software infrastructure, not AI infrastructure. What makes
   it in-scope here is the AI-specific form the studied projects actually
   implement: caching keyed on a *prompt plus model plus parameters*, where the
   avoided cost is a metered API call rather than CPU. If the entry is later
   built, it must be the AI-specific form or it does not belong here.
5. **Propose without an ADR.** Rejected: charter §12 requires the decision
   recorded in the same session it is taken.

## Consequences

**Positive.** Names a concern 56% of studied frameworks implement, and does so
with a real boundary established by an actual false positive rather than by
definition alone.

**Negative, stated plainly.**

- **The weakest of the three new categories.** §2's list is already long and
  caching is the one most plausibly argued to be generic. It is recorded with
  that reservation and a narrow scope, so a future session can reject the entry
  without having to first reconstruct why it was added.
- **The 14/25 figure counts directory and dependency evidence**, not
  implemented behaviour. Some are `cache/` directories that may be small or
  unused. This is stated in the reports; the ADR repeats it so the count is not
  read as "14 projects have a maintained cache".
- **Category-count growth** to 25 top-level entries (from 22), accepted for the reasons in
  ADR-0022.

## Evidence

- 14 of 25 studied repositories, from reports regenerated after the `store`
  false-positive fix.
- Taxonomy entry added: `response-cache` (`DISCOVERED`, `decision: pending`).
- Criterion: charter §2, §12, §14.
