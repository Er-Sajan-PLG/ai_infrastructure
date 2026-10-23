# ADR-0042: Public API Namespace Policy (Hybrid)

**Status:** Accepted
**Date:** 2026-10-23
**Drivers:** Phase 3 of the stabilization sequence; audit finding F-namespace;
charter §14 (public API), §31 (independence)

## Context

`ai_infrastructure/__init__.py` is a **flat** re-export of 175 symbols from
13 capabilities. Three capability-level names collide at the root:
`Clock`, `SystemClock` (execution-trace-recorder vs rate-limiting) and
`RateLimitError` (model-provider-abstraction vs rate-limiting). The shim
resolves each collision by **omitting** one owner from the root export; the
omission is **undocumented**. Capability-level imports still work
(`from rate_limiting import RateLimitError`).

This works at 13 capabilities. It does not scale: the next collision on any
common name (`run`, `chat`, `Provider`, `Memory`, `Evaluator`, `Validator`,
`Tool`, `Error`) silently drops a public symbol and breaks a consumer. The
flat root also contradicts the peer-capability model: independent capabilities
are forced through a single centralized export surface that must know about
every one of them.

## Decision

**Adopt a hybrid namespace policy (Option E), staged:**

1. **Canonical API is namespaced by capability domain**, not by capability
   id and not flat:
   ```python
   from ai_infrastructure.tools import ToolRegistry
   from ai_infrastructure.models import ModelProvider
   from ai_infrastructure.memory import VectorStore
   from ai_infrastructure.reliability import RateLimitError
   ```
   The domain groups are stable (`tools`, `models`, `memory`, `retrieval`,
   `agents`, `observability`, `protocols`, `deployment`, `guardrails`,
   `reliability`, `evaluation`). Collisions are impossible because each
   capability owns its own subpackage.

2. **The flat root keeps a small, curated set of convenience exports** for the
   most common primitives (`ToolRegistry`, `ModelProvider`, `VectorStore`,
   `BasicRagPipeline`, `ReactAgentLoop`, `ExecutionTraceRecorder`, ...). These
   are **aliases**, not a second API. They are listed explicitly in
   `__init__.py` with the source capability named in a comment.

3. **No code rewrite now.** The flat shim stays as the implementation of (2)
   until the first consumer (Phase 4-6) proves the namespaced path. The
   `sys.path` shim in `ai_infrastructure/__init__.py` is retained for
   backwards compatibility during the transition.

4. **Collision policy:** a new capability may not introduce a root-level name
   that collides with an existing one. On collision, the new capability's
   symbol is available only via its namespace; the root convenience alias is
   added only if a maintainer explicitly chooses it (recorded in this ADR's
   successor).

5. **Document the existing omissions.** `Clock`, `SystemClock`,
   `RateLimitError` (rate-limiting's) are not re-exported at root; this is
   now stated in `__init__.py` and in the public-API section of
   `docs/architecture.md`.

## Options Considered

| Option | Collision resistance | Discoverability | Packaging | Verdict |
|---|---|---|---|---|
| A. Flat root (`from ai_infrastructure import X`) | Poor (fails at ~30 caps) | High | Single dist | Rejected — does not scale |
| B. Namespaced by domain (`ai_infrastructure.tools`) | Excellent | Good | Single dist | Accepted as canonical |
| C. Capability modules (`ai_infrastructure.tool_registry`) | Excellent | Medium | Single dist | Rejected — leaks capability ids into the public path |
| D. Separate distributions per capability | Excellent | Low | Many dists | Deferred — consumer-driven (Phase 5) |
| E. Hybrid (B canonical + curated flat aliases) | Excellent | High | Single dist | **Accepted** |

## Consequences

- No immediate code change; this ADR records policy. The migration to (1) is
  a follow-up ADR once a consumer validates the namespaced path.
- `ai_infrastructure/__init__.py` gains a documented collision list.
- Future capability additions must check for root-name collisions before
  merging (a lint/check is a follow-up).
- Per-capability distribution (Option D) remains an open question gated on
  Phase 4-6 consumer evidence.

## Alternatives considered

- Rewriting `__init__.py` now — rejected: violates the "no rewrite before
  consumer proof" rule; the policy is the deliverable of this phase.
- Keeping flat root indefinitely — rejected: collision risk is concrete and
  already bitten (3 omissions, undocumented).

## Charter references

§14 (public API), §31 (independence), §4 (decide before building).

## Taxonomy impact

None — policy only. Every capability's `depends_on` is unaffected.
PY
echo "written"