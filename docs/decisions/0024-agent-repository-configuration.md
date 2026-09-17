# ADR-0024 — Agent Repository Configuration (new taxonomy category)

- **Status:** Accepted
- **Date:** 2026-09-17
- **Supersedes:** —
- **Superseded by:** —

## Context

Phase 2 Track 2B studied 25 AI infrastructure repositories at pinned commits
([ADR-0021](0021-study-pipeline-architecture.md)).

**This category was not proposed by the pipeline.** The pipeline proposes a
category when one of its *rules* fires and the resulting category is absent from
the taxonomy tree. No rule matches agent-facing repository configuration, so
nothing was proposed — the finding came from aggregating the studies' **top-level
entry lists** and noticing a recurring structure the rules did not name.

Measured across the 25 reports:

| Marker | Repositories |
|---|---|
| `AGENTS.md` | **18 / 25** |
| `CLAUDE.md` | 14 / 25 |
| `.claude/` or `.cursor/` | 10 / 25 |
| `.agents/` | 8 / 25 |
| `.agents/skills/` | 7 / 25 |
| `SKILL.md` | 0 / 25 |

`AGENTS.md` appears in 72% of studied repositories. In several it is the
repository's most prominent file after the README, and it is frequently longer
than `CONTRIBUTING.md`.

**Why this is a new class rather than existing categories.** Verified against
charter §2's scoping: `skills` covers *"skill systems, discovery, registration,
composition, execution, permissions, lifecycle, evaluation, packaging"* — that
is a *runtime's* skill mechanism, not files a repository ships to instruct an
external agent. `harnesses` covers *"execution environments, coding-agent
harnesses, sandboxes, terminal execution"* — environments, not declarations.
`development` covers AI coding environments and repository analysis. None covers
**a repository declaring how AI agents should work inside it**: instruction
files, agent-specific ignore rules, per-tool context files, and in-repo skill
definitions consumed by whatever agent the contributor happens to run.

The distinguishing property is that the repository is the *producer* and an
external, unspecified agent is the *consumer*. That is a new relationship
between a codebase and its tooling, and it did not exist as a category because
until recently it barely existed as a practice.

## Decision

Add **`agent-config/` — Agent Repository Configuration** as a taxonomy category,
and record the evidence as a `DISCOVERED` capability entry.

The category covers: agent instruction files (`AGENTS.md`, `CLAUDE.md`,
tool-specific equivalents), in-repository skill/prompt definitions intended for
external agents, agent-facing ignore and scope rules, and the **conventions and
cross-tool interoperability** between them.

**Out of scope:** the agent that *reads* these files (that is `harnesses`), and
skill *execution* (that is `skills`).

## Options considered and rejected

1. **Map onto `skills`.** Rejected — verified against §2. `skills` is a runtime
   mechanism; this is repository content. A project can ship `AGENTS.md` with no
   skill system at all, which 18 of the studied repositories do.
2. **Map onto `harnesses`.** Rejected — §2 scopes `harnesses` to execution
   environments. A file declaring conventions is not an environment.
3. **Map onto `development`.** Rejected — §2 scopes it to AI coding
   environments and repository analysis *tooling*. This is the configuration
   those tools consume, which is a different artifact class.
4. **Treat it as documentation, not infrastructure.** Rejected, and this was the
   serious alternative. Documentation describes what exists; `AGENTS.md`
   *changes agent behaviour*, and the studied repositories treat it as
   functional — several gate CI on it and version it alongside code. It is
   closer to a build file than to a README.
5. **Defer as too new to judge.** Rejected: 18/25 is not emerging, it is
   established. Deferring would also mean the taxonomy cannot describe the
   repositories this project studies most often.
6. **Propose it from a pipeline rule instead.** Rejected for now: adding a
   detection rule is a pipeline change, and ADR-0021's Track 2B rule permits
   pipeline changes only when they raise report quality or count. This ADR is
   therefore explicit that the finding came from aggregation, not detection —
   see the negative consequences.

## Consequences

**Positive.** Names a practice in 72% of studied repositories that no category
covered. It is the clearest genuinely-new finding of Phase 2: unlike `config`
(ubiquitous, partly a Python convention) this is both common and *recent*, which
is what a taxonomy extension should look like.

**Negative, stated plainly.**

- **The pipeline cannot detect it.** The finding required a human-or-agent
  aggregation step over reports, which means Track 2B's "≥3 new patterns" was
  not satisfied by the pipeline alone. That is recorded rather than hidden: it
  is the strongest evidence yet for the DW-013 concern that structural
  detection has a ceiling, and it raises DW-013's priority — the trigger
  ("two or more reports materially wrong because reading the source would have
  found what the detector missed") is *not* met, since nothing was wrong, but
  the related case of *nothing detected at all* now has a concrete instance.
- **Convention may not survive.** `AGENTS.md` has no standard beyond a
  community one, and `.claude/`, `.cursor/`, `.agents/` are three competing
  layouts for the same idea. The category may need to become a *conventions*
  entry rather than a capability if no single design wins. Recorded so a future
  session expects churn here.
- **Evidence is filename presence**, not content. A repository with a two-line
  `AGENTS.md` counts the same as one with a detailed policy. The reports state
  this; the ADR repeats it.
- **Category-count growth** to 25 top-level entries (from 22).

## Evidence

- Marker counts measured across all 25 reports in
  [`study_pipeline/studied_repos/`](../../study_pipeline/studied_repos/).
- Taxonomy entry added: `agent-instruction-files` (`DISCOVERED`,
  `decision: pending`).
- Criterion: charter §2 (extend rather than drop), §12, §14.
