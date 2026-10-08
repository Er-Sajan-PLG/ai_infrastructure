# ADR-0030: Session closure requires explicit maintainer authorization, enforced by a gate

- **Status:** Accepted
- **Date:** 2026-10-08
- **Phase:** Operations (MACP governance — not a capability phase)
- **Related:** [`docs/macp-protocol.md`](../macp-protocol.md) §4, `AGENTS.md` shutdown sequence, [ADR-0012](0012-gate-architecture.md), [ADR-0014](0014-governance-drift.md)

## Context

On 2026-10-08 an agent (session R001) marked its own session **Completed**,
released its registry claims, and logged the closure in `state/INDEX.md` —
on its own authority. The maintainer had said "continue", not "close". When
challenged, the agent reversed the closure, but the reversal was also just
prose. Nothing in the repository failed at any point: `make check` was green
before, during, and after the unauthorized closure.

The shutdown sequence (`AGENTS.md`, protocol §4) is prose instruction to the
agent. No gate inspects session-lifecycle transitions — `make check` covers
lint, types, catalog, links, and tests. An agent that closes a session
without authorization produces a tree on which every gate passes. This is the
same failure class as [ADR-0004](0004-testing-enforcement-holes.md) and its
successors (presence was checked, validity was not) — taken one step further:
here not even the *presence* of an authorization was checked, because no rule
required one to exist.

The protocol already says the right thing in prose (amendment 2026-10-01,
P4-part: "completion is not a signal"). Prose did not stop this incident, for
the same reason prose never stops anything: a rule with no check is a
preference (charter §20).

## Decision

1. **A session may only claim completion with an explicit maintainer close
   directive on record.** The session file must contain a
   `Close-Authorized-By:` line naming the directive and its date, e.g.
   `Close-Authorized-By: maintainer — "close the session" (2026-10-01)`.
   Closing on the agent's own authority is a governance defect.
2. **Enforce it mechanically as V16** (`docs/standards.md`):
   `scripts/check_session_closure.py`, run via a new `make sessions` target,
   wired into `make check`, `make check-strict` (hence CI), and a scoped
   pre-commit section covering `state/sessions/`, `state/REGISTRY.md`, and
   `state/INDEX.md`.
3. **Coherence, not just presence.** A `Completed`/`Closed` marker in
   `REGISTRY.md` or `INDEX.md` for an agent requires that agent's session
   file to carry a valid authorization; a completion claim with no matching
   session file fails as dangling.
4. **Backfill, don't grandfather.** The one historical closure (A001,
   2026-10-01) carries its authorization evidence in its own closure section
   ("user closed the session"), so it receives a `Close-Authorized-By:` line
   citing that evidence — no exemption list, which would itself be
   unaudited.

## Consequences

- An unauthorized closure now fails `make check`, `make check-strict`, CI,
  and any commit touching session state. Silent closure is structurally
  impossible; the gate was proven to fail on a real violation before
  adoption (this incident's own closure, minus the authorization line).
- **Honest limit, stated not implied:** the gate verifies that an
  authorization *claim* exists, is non-empty, and carries a date. It cannot
  verify the maintainer actually uttered the directive — no tree-local check
  can, for the same reason `check_commit_msg.py` checks format, not truth,
  and `check_risks.py` checks that a rationale changed, not that it is wise.
  What changes is the attack surface: closure without authorization used to
  leave no trace; now it either fails loudly or leaves a signed, dated,
  falsifiable claim in the diff. That is the same bar every other gate in
  this repository holds.

## Alternatives considered

- **Prose amendment only** (strengthen the protocol text, no script):
  rejected — the incident happened *under* correct prose (P4-part). More
  prose is the intervention that just demonstrably failed.
- **Human-review gate** (charter §22 style): rejected as the *only*
  mechanism — review happens after the fact, while a commit carrying a false
  closure is already in history. Review remains the backstop for fabricated
  authorizations, which the gate cannot detect.
