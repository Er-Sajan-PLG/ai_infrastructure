# Research Record: Agent Repository Configuration

- **Capability:** `agent-instruction-files` (category: agent-config)
- **Status:** `RESEARCHED` — marker counts (FACT) plus convergence-level aggregation
- **Date:** 2026-10-16
- **Decision:** see [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) *(DOCUMENT)*
- **Sources:** [ADR-0024](../../docs/decisions/0024-agent-repository-configuration.md), study pipeline reports (`study_pipeline/studied_repos/`), [TAXONOMY.md](../../TAXONOMY.md) §4

Claims are labelled per charter §6:
**FACT** (verified, cited) · **OBSERVATION** (inferred from docs/structure) ·
**INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice, not a fact).

---

## 1. Evidence from the study corpus

**FACT.** Marker counts measured across all 25 reports: `AGENTS.md` appears
in 18 of 25 repositories (72%), `CLAUDE.md` in 14 of 25 (56%), and
`.claude/` or `.cursor/` in 10 of 25 (40%)
([ADR-0024](../../docs/decisions/0024-agent-repository-configuration.md)).

**OBSERVATION.** This category was **not** proposed by the pipeline's rule
classifier — no rule matched agent-facing repository configuration. The
finding came from aggregating the studies' top-level entry lists and noticing
a recurring structure the rules did not name (ADR-0024 records this
explicitly). That is why it is the "clearest new finding" of Phase 2: common
and recent, which is what a taxonomy extension should look like.

**FACT.** This repository itself ships the practice: `AGENTS.md` at the root,
plus docs and skill conventions — created before this research record, as a
working convention rather than an implementation of this capability.

## 2. The problem, stated without reference to any implementation

> Give an agent working in a repository a standard way to learn its
> conventions — while treating those conventions as untrusted input.

**DESIGN OPINION.** The second half of that sentence is the uncomfortable
half: these files are *instructions an agent follows*, so an untrusted
repository shipping them is an instruction-injection surface. The taxonomy
entry records this as its security note.

## 3. What was not studied, and why it does not block the decision

**OBSERVATION.** No cross-tool interoperability matrix was built: which
tool reads which file, with what precedence, is not established here.

**INFERENCE.** That gap does not block DOCUMENT, because DOCUMENT does not
claim a design. It claims the pattern is real, common, and recorded — all of
which the counts establish. A deeper study would be owed only if a *tool*
were ever built (linters, syncers), and there is no second consumer for one.

## 4. Why the decision is DOCUMENT

See [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) §Decision 3.
This is a repository practice, not a runtime component; the pattern and the
injection risk are recorded in the taxonomy, and this repository already
instantiates the practice. There is no catalog artifact to build that would
not be speculative tooling. DOCUMENT, per the charter §8 legend, means
researched and recorded, not built.

**DESIGN OPINION.** If tooling is ever justified (for example, drift checking
of instruction files across tools in a multi-tool fleet), that is a new
proposal with its own consumer — not a revival of this entry.

## 5. References

- [Specification: agent-instruction-files](../../specifications/agent-instruction-files.md)
- [ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md) — decision
- [`AGENTS.md`](../../AGENTS.md) — this repository's instantiation of the practice
