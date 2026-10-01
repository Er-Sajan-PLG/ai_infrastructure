# MACP — Multi-Agent Coordination Protocol

> **Canonical source.** This document is the single authoritative text of the
> Multi-Agent Coordination Protocol. `AGENTS.md` points here; summaries
> elsewhere are non-normative. Amendments are integrated inline, each marked
> with its proposal ID, and recorded in Appendix A with rationale pointers.
>
> **Version history:** 2026-10-01 — initial capture of the protocol text plus
> amendments P1–P6 (refined per adversarial review; see
> `macp-protocol-review.md`). P7 deferred — see Appendix A.

You are operating under MACP (Multi-Agent Coordination Protocol) — a disciplined, state-driven workflow that enables multiple AI agents to work on the same repository without conflicts, context loss, or stepping on each other's work.

Read this protocol fully before taking any action. If any rule here conflicts with other instructions, this protocol wins unless the user explicitly overrides it.

═══════════════════════════════════════════════════════════════
                    CORE PHILOSOPHY
═══════════════════════════════════════════════════════════════

You are stateless. The repository is not. Other agents have worked here before you, and others will work here after you. Your job is not just to complete the task — it's to leave a perfect record so the next agent can continue seamlessly.

Three unbreakable rules:
1. ALWAYS start by reading state. NEVER assume you know the current situation.
2. ALWAYS log your work in real-time. NEVER wait until the end to document.
3. ALWAYS end clean. NEVER leave uncommitted changes, broken state, or ambiguous handoffs.

═══════════════════════════════════════════════════════════════
                 THE STATE DIRECTORY STRUCTURE
═══════════════════════════════════════════════════════════════

All coordination happens through a `state/` directory at the repo root:

state/
├── DASHBOARD.md          # Executive summary — ALWAYS read first
├── REGISTRY.md           # Who's actively working and what files they own
├── INDEX.md              # Searchable log of all past sessions
├── ARCHITECTURE.md       # Current system architecture (living document)
├── DECISIONS.md          # Architecture Decision Records
├── DEBT.md               # Technical debt tracker
├── BLOCKERS.md           # Active blockers and dependencies
├── sessions/             # One file per agent session (your workspace)
├── plans/                # Active plans (deleted when done)
├── conflicts/            # Documented conflicts needing coordination
└── archive/              # Old sessions compressed by month

If this directory does not exist, you must create it via the Bootstrap Protocol (Section 7 below).

═══════════════════════════════════════════════════════════════
              SECTION 1: STARTUP SEQUENCE (MANDATORY)
═══════════════════════════════════════════════════════════════

Before you do ANY work, execute these steps in order:

STEP 1 — Git Reconnaissance
  Run (or request to run):
    git status
    git branch -vva
    git log --oneline -10
    git stash list
    git fetch --all

  Confirm:
    □ Working tree is clean (if not, document why)
    □ You know which branch you're on
    □ No unresolved merge conflicts exist
    □ You have the latest from remote

STEP 2 — Check if state/ directory exists
  IF state/ DOES NOT EXIST → Jump to Section 7 (Bootstrap Protocol)
  IF state/ EXISTS → Continue to Step 3

STEP 3 — Read DASHBOARD.md
  This gives you the full picture in <60 seconds:
    • What's the current state of the project?
    • Which agents are active right now?
    • What are the critical alerts and blockers?
    • What was recently completed?

  Check the "Last Reconciled" timestamp at the top:
    • <24h old → Trust it, proceed
    • 24-48h old → Verify against git log before trusting
    • >48h old → STALE. You must reconcile DASHBOARD.md before working
                 (read recent session files and rebuild it)

  Also confirm the checked-out branch matches DASHBOARD's Branch field.
  On mismatch, HALT: either check out the stated branch or reconcile the
  dashboard first. Never proceed with git and the record disagreeing about
  where you are.

STEP 4 — Read REGISTRY.md
  Identify:
    • Who else is active on this repo right now
    • Which files/directories they have claimed ownership of
    • Whether your intended work overlaps with their claims

  File ownership rules:
    • If another ACTIVE agent owns files you need to modify → STOP.
      Either coordinate (add note to their session file), choose a
      different approach, or wait.
    • If owner is INACTIVE (>24h) → You may claim ownership.
    • Shared files (config, package.json, etc.) require a
      [COORDINATION] note in both session files.

STEP 5 — Check BLOCKERS.md (if it exists)
  Confirm your task is not blocked by something upstream.
  Confirm your task does not block another agent's work.

STEP 6 — Targeted History Reading via INDEX.md
  Search INDEX.md by keyword or file path relevant to your task.
  Read ONLY the 2-3 most relevant past session files.
  DO NOT read every session file — that wastes your context window.

STEP 7 — Read ARCHITECTURE.md and DECISIONS.md (conditionally)
  • Only read ARCHITECTURE.md if your task touches system structure
  • Only read DECISIONS.md if you're about to make a design choice
    (someone may have already decided it)

STEP 8 — Register Yourself
  Create your session file:
    state/sessions/YYYYMMDD-HHMM-<AGENT-ID>-<short-slug>.md

  Example: state/sessions/20250614-1530-C7A2-fix-login-bug.md

  Add yourself to REGISTRY.md with:
    • Your agent ID (invent one: 4 alphanumeric characters)
    • Your model/type (e.g., "Claude 3.5 Sonnet")
    • Your branch
    • Your task (one line)
    • Current UTC timestamp
    • Files/directories you claim ownership of

STEP 9 — Create a Plan Entry
  Add state/plans/agent-<YOUR-ID>-<slug>.md with:
    • Objective
    • Scope (what's in and out)
    • Approach (step by step)
    • Risks and mitigations
    • Rollback strategy
    • Success criteria

Only after all 9 steps are complete may you begin actual work.

═══════════════════════════════════════════════════════════════
             SECTION 2: DURING WORK (LIVE LOGGING)
═══════════════════════════════════════════════════════════════

While working, maintain a running log in YOUR session file. Write ONLY to your own session file during active work. Do not touch DASHBOARD.md, REGISTRY.md, or INDEX.md until shutdown.

Log every significant event using these tags:

  [START]         — Beginning a work phase
  [PROGRESS]      — Completed a milestone
  [DISCOVERY]     — Found something unexpected
  [PIVOT]         — Changing approach from the original plan
  [DECISION]      — Chose between alternatives (document rationale)
  [BLOCKER]       — Cannot proceed, need resolution
  [DEBT]          — Introducing known technical debt
  [BUG FOUND]     — Found unrelated bug (log it, don't fix unless blocking)
  [SECURITY]      — Security-relevant consideration
  [SCOPE EXPANSION] — Doing something beyond original plan (must justify)
  [DISCREPANCY]   — State files don't match reality
  [COORDINATION]  — Need to notify or sync with another agent

Example entries:
  `15:45` [DISCOVERY] Found that auth.ts exports changed in last session.
          Adjusted my refactor to preserve backward compatibility.
  `16:12` [PIVOT] Redis approach won't work — Redis isn't in the stack.
          Switching to DB-backed solution.
  `16:30` [COORDINATION] Modified shared config.ts. Notified agent B3K1
          via note in their session file.

Scope discipline:
  • If a "quick fix" reveals a deeper issue → log [BUG FOUND], stay focused.
  • If you must expand scope → log [SCOPE EXPANSION] with justification.
  • Never silently refactor unrelated code.
  • Never fix unrelated bugs unless they block your current work.

> **Amendment 2026-10-01 (P4-part): completion is not a signal.** Declare
> completion only when all plan items are checked off AND Section 3
> validation passes. User satisfaction ("looks good") is not a completion
> signal — agreeableness is not verification.

### State-file ownership (Amendment 2026-10-01, P4)

Every state file has event triggers. When the event occurs in your session,
you own the update — in the same session, not a later one. Partial updates
(all triggered files except one) are failures, caught by the terminal
verification loop (Section 4).

| Event in your session | File(s) you MUST update |
|---|---|
| Capability status changed | `TAXONOMY.md` (repo), DASHBOARD.md, your session file |
| ADR created | `docs/decisions/README.md` (repo) AND `state/DECISIONS.md` |
| Repository structure changed | `state/ARCHITECTURE.md` |
| Debt found or accepted | `state/DEBT.md` |
| Blocker appears or clears | `state/BLOCKERS.md` |
| Commits landed | Your session file's commit list |
| Session ends | INDEX.md entry, REGISTRY.md status, DASHBOARD.md reconcile |

An event is anything that would make an existing claim in a state file
become false or incomplete. When in doubt, update — a redundant accurate
line costs nothing; a missing update rots silently.

This table is incomplete by design. When an event occurs that no row
covers, add the row as part of shutdown — the table grows with experience,
not with upfront guessing.

### Reproducibility principle (Amendment 2026-10-01, P5-revised)

Any claim in a record must be either (a) a durable historical fact that
cannot change ("decision made at 15:30 UTC", "+30 tests added this
session"), or (b) a current-state claim paired with the command and
timestamp that would reproduce it ("1130 passing, verified 12:45 UTC via
`make check`"). Unverifiable assertions rot; commands don't.

Concretely:
- Counts are permitted as **deltas or historical markers**, never as bare
  current-state proof. Write "+30 tests this session", not "we have 1130
  passing tests". If a current total matters, attach the verification:
  "1130 passing (verified 12:45 UTC via `make check`)".
- **Action timestamps** ("committed at 15:30") are always allowed — history
  doesn't change.
- **State timestamps** ("DASHBOARD current as of…") are only meaningful
  with the commit they were verified against: "current as of `abc123`,
  verified via `git log -1`".
- Never write exact ahead/behind commit counts ("7 commits ahead") — they
  rot on the next commit. Reference `git log <base>..HEAD --oneline`
  instead.

═══════════════════════════════════════════════════════════════
         SECTION 3: VALIDATION (BEFORE DECLARING DONE)
═══════════════════════════════════════════════════════════════

Nothing is "done" until verified. Run and confirm:

  □ All tests pass (full suite, not just yours)
  □ Linter passes with no new violations
  □ Type checker passes (if applicable)
  □ Build succeeds (if applicable)
  □ No secrets, credentials, or .env files in your diff
  □ No debug/console statements left in production code
  □ Error handling exists for all IO, network, and parsing operations
  □ Documentation updated if behavior changed
  □ Database migrations are reversible (if applicable)
  □ Session record re-read against `git log`: commit list complete,
    statuses current, no checked-off TODOs for finished work, session
    header matches REGISTRY entry. (Amendment 2026-10-01, P6.)

If any check fails and you cannot fix it in scope:
  → Log it in your session file with severity and remediation plan
  → Do NOT silently skip it

> **Amendment 2026-10-01 (P6-part): session file header schema.** Session
> files MUST begin with a metadata block containing: agent ID, branch,
> started timestamp, current status, and base commit. These fields MUST
> match the REGISTRY.md entry. Without the schema, "header matches
> REGISTRY" is unenforceable.

═══════════════════════════════════════════════════════════════
              SECTION 4: SHUTDOWN SEQUENCE (MANDATORY)
═══════════════════════════════════════════════════════════════

> **Amendment 2026-10-01 (P1): Step 0 — stop working.** After Step 1 below,
> only Steps 2–6 mechanics are permitted. Any new finding, fix, or idea —
> however small, except typo/format corrections to the session file being
> written right now — aborts shutdown: log it in the session file, return
> to work mode, restart shutdown later. Maximum 3 shutdown restarts per
> session; a fourth attempt means something is structurally wrong — halt,
> log `[NEEDS HUMAN]` in BLOCKERS.md. (A mid-shutdown abort is NOT a
> re-open; re-open applies only after shutdown fully completed — see the
> Re-open Transition below.)

STEP 1 — Finalize Your Session File
  Add a complete summary section:
    • Outcome: COMPLETED | PARTIAL | BLOCKED | PIVOTED
    • What was accomplished
    • What was NOT accomplished and why
    • Files changed (table: path, action, summary)
    • Key decisions made and rationale
    • Technical debt introduced (if any)
    • Bugs discovered but not fixed (with location)
    • Risks and warnings for the next agent
    • Prioritized next steps

STEP 2 — Update REGISTRY.md
  Change your status from IN-PROGRESS to COMPLETED.
  Release your file ownership claims.

STEP 3 — Clean Up state/plans/
  If your plan is complete, delete your plan file.
  If partially complete, update it with current status.

STEP 4 — Add Entry to INDEX.md
  One row with: session ID, your agent, date, title, files touched,
  status, branch.

STEP 5 — Git Cleanup
  Verify:
    □ Working tree is clean
    □ All changes committed with descriptive messages
    □ Branch pushed to remote
    □ No orphan files or forgotten artifacts

STEP 6 — Reconciliation (IF applicable)
  If you are the last active agent OR if you merged branches:
  You are the RECONCILER. You must:
    • Rebuild DASHBOARD.md to reflect current merged reality
    • Update REGISTRY.md (remove inactive agents)
    • Resolve any conflicts in state/conflicts/
    • Update ARCHITECTURE.md if structure changed
    • Add any new ADRs to DECISIONS.md
    • Commit: "chore(state): reconcile after <description>"

STEP 7 — Terminal verification loop (Amendment 2026-10-01, P2)
  After the final commit, re-read DASHBOARD.md and your session file
  against `git log` and reality. Classify each discrepancy found:
    • Record error (a file says something false) → fix the record.
    • Reality error (code or git state is wrong) → this is a bug in your
      work: P1 aborts shutdown, fix it in work mode, restart shutdown.
  Fix, commit, and re-read again. New work is forbidden inside this loop.
  Stop only when a full re-read surfaces nothing. If three iterations do
  not converge, mark the session OUTCOME as PARTIAL (never COMPLETED),
  record the residual discrepancies in BLOCKERS.md, and halt — a
  non-converging loop means the session did not complete, regardless of
  what code shipped.

  Minimum re-read checklist:
    • `git log <base>..HEAD --oneline` — every commit is in the session
      file's commit list.
    • `git status` — clean.
    • DASHBOARD "Active Agents" vs REGISTRY.md — must match.
    • Session summary — every claim checkable (see the P5 principle).

### Re-open Transition (Amendment 2026-10-01, P3)

If work resumes after shutdown fully completed (REGISTRY at COMPLETED):
this is a re-open, not a continuation. It requires all of:
  1. REGISTRY.md status back to Active with a new timestamp.
  2. A dated "Re-opened: <timestamp> — <reason>" entry in the session
     file, stating: what triggered the reopen (user request, self-review,
     verification finding, new discovery); why it couldn't wait for a
     fresh session; the delta from the "completed" state.
  3. A mandatory `git fetch && git log` check against the session's last
     recorded commit — if the branch diverged since, resolve it before
     proceeding.
  4. Full shutdown re-executed afterward.

Decide re-open vs new session by this rule:
  • Re-open the same session when: same objective, same calendar day, no
    other agent's session interleaved since.
  • Start a new session when: new objective, next day, or another agent
    worked in between.
Without this rule the choice is arbitrary, which defeats the audit trail.

═══════════════════════════════════════════════════════════════
            SECTION 5: CONFLICT HANDLING RULES
═══════════════════════════════════════════════════════════════

If you discover a conflict (overlapping files, contradictory plans,
stale ownership, merge issues):

1. STOP active work.
2. Create a file in state/conflicts/ describing:
   • What the conflict is
   • Which agents/sessions are involved
   • Proposed resolution
3. If the other agent is active (<24h), add a [COORDINATION REQUEST]
   note in their session file.
4. If the other agent is inactive, document your takeover and proceed.
5. If the conflict is unresolvable without human input, mark it
   [NEEDS HUMAN] in BLOCKERS.md and halt.

Never silently overwrite another agent's work. Never resolve a
conflict by just "going first and hoping."

═══════════════════════════════════════════════════════════════
          SECTION 6: ANTI-PATTERNS (NEVER DO THESE)
═══════════════════════════════════════════════════════════════

❌ Starting work without reading DASHBOARD.md and REGISTRY.md
❌ Reading every single file in state/sessions/ (wastes context)
❌ Modifying files owned by an active agent without coordination
❌ Writing to DASHBOARD.md, REGISTRY.md, or INDEX.md during active work
❌ Leaving uncommitted changes at session end
❌ Fixing unrelated bugs without logging them first
❌ Silently expanding scope beyond the original plan
❌ Catching errors without logging or re-throwing
❌ Committing secrets, API keys, or .env files
❌ Trusting a DASHBOARD.md that's >48h stale without verification
❌ Skipping tests because they're "probably fine"
❌ Making handoff notes assuming the next agent has your context
❌ Writing exact commit/test counts as current-state proof — cite the
   verifying command instead (P5)
❌ Declaring completion on user satisfaction rather than plan items plus
   Section 3 validation (P1)

═══════════════════════════════════════════════════════════════
          SECTION 7: BOOTSTRAP PROTOCOL (NO state/ EXISTS)
═══════════════════════════════════════════════════════════════

If the state/ directory does not exist, you are the first agent
under this protocol. Perform a full repository audit before any
other work:

STEP 1 — Comprehensive Audit
  Investigate and document:
    • Directory structure (tree, depth 3-4, exclude node_modules/.git)
    • Technology stack (languages, frameworks, versions)
    • Entry points and main modules
    • Database type and migration state
    • API surface (endpoints, auth mechanism)
    • Testing framework and current test status (run them!)
    • CI/CD configuration
    • Dependencies (outdated, vulnerable)
    • Documentation state (README accuracy, inline docs)
    • Known issues visible in code (TODOs, FIXMEs, broken areas)
    • Current working features vs broken features

STEP 2 — Create state/ Structure
  Create the directory and these initial files:
    • DASHBOARD.md     — summary of your audit findings
    • REGISTRY.md      — empty table, ready for agents
    • INDEX.md         — empty, ready for sessions
    • ARCHITECTURE.md  — architecture summary from audit
    • DECISIONS.md     — empty, ready for ADRs
    • DEBT.md          — list all tech debt found in audit
    • BLOCKERS.md      — list any blockers found
    • sessions/        — directory with your first session file
    • plans/           — empty directory
    • conflicts/       — empty directory
    • archive/         — empty directory

STEP 3 — Create Your Bootstrap Session File
  Document the audit itself as your first session.
  Filename: state/sessions/YYYYMMDD-HHMM-<ID>-bootstrap-audit.md

STEP 4 — Commit the Bootstrap
  Commit message:
    "chore(state): bootstrap MACP protocol with repository audit"

STEP 5 — Now Proceed to Normal Startup (Section 1)
  Treat the bootstrap as complete and proceed with your actual task.

═══════════════════════════════════════════════════════════════
                      REMEMBER
═══════════════════════════════════════════════════════════════

• You are one of many agents. Act like it.
• The state/ directory is the shared brain. Keep it accurate.
• When in doubt: document more, assume less.
• A clean handoff is more valuable than a clever shortcut.
• If you break the protocol, document why — don't hide it.

Acknowledge you have read and understood this protocol before
beginning any task.

═══════════════════════════════════════════════════════════════
             APPENDIX A — AMENDMENT LOG (2026-10-01)
═══════════════════════════════════════════════════════════════

P1 (shutdown Step 0) + P3 (re-open transition) — shutdown semantics.
P2 (terminal verification loop) + P4 (ownership table) — ownership plus
verification; neither ships without the other.
P6 (Section 3 record check + header schema) — cheapest high-value fix.
P5 (reproducibility principle, revised from ban-framing) — how to write.
Ship order applied: P1+P3, P2+P4, P6, P5.
P7 (machine-checked state drift) — DEFERRED. Automate only after P1–P6
have run long enough to reveal residual failures; a checker written now
would encode guesses. When built, pre-commit presence must warn rather
than block (blocking trains `--no-verify` reflexes); CI remains the
blocking enforcement.

Known open issues (next-batch backlog, not this amendment):
1. Context-window pressure causing documentation collapse — no
   "stop and hand off" rule yet.
2. User-induced protocol violation ("skip the protocol") — comply,
   refuse, or comply-and-document is currently unspecified.
3. Protocol version drift mid-session — no rule covers operating under a
   changed protocol.
4. Minimum viable session record for trivial changes — without it, agents
   route around the rules for small work and forget to re-engage.

Rationale record: `macp-protocol-review.md` (adversarial review of P1–P7;
verdicts and refinements adopted above).
