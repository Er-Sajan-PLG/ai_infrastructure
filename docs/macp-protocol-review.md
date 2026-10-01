# MACP Amendments P1–P7 — Adversarial Review Record

> **Purpose.** This document preserves, verbatim, the adversarial review of
> the proposed MACP amendments P1–P7. It is the rationale record for every
> refinement integrated into `macp-protocol.md` (see Appendix A there).
> Do not "simplify" amended rules without re-reading this review — the
> refinements exist because the naive versions fail in the ways described
> below.
>
> **Verdict summary:** P1 accept w/ refinements · P2 accept w/ refinements
> (strongest) · P3 accept w/ refinements · P4 accept w/ refinements ·
> P5 accept principle, revise rule · P6 accept w/ schema tightening ·
> P7 defer. Ship P1+P3, P2+P4, P6, P5 — then evaluate residual failures
> before considering P7.

---

# 🔍 Rigorous Review of Proposed MACP Amendments (P1–P7)

I'm going to stress-test each proposal against: **logical soundness**, **failure modes it introduces**, **failure modes it fails to fix**, **real-world ergonomics**, and **interactions with the rest of the protocol**. I'll be adversarial where warranted.

---

## P1 — Shutdown Step 0: "Stop Working"

### Verdict: ✅ **ACCEPT with refinement**

### What it fixes (real)
This is diagnosing a genuine, severe pathology: **the "finalized" record is a lie if work continues after finalization**. The protocol as written has no re-entry barrier, so agents naturally drift into finalize → "oh one more thing" → finalize again → ad infinitum, each round silently invalidating the previous "final" state.

### What's strong about it
- The abort-and-restart semantic is **the only correct answer**. Half-measures ("update the summary too") would normalize the drift.
- It makes an invisible failure mode (silent re-work) **loud and expensive**, which is exactly how you kill a bad habit.

### Where it's weak / needs refinement
1. **"Any new finding aborts shutdown" is too strict.** A typo in your own session file prose should not restart the entire shutdown. The rule needs a scope boundary:
   - **Aborts shutdown:** any code change, any config change, any state file change *other than* the session file being finalized, any new commit touching repo content.
   - **Does NOT abort:** typo fixes in the session file being written right now, formatting of the shutdown summary itself.

2. **No cap on restart cycles.** An agent could legitimately get stuck in finalize→find→fix→finalize→find→fix. P2 addresses this for the verification loop, but P1 needs its own cap. Suggest: **3 shutdown restarts max per session.** Fourth attempt → halt, log `[NEEDS HUMAN]` in BLOCKERS.md.

3. **Doesn't address the root cause**, only the symptom. The root cause is agents declaring "done" prematurely — often because the user asked "are you done?" and the agent said yes to be agreeable. Consider adding to Section 2: *"Declare completion only when all plan items are checked off AND Section 3 validation passes. User satisfaction is not a completion signal."*

### Hidden interaction
P1 interacts with P3 (re-open transition). If shutdown aborts mid-way, is that a "re-open"? Needs clarification: **mid-shutdown abort is not a re-open; re-open applies only after a shutdown fully completed and REGISTRY was updated to COMPLETED.**

### Final judgment
**Accept, with the refinements above.** This is one of the two most important changes in the batch.

---

## P2 — Terminal Verification Loop

### Verdict: ✅ **ACCEPT, strongest proposal in the batch**

### What it fixes (real)
This encodes a **proven empirical result** (your cold-read caught 5+2 bugs). The protocol as written treats "I wrote the summary" as the end state, with no feedback loop confirming the summary matches reality. That's a trust-without-verify design, which fails deterministically given enough sessions.

### What's strong about it
- **Convergence argument is sound.** Each iteration strictly reduces discrepancies (because you fix what you find), so the loop terminates in finite steps for any finite set of discrepancies. The 3-iteration cap handles pathological cases where fixes create new discrepancies (which is itself a signal of deeper rot).
- **The "forbid new work in the loop" rule, cross-referenced with P1, is critical.** Without this, verification becomes just more work, which falsifies the thing being verified. The two proposals are co-dependent.
- **Grounded in evidence, not theory.** You tested it. It worked. That beats any amount of design reasoning.

### Where it's weak / needs refinement
1. **"Any discrepancy → fix" is ambiguous.** Some discrepancies are session-file errors (fix in session file), some are state file errors (fix in DASHBOARD/INDEX), some are reality errors (code or git state is wrong). The loop should classify:
   - **Record error** → fix the record, re-verify.
   - **Reality error** → this is a bug in your work. Fix it, which means re-entering work mode, which means P1 aborts shutdown. Explicit about this.

2. **"If three iterations don't converge, record in BLOCKERS.md" is right, but should be stronger:** also mark the session OUTCOME as `PARTIAL` or `FAILED`, not `COMPLETED`. A non-converging verification loop means the session did not actually complete, regardless of what code was shipped.

3. **No specification of what "re-read" means.** Is it a diff-based check? A cold cognitive re-read? Both? Specify at least:
   - Run `git log <base>..HEAD --oneline` and confirm every commit is in session file's commit list.
   - Run `git status` and confirm clean.
   - Re-read DASHBOARD "Active Agents" and REGISTRY — must match.
   - Re-read session summary — every claim must be checkable.

### Hidden interaction
This loop will **expose the ownership gaps that P4 addresses**. If ARCHITECTURE.md is rotted, the verification loop will find it, try to fix it, and the agent will realize they didn't know they owned that update. So **P2 without P4 produces an infinite loop of "found rot, don't know whose job it is."** These two proposals are a package.

### Final judgment
**Accept, with the refinements above. Non-negotiable pairing with P4.**

---

## P3 — Re-open Transition

### Verdict: ✅ **ACCEPT, this is a correctness fix, not a feature**

### What it fixes (real)
Diagnoses an **unrepresentable state** in the current protocol: "session was marked COMPLETED at 12:15 but work continued until 14:00." The files are forced to lie because there's no legal transition back. This is a classic "make illegal states unrepresentable" fix, which is one of the highest-leverage design moves available.

### What's strong about it
- Formal state machine thinking: `COMPLETED → ACTIVE` requires an explicit, timestamped, reasoned transition. No sneaking back.
- "Full shutdown re-executed afterward" closes the loop — you can't half-reopen.
- The dated "Re-opened: <reason>" entry creates an audit trail that explains why the session has non-linear timestamps.

### Where it's weak / needs refinement
1. **Why would an agent re-open rather than start a new session?** The protocol doesn't say. Needs a decision rule:
   - **Re-open same session** when: continuing the same objective, within same calendar day, no other agent has worked in between.
   - **Start new session** when: new objective, next day, or another agent's session is interleaved.

   Without this, agents will arbitrarily pick, which defeats the purpose.

2. **Reason field needs structure.** "Re-opened: forgot to add tests" is useless for audit. Suggest requiring:
   - What triggered the reopen (user request, self-review, cold-read finding, new discovery)
   - Why it couldn't wait for a fresh session
   - What's the delta from the "completed" state

3. **Doesn't address git state.** If you re-open, your branch may have been merged or others may have committed to it. The re-open transition should include a mandatory `git fetch && git log` check against your last session's commit list — if divergence exists, handle it before proceeding.

### Hidden interaction
This solves a problem that **P1 might otherwise paper over**. Without P3, P1's "abort shutdown → return to work" creates its own ambiguity (did shutdown ever happen?). With P3, the two proposals compose cleanly:
- P1: in-flight shutdown aborts, no state change needed, continue work.
- P3: shutdown fully completed, status is COMPLETED, re-opening requires transition.

### Final judgment
**Accept, with the refinements above. This is correctness, not polish.**

---

## P4 — State-File Ownership Table

### Verdict: ✅ **ACCEPT, mandatory companion to P2**

### What it fixes (real)
Diagnoses the **ownerless-file rot pathology** correctly. The current protocol lists state files but never says *which action triggers which file update*. This is a Conway's Law failure: no owner → no maintenance → inevitable rot. ARCHITECTURE.md rotting and ADR-0029 being lost in state/DECISIONS.md are not accidents — they're the predicted outcome of ownerless files.

### What's strong about it
- **Event-driven ownership is the correct model.** Not "update ARCHITECTURE.md periodically" (vague, skippable) but "ARCHITECTURE.md MUST be updated when structure changes" (triggered, verifiable).
- **The table makes it checkable.** You can mechanically ask "did any structural change happen this session? If yes, is ARCHITECTURE.md updated?" This is the foundation for P7.
- **Multiple files per event is correct.** ADR creation hitting both `docs/decisions/README.md` and `state/DECISIONS.md` recognizes that documentation lives in multiple places and all must be synced.

### Where it's weak / needs refinement
1. **The event list is probably incomplete.** Needs iterative expansion. Starter audit questions:
   - Dependency added/removed/upgraded → DEBT? ARCHITECTURE? session?
   - Test suite restructured → ARCHITECTURE? session?
   - CI/CD config changed → ARCHITECTURE? session?
   - Environment variable added → ARCHITECTURE? README? session?
   - Public API changed → ARCHITECTURE? DECISIONS (if breaking)? session?
   - Security-relevant change → DECISIONS? separate SECURITY.md?

   Suggest shipping P4 with a **"this table is incomplete by design; add rows when events occur that aren't covered, as part of session shutdown"** meta-rule.

2. **"Event" needs definition.** Is renaming a file a "structure change"? Is adding a new function to an existing module? The threshold matters:
   - **Low threshold** (every change is an event) → table becomes useless noise.
   - **High threshold** (only major changes) → rot returns.

   Suggest: **an event is anything that would make an existing claim in a state file become false or incomplete.** This is self-referential but testable.

3. **No conflict resolution for multi-event changes.** A single commit might trigger 4 file updates. If the agent updates 3 of 4, is the session complete? P2's verification loop would catch this, but P4 should say explicitly: **all triggered files must be updated in the same session that produced the event. Partial updates are failures.**

### Hidden interaction
P4 is a **precondition for P2 to work**. Without ownership rules, the verification loop finds rot and doesn't know what to do. With ownership rules, the loop finds rot, identifies the owner (which is "you, this session, because you did the triggering event"), and fixes it. **Ship them together or neither.**

### Final judgment
**Accept, with the refinements above. Non-negotiable pairing with P2.**

---

## P5 — Volatile-Data Ban

### Verdict: ⚠️ **ACCEPT WITH SIGNIFICANT REVISION — the diagnosis is right, the prescription is overreach**

### What it fixes (real)
The core observation is correct: **committed-count-as-truth rots the moment you look away**. "7 commits ahead" is not a fact — it's a snapshot that was true for one moment. Writing it down as prose creates a time bomb.

### What's strong about it
- Reframes records as **either command outputs (volatile) or commitments (durable)**. This is a useful mental model.
- "Last verified <time> via <command>" is a correct template: it tells the reader *when* and *how* to re-verify, rather than claiming eternal truth.

### Where it's wrong or overreaching
1. **"Never write exact test counts" throws out the baby.** Test counts are not useless — they're useful as **trend indicators** ("was 1100, now 1130: +30 new tests this session"). The problem isn't the number; it's treating the number as current-state proof rather than historical delta.

   **Revised rule:** Test counts, commit counts, line counts are permitted as **deltas or historical markers** ("+30 tests added this session," "at session start: 1100 passing"). They are forbidden as **current-state claims** ("we have 1130 passing tests") without the verification suffix.

2. **"Bare timestamps as freshness evidence" conflates two things.** A timestamp on an action ("committed at 15:30") is a durable historical fact. A timestamp on a state ("DASHBOARD last reconciled at 15:30") is freshness evidence only *if* nothing has happened since. The rule should distinguish:
   - **Action timestamps** (always allowed): "Decision made at 15:30 UTC."
   - **State timestamps** (require verification context): "DASHBOARD current as of commit abc123, verified via `git log -1`."

3. **The rule as stated will produce defensive mush.** Agents will stop writing anything concrete to avoid rule violation, leading to vague prose that's technically compliant but informationally dead. The rule needs a **positive form**: "when you reference a count or state, cite the command that produced it, so a future reader can re-verify."

### Where it's weak
The underlying principle — **records should be reproducible, not asserted** — is more fundamental than the specific rule. Suggest leading with the principle, then giving the volatile-data ban as one application:

> *Principle: Any claim in a record must be either (a) a durable historical fact that cannot change, or (b) a current-state claim paired with the command and timestamp that would reproduce it. Unverifiable assertions rot.*

### Hidden interaction
P5 overlaps with P6 in spirit (verify the record, not just the code), but P5 is about *form* (how to write) while P6 is about *process* (when to check). They complement; they don't conflict.

### Final judgment
**Accept the principle, revise the rule. The ban-based framing will produce protocol-compliant garbage. The principle-based framing produces the behavior you actually want.**

---

## P6 — Record Verification in Section 3

### Verdict: ✅ **ACCEPT, cheapest high-value fix in the batch**

### What it fixes (real)
Section 3 verifies the code's correctness but **not the record's correctness**. The record is the actual handoff deliverable. A one-line checklist addition that forces re-reading the session file against reality is enormous ROI.

### What's strong about it
- **Minimal protocol change, maximum behavior change.** One checkbox adds a habit.
- **Fits the existing structure.** Section 3 is already a checklist. Adding a line is low-friction.
- **The specified checks are the right ones:**
  - Commit list complete (catches "I forgot to log that commit")
  - Statuses current (catches stale IN-PROGRESS markers)
  - No checked-off TODOs for finished work (catches drift between plan and execution)
  - Header matches REGISTRY (catches identity/branch desync)

### Where it's weak
1. **"Header matches REGISTRY" assumes a session file header schema.** The current protocol doesn't rigorously specify what the session file header contains. Needs a tightening: session files MUST begin with a metadata block containing [agent, branch, started, status, base commit] and these fields MUST match REGISTRY entries. Without the schema, "matches REGISTRY" is unenforceable.

2. **Doesn't force cold-read.** The agent that wrote the session file is the worst reader of it (confirmation bias). The strongest version of this rule would require: **re-read the session file after a context break** (minimum: do 30 seconds of unrelated protocol work, then re-read). But this may be too fiddly to enforce; the checklist line is a reasonable floor.

### Hidden interaction
P6 is the **manual version of P2's verification loop**. P6 happens pre-shutdown (Section 3 is validation), P2 happens post-shutdown (terminal loop). Both are needed because:
- P6 catches issues before you declare "ready to shut down."
- P2 catches issues the shutdown itself introduced (new commits, status changes).

### Final judgment
**Accept as-is, with the session file header schema tightening.** Easiest win in the batch.

---

## P7 — Machine-Checked State Drift (Optional)

### Verdict: ⚠️ **DEFER, with strong agreement on the sequencing argument**

### What's right about this proposal
- **The sequencing argument is correct and important.** "Discipline fixes precede mechanical ones" is good design philosophy. Tooling that enforces undisciplined behavior produces compliant-looking rot ("passing checks on empty records"). This is the mypy-overrides pathology: suppression becomes the goal, and the suppressed problem persists.
- **The specific checks proposed are well-chosen** — they map 1:1 to the empirically observed failures.

### Where it's weak
1. **"Thin-but-passing records are worse than honest rot" — true but under-argued.** The real reason to defer is: **tooling encodes assumptions about the protocol, and the protocol just changed significantly.** Shipping P1–P6, letting them run for 20+ sessions, learning what fails despite the discipline fixes, *then* automating what remains, produces a checker that checks real problems. Shipping the checker now encodes guesses.

2. **"Pre-commit wiring" is dangerous without a bypass.** State updates sometimes need to happen in a dirty-record state (mid-emergency, blocker documentation, etc.). A pre-commit hook that rejects commits violating state rules will train agents to either (a) `--no-verify` reflexively, or (b) write minimal records to pass the hook. Both are worse than no hook.

3. **The checker's scope is unclear.** Does it check that DASHBOARD was updated, or that it was updated *correctly*? The former is easy; the latter is undecidable in general. The proposal should specify this is a **completeness checker** (did you touch the required files?) not a **correctness checker** (are the contents right?). Only humans/agents can judge correctness.

### Final judgment
**Defer. Agree with the author's own sequencing argument. Revisit after P1–P6 have been exercised for a non-trivial period and the actual residual failures are known.**

---

## Cross-Cutting Analysis

### Dependency graph of proposals

```
P4 ──┐
     ├──► P2 (verification needs ownership rules to resolve findings)
P1 ──┤
     └──► P3 (shutdown abort semantics need re-open semantics for completeness)
P5 ──► independent, principle fix
P6 ──► independent, checklist fix
P7 ──► depends on P1–P6 being settled
```

**Ship order:** P1 + P3 together (shutdown semantics), P4 + P2 together (ownership + verification), P6 (checklist), P5 (principle), then evaluate P7.

**Do not ship P4 without P2.** Ownership rules without a loop that enforces them become documentation nobody reads.

**Do not ship P2 without P4.** Verification without ownership becomes "found rot, no idea whose job it is."

### Failure modes the batch does NOT address

1. **Context window pressure causing documentation collapse.** When agents run out of context mid-session, record quality degrades first (because it feels optional). The protocol has no "if you're context-constrained, stop and hand off" rule. Observed in practice.

2. **User-induced protocol violation.** When the user says "just do X quickly, skip the protocol," there's no rule for the agent. Options: refuse, comply, comply-and-document. Current protocol is silent, which means agents will comply silently, which is the worst option.

3. **Protocol version drift.** If AGENTS.md is updated mid-session, the agent is now operating under a different protocol than the one they started with. No rule covers this.

4. **The "boring update" skip.** When a session is small (one-line fix), agents will skip state updates as disproportionate. The protocol needs a **minimum viable session record** for small changes, or agents will route around the rules for trivial work and then forget to re-engage for substantial work.

These are not reasons to reject P1–P6 — they're the next-batch backlog.

### The meta-observation

All six accepted proposals share one shape: **they close feedback loops that the original protocol left open**. Each of them adds a point where reality is checked against the record:

| Proposal | Loop closed |
|---|---|
| P1 | Finalize claim ↔ actual stopping |
| P2 | Shutdown summary ↔ repo reality |
| P3 | COMPLETED status ↔ continued work |
| P4 | Event occurrence ↔ file update |
| P5 | Written claim ↔ reproducibility |
| P6 | Session file ↔ git truth |

This is diagnostic. The original protocol specified *actions* without *verifications*, which is why it rotted. The amendment batch's unifying principle is: **every assertion needs a verifier, every state needs a transition, every file needs an owner.**

The amendments as a batch upgrade the protocol from an **honor system** to a **verified system**. That's the right direction.

---

## Final Recommendation

| Proposal | Decision | Priority |
|---|---|---|
| P1 — Shutdown Step 0 | ✅ Accept with refinements | HIGH, ship with P3 |
| P2 — Verification Loop | ✅ Accept with refinements | HIGH, ship with P4 |
| P3 — Re-open Transition | ✅ Accept with refinements | HIGH, ship with P1 |
| P4 — Ownership Table | ✅ Accept with refinements | HIGH, ship with P2 |
| P5 — Volatile Data | ⚠️ Accept the principle, revise the rule | MEDIUM |
| P6 — Record Verification | ✅ Accept with schema tightening | LOW-effort, HIGH-value |
| P7 — Machine Checks | ⏸️ Defer per author's own reasoning | After P1–P6 proven |

**Ship P1+P3 and P2+P4 as two coordinated updates. Then P6. Then P5. Then evaluate residual failures before considering P7.**

The author of these proposals understands the protocol's failure modes better than the protocol's original design did. The proposals should be adopted with the refinements noted, and the author's sequencing instincts (defer P7) should be respected.
