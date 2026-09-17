# ADR-0019: Commit-message validation

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Related:** [ADR-0015](0015-makefile-shell-hardening.md), [`../risks/ACCEPTED_RISKS.md`](../risks/ACCEPTED_RISKS.md)

## Context

Phase 1.5 adds a commit-message gate. The convention is
[Conventional Commits](https://www.conventionalcommits.org/), which the
repository already used informally. Nothing enforced it.

The SOTA comparison surveyed the available tooling. Two findings changed the
decision from "adopt the obvious tool" to "write a small check":

**`gitlint` is stale.** PyPI shows `0.19.1` uploaded **2023-03-10** — roughly
3.5 years with no release at the time of writing. An unmaintained validator
enforcing a specification that has itself had unresolved ambiguities is a poor
long-term dependency for a gate that runs on every commit.

**The PyPI package named `commitlint` is a different project, under GPL-3.0.**
This is a **trap**, and it is recorded as one: anyone reaching for the familiar
"commitlint" name — the de-facto standard in the JavaScript ecosystem — lands
on an unrelated copyleft package they did not intend to depend on. The
requirement is the Conventional Commits **specification**, not the commitlint
**brand**.

**`commitizen` is the maintained option** (4.18.1, released 2026-09-13) and was
installed and evaluated. Its `check` subcommand validates the same header-only
subset implemented here. What it additionally brings is changelog generation,
version bumping, and an interactive `cz commit` prompt — none of which this
repository uses.

## Decision

**Write a first-party header validator** (`scripts/check_commit_msg.py`,
~50 lines of validation logic) rather than adopt a dependency, and wire it as a
`commit-msg` git hook installed by `make install-hooks`.

The deciding argument is proportional: the requirement is a single regular
expression over a commit header, enforced locally and in CI. Adopting a tool
that carries changelog and versioning machinery for that is a poor trade, and
it would add a dependency whose transitive tree must then be re-reviewed at
every phase gate. `commitizen` was **uninstalled** after evaluation, so it does
not appear in the lock file — a lock file containing a deliberately rejected
tool is a contradiction in terms.

### What is validated

**The header only:** `type(scope): description`, where `type` is a lower-case
word, `scope` is optional, and `description` is non-empty.

**One structural rule:** a **blank line between the header and the body**. This
is the single most consequential formatting rule in practice — without it the
header is no longer the first paragraph, and `git log --oneline`,
`git rebase -i`, and every changelog generator display something different from
what was intended.

### What is deliberately NOT validated

Recorded as **AR-003**, because an unenforced rule is a preference and should
be labelled as one:

- **lower-case subject** — not a rule in the specification. It is a convention
  from a popular commitlint config, not the spec;
- **a maximum subject length** — a widely copied 72-character rule is
  convention. A warning is emitted at that length; it never fails a build;
- **a required scope, or a scope allow-list** — the specification makes scope
  optional, and this repository's changes routinely span several areas;
- **`Signed-off-by`** — not part of the specification;
- **body and footer structure.** The specification is genuinely ambiguous here.
  Its own issue tracker records unresolved questions about footers without a
  body and about whether `!` implies a breaking change. Enforcing more than the
  header would **encode one reading of an ambiguous document as if it were the
  document.**

The type vocabulary is checked as a **warning**, not an error, because the
specification explicitly permits types beyond `feat` and `fix` ("others are
allowed").

### The escape hatch

A header containing the literal marker `[skip commit-msg]` is accepted with a
warning. The marker is a deliberate design choice over the alternative:

- `--no-verify` bypasses the hook **invisibly** — nothing in the log records
  it, and charter §28 forbids it;
- `[skip commit-msg]` is **visible in `git log` forever**, so the exception is
  reviewable.

Legitimate uses exist: reverting a revert, importing an upstream commit
verbatim. The gate should permit those while making them visible.

### Scope of history checked

Only the **range being pushed** (or `HEAD` when there is no upstream). The
entire history is never validated — commits made before this convention existed
could only be fixed by rewriting history, which the charter forbids, or by
disabling the check. This mirrors how the migration's own commits are handled:
they are not retroactively failed.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| `commitizen` | **Rejected** | Maintained and correct, but brings changelog/versioning machinery this repository does not use. Installed, evaluated, uninstalled. |
| `gitlint` | **Rejected** | PyPI shows 0.19.1 from 2023-03-10 — ~3.5 years stale. |
| PyPI `commitlint` | **Rejected — flagged as a trap** | A different, GPL-3.0 project. Taking on copyleft for a header check would be an unforced licensing decision. |
| `conform` (Go) | **Rejected** | A compiled binary, so it cannot be pinned by the Python toolchain. Effectively unmaintained; a fork (`go-conventional-commits`) exists but adds a second pinning mechanism. |
| `pre-commit` framework with a commitlint hook | **Rejected** | Introduces a second hook manager alongside the existing native hooks, and the hook it would run is the same one implemented here. |
| Enforce lowercase subject | **Rejected** | Not in the specification. Encoding a config convention as a spec rule is exactly the conflation this ADR avoids. |
| Enforce a 72-character limit | **Rejected as an error** | Convention, not specification. Kept as a warning. |
| Enforce body/footer structure | **Rejected** | The specification is ambiguous; enforcing it would encode an interpretation. |
| Validate the whole history in CI | **Rejected** | Unfixable without rewriting history (forbidden, §28) or disabling the check. |
| No message gate at all | **Rejected** | The repository already followed the convention by discipline. Adding the gate caught the author of this change committing a non-conforming header minutes earlier — the discipline was not, in fact, sufficient. |

## Consequences

**Positive.** Commit format is enforced with zero new dependencies. The rules
are exactly the specification's, with the ambiguity documented rather than
resolved by fiat. The exception mechanism is visible in the log.

**Negative / accepted costs.**

- ~50 lines of first-party code to maintain instead of a dependency. Justified
  by the narrowness of the requirement, and the code is covered by the test
  suite's conventions.
- A developer's first commit on a clone will fail if they have not run
  `make install-hooks`. The hook is installed by `make setup`'s documented
  follow-up, and CI re-validates every commit on a branch, so a local skip is
  caught.
- **A local hook is bypassable** with `--no-verify`. Charter §28 is a rule
  about not doing that; it is not a mechanism that prevents it. CI catches it.
- Body and footer structure remain unenforced (AR-003).

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §13 — repository standards.
- §20 — the unenforced rules are labelled preferences and recorded as AR-003.
- §28 — the escape hatch is a visible marker rather than an invisible bypass.
- Enforced by: `make commit-msg`, `.git/hooks/commit-msg` (via
  `make install-hooks`).
