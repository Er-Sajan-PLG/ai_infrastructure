# ADR-0035: Phase 5 Decisions on the Five Discovered Capabilities

**Status:** Accepted
**Date:** 2026-10-16
**Drivers:** Phase 5 Sustain — WP5 of session OC1; charter §8 (DECIDE), §24 (re-derive priority from evidence)

## Context

Phase 2 Track 2B (25 repositories studied, ADR-0021 pipeline) added three
taxonomy categories — `config/`, `caching/`, `agent-config/` (ADR-0022–0024)
— and recorded one `DISCOVERED` capability for each: `config-and-settings`,
`response-cache`, `agent-instruction-files`. Phase 3 convergence detection
added `guardrails/` and `reliability/` (ADR-0031, ADR-0032) with the
`guardrails` and `rate-limiting` entries.

All five were recorded with `decision: pending` — deliberately, because
"found in N of 25 repositories" is evidence the pattern EXISTS, not that it
is worth building here (charter §24). WP5 requires each to receive a recorded
decision with rationale, and requires implementation of the medium-priority
items only if the post-WP4 budget allows; otherwise DEFER with triggers.

Priority re-derived from evidence (charter §24) against the repository as it
exists today, not as an imaginary large system:

- The catalog has zero runtime dependencies and every entry takes explicit
  constructor arguments; no entry resolves settings from the environment.
- No code path makes a metered or remote model call: every model interaction
  under test is a scripted double, and `integrations/llm_http_transport` is
  documented offline-verified ("live vendor compatibility has not been
  verified").
- No entry delivers model output to end users; the only consumers of output
  are tests, benchmarks and examples.
- The one queue item with an existing consumer (`retrieval`:
  `basic-rag-pipeline`) was decided and implemented in ADR-0034; nothing in
  the catalog depends on any of these five.

## Decision

One ADR carries all five decisions: they were taken together, in one work
package, against one evidence base. Each capability remains individually
citable below and in the taxonomy.

1. **`config-and-settings` — DEFER** (DW-014).
   A settings layer is justified by the consumers it resolves configuration
   for. There are none: every entry takes constructor arguments, and the only
   environment read in `catalog/` is an opt-in example (scanner quickstart).
   Precedence machinery built with no reader cannot be exercised against a
   real requirement, and its classic failures (logging resolved secrets,
   wrong precedence) would be discovered by its first real user. Trigger and
   reversal recorded in DW-014.

2. **`response-cache` — DEFER** (DW-015).
   A cache protects a billed network call; no such call exists in this
   repository. More importantly, the correctness property — the key must
   include every input that changes the answer — cannot be designed against
   imaginary callers. A cache built now would be a guess about what varies
   between requests, which is exactly the failure the taxonomy entry's own
   security note warns about. Trigger and reversal recorded in DW-015.

3. **`agent-instruction-files` — DOCUMENT**.
   This is a repository practice, not a runtime component. The pattern is
   evidenced (AGENTS.md in 18/25 studied repositories) and this repository
   itself already instantiates it (`AGENTS.md`, docs, skill conventions).
   There is no artifact to build in the catalog that would not be speculative
   tooling (linters, cross-tool syncers) with no second consumer. Decision
   legend (charter §8): DOCUMENT means researched and recorded, not built.

4. **`guardrails` — DEFER** (DW-016).
   Guardrails are meaningful at a trust boundary: untrusted model output
   flowing toward a user, a tool call, or another system. No such flow exists;
   output is consumed only by tests, benchmarks and examples, so the
   validation policy would be invented rather than derived. The model-backed
   half of the space additionally needs a live classifier surface this
   repository deliberately does not have. Trigger and reversal recorded in
   DW-016 (deterministic validators first; classifiers stay out of scope).

5. **`rate-limiting` — DEFER** (DW-017).
   Backoff, limiting and circuit breaking manage a remote dependency's
   failure and quota behavior; there is no remote dependency. Their parameters
   (window sizes, retry budgets, breaker thresholds) would be invented. It
   would also contradict a recorded design decision:
   `specifications/basic-rag-pipeline.md` (D-4) assigns retry responsibility
   to the caller, and the provider error taxonomy already carries the
   `retryable` distinctions a future policy needs (ADR-0007 D-4). Trigger and
   reversal recorded in DW-017.

The four deferrals are recorded in `docs/DEFERRED.md` with the measurable
current fact, the trigger, and the reversal. All five taxonomy entries move
from `DISCOVERED` to `DECIDED`, since DEFER and DOCUMENT are recorded
decisions, not omission (charter §8).

Because the lifecycle model requires the DESIGNED artifact before a
DECIDE-stage claim, each capability also gains a research record
(`research/<category>/`) and a **deferral specification**
(`specifications/<id>.md`) that pins the design questions the trigger will
need — precedence, key derivation, validation policy, retry ownership — so
the reversal is a planned step rather than a rediscovery. None gains an
implementation artifact; none is owed one until its trigger fires. `make
status` surfaced this requirement during WP5 and the artifacts were added in
the same work package rather than weakening the claim.

## Consequences

- The taxonomy's map of the ecosystem keeps all five entries; nothing is
  removed or rejected. Each now says what was decided and why.
- Five research records and five deferral specifications are added, so no
  capability claims `DECIDED` without the artifacts that stage requires
  (charter §4: never claim a stage the artifacts cannot back).
- Four new deferred-work entries (DW-014 … DW-017) each name a measurable
  trigger. `scripts/check_deferred.py` reports possible trigger fires, and
  `review_by: 2027-10-16` forces re-evaluation within a year.
- Until a trigger fires, no work is owed on these capabilities. When one
  fires, the register's `reversal` field is the starting point — the
  reasoning does not have to be re-derived.
- `make status` stages move from `DISCOVERED ×5` to `DECIDED ×5`; the
  capability count is unchanged.

## Evidence

- `docs/discovery/2026-10-08-convergence.md` — guardrails 10/25,
  rate-limiting 6/25.
- Phase 2 Track 2B reports (`study_pipeline/studied_repos/`) — config 15/25,
  caching 14/25, AGENTS.md 18/25.
- `integrations/llm_http_transport/README.md` — "live vendor compatibility
  has not been verified"; "offline by default; no network call".
- `catalog/models/model_provider/errors.py` — retryable distinctions already
  carried (ADR-0007 D-4).
- `specifications/basic-rag-pipeline.md` D-4 — retry ownership with the
  caller.

## Rejected alternatives

- **IMPLEMENT `guardrails` and `rate-limiting` now** (both marked medium).
  Rejected: neither has a consumer, and building both to TESTED against
  invented requirements would create unfalsifiable scope. Priority "medium"
  justifies the taxonomy leaves they already have, not premature code
  (charter §24: the smallest thing that proves the pattern).
- **REJECT `guardrails` and `rate-limiting`.** Rejected: both are real
  production concerns with cross-repo evidence; REJECT would claim the
  patterns themselves are unjustified, which the evidence does not support.
  They are early, not wrong.
- **DOCUMENT for all five.** Rejected: DOCUMENT means "researched, don't
  implement" for patterns this repository has decided never to need. The four
  deferred capabilities become valuable the moment a consumer exists, which
  is precisely DEFER's definition (charter §8).
- **Record the decisions only in `docs/discovery/review/*.md`.** Rejected:
  those documents are generated category-review proposals and are regenerated
  by `make review`; hand-recorded decisions there would be destroyed and
  would mismatch the generated content. Decisions live in ADRs (charter §12)
  and the deferred register (ADR-0020).
- **Five separate ADRs (0035–0039).** Rejected: the five decisions share one
  evidence base and were taken together in one work package; five
  near-identical documents would add noise without adding traceability. Per-
  capability sections keep each decision individually citable.
