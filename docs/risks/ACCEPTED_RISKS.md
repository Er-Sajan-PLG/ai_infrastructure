# Accepted Risks

**Purpose.** The single home of every decision to *not* fix, *not* apply, or
*defer* a security or quality control. A suppression that lives only inside a
scanner's ignore file records *what* was suppressed and never *why* or *until
when* — this file supplies exactly those two facts.

**Authority.** The fenced YAML block below is the machine-readable source of
truth, parsed by `scripts/check_risks.py`. The prose above and below it is for
humans and is not parsed. Editing the prose alone changes nothing.

**How this differs from a suppression.** A suppression *applies* an exception.
This register only *records* one. The scanner's own configuration still
applies it (`bandit` `skips`, `ruff` per-file-ignores, a `--ignore-vuln`
argument). `scripts/check_risks.py` keeps the two in step: it fails when an
entry is past its `review_by` date, and it fails when `review_by` advances
without the rationale changing.

**Why `rationale_ref` is mandatory.** A register whose only gate is a date has
a one-keystroke fix: bump the date. The build goes green and no review
occurred — and that failure mode is *more* likely when an automated agent
session is asked to fix a red build, because editing a date is the cheapest
way to do it. Requiring a reference to a real decision record (an ADR, an
issue, or an explicit `DO-NOT`) means the cheapest fix is no longer
sufficient: the rationale must genuinely change, which means someone had to
think about it again.

**Reviewing this file.** Run `make risks`. The check is a pure function of
(this file, today's date) — it performs no network access, so it is safe in
any environment. A review that finds a risk no longer applies should DELETE
the entry and its corresponding suppression together, in one change.

**Classification.** Every entry is marked `detective` or `normative`:

- `detective` — a fact could change such that the risk no longer applies
  (an upstream fix ships, a dependency is removed). These should be re-checked
  by re-running the scanner, not merely re-dated.
- `normative` — a decision, not a fact. Nothing will "become true" that
  retires it; the only correct action is to revisit the decision deliberately.

Putting a detective risk behind a date-only check is theatre, which is why
the distinction is recorded rather than left implicit.

---

## The register

```yaml
# Accepted risks. Parsed by scripts/check_risks.py.
#
# Schema (every field required unless marked optional):
#   id            stable identifier, AR-NNN, never reused
#   title         one line, human-readable
#   kind          detective | normative
#   scope         where the suppression is applied, or "none" if recorded only
#   rationale     closed enum + free-text statement (see below)
#   rationale_ref reference to a recorded decision: ADR-NNN, #NNN, or DO-NOT #NNN
#   statement     why this is accepted, in prose
#   accepted_by   who accepted it (a name, or "maintainer")
#   accepted_on   YYYY-MM-DD when accepted
#   review_by     YYYY-MM-DD when it must be revisited (<=400 days out)
#   tool          the scanner/tool the suppression applies to

version: 1

risks:
  - id: AR-001
    title: "Bandit B101 (assert) skipped repository-wide instead of per-path"
    kind: detective
    scope: "pyproject.toml [tool.bandit] skips"
    rationale: mitigated_elsewhere
    rationale_ref: ADR-0018
    statement: >-
      bandit's per-plugin `skips` take glob patterns, but they do not reliably
      suppress B101 for nested test directories in practice, and a rule that
      silently does not do what it says is the failure mode this repository
      exists to avoid. The blanket skip is used instead because it measurably
      works (558 findings -> 8). The residual risk is an `assert` used for a
      real runtime check in production code; ruff's B011 covers the sharpest
      form of that, and bandit still runs at MEDIUM severity over production
      code, where an assert-based control failure would surface as a finding
      from a different rule.
    accepted_by: maintainer
    accepted_on: 2026-09-17
    review_by: 2027-09-17
    tool: bandit

  - id: AR-002
    title: "Attack-payload strings in tests trip B105/B108 and are not suppressed"
    kind: normative
    scope: "none - findings are avoided by scoping bandit to production code"
    rationale: accepted_cost
    rationale_ref: ADR-0018
    statement: >-
      Tests deliberately contain forged credentials (sk-LEAKED-SECRET,
      hunter2) and forged traversal paths (/tmp/attacker) and then assert
      those inputs are rejected or redacted. A scanner cannot distinguish a
      forged payload from a real secret. Rather than suppress the rules or
      annotate each line with `# nosec` -- which a published practitioner
      review found had been "suppressing real vulnerabilities, not false
      positives" -- bandit is scoped by PATH to production code. The cost is
      that a genuine hardcoded credential introduced into a TEST file would
      not be caught by bandit; gitleaks scans the full history for exactly
      that, on every commit and in CI.
    accepted_by: maintainer
    accepted_on: 2026-09-17
    review_by: 2027-09-17
    tool: bandit

  - id: AR-003
    title: "Conventional Commits checked on the commit subject only"
    kind: normative
    scope: ".gitlint / commitizen configuration"
    rationale: accepted_cost
    rationale_ref: ADR-0019
    statement: >-
      The commit-message gate validates the header. It does not validate body
      structure, footer format, or the semantics of BREAKING CHANGE. The
      specification is genuinely ambiguous on several of these points (its own
      issue tracker records unresolved questions about footers without a body
      and about whether `!` implies a breaking change), so enforcing more than
      the header would encode an interpretation rather than the spec. The
      cost is that a well-formed header over a misleading body passes.
    accepted_by: maintainer
    accepted_on: 2026-09-17
    review_by: 2027-09-17
    tool: commitizen

  - id: AR-004
    title: "Catalog entry internals are not mechanically protected from import"
    kind: normative
    scope: "none - review rule, recorded here because it is not enforced"
    rationale: mitigated_elsewhere
    rationale_ref: ADR-0017
    statement: >-
      Charter 31 requires entries to be relocatable, and `make independence`
      enforces the enforceable half (leaves stay mutually independent, and no
      entry depends on an integration). It does NOT mechanically prevent one
      entry from importing another entry's internal submodule rather than its
      public interface, because an import-linter `forbidden` contract on
      submodule names flags legitimate `from pkg import X` usage -- the graph
      walk follows the package's own internal imports -- and therefore fails
      on correct code. Per charter 20 this is recorded as a REVIEW rule, not
      claimed as a standard.
    accepted_by: maintainer
    accepted_on: 2026-09-17
    review_by: 2027-09-17
    tool: import-linter

  - id: AR-005
    title: "Static import analysis cannot see dynamic or string-named imports"
    kind: normative
    scope: "none - tool limitation of import-linter"
    rationale: not_reachable
    rationale_ref: ADR-0017
    statement: >-
      import-linter sees EXPLICIT imports only. importlib.import_module(...),
      __import__(...), string-named modules and __init__ re-export chains are
      invisible to it, so a determined violation can evade the check. This is
      accepted because the check's purpose is to make ACCIDENTAL violations
      near-impossible and to make deliberate ones visible in review, not to
      act as a security boundary. No static Python tool closes this gap
      completely; dynamic import tracing would require executing the code.
    accepted_by: maintainer
    accepted_on: 2026-09-17
    review_by: 2027-09-17
    tool: import-linter
```

---

## Entry template

Copy this into the `risks:` list. Every field is required.

```yaml
  - id: AR-006
    title: "One line describing the risk"
    kind: detective            # detective | normative
    scope: "where the suppression is applied, or none"
    rationale: awaiting_upstream   # closed enum, see below
    rationale_ref: ADR-00NN        # ADR-NNN | #NNN | DO-NOT #NNN
    statement: >-
      Why this is accepted, what the compensating control is, and what
      evidence would tell us the situation changed.
    accepted_by: maintainer
    accepted_on: YYYY-MM-DD
    review_by: YYYY-MM-DD          # must be <= 400 days after accepted_on
    tool: bandit                   # or the relevant scanner
```

### The `rationale` enum

Borrowed from VEX, which constrains its justification to a closed set for the
same reason: free prose drifts, and a closed set can be counted and reviewed.
The `statement` field carries the nuance.

| Value | Means |
|---|---|
| `component_not_present` | The affected code is not in this repository at all |
| `not_reachable` | Present, but not reachable by an attacker or a consumer |
| `mitigated_elsewhere` | A different control covers it |
| `accepted_cost` | Real, understood, and accepted as a deliberate trade-off |
| `awaiting_upstream` | A fix exists upstream; we are waiting for it to ship |
| `no_bandwidth` | Known and unaddressed for resourcing reasons |

`awaiting_upstream` and `no_bandwidth` are the two that should be rare and
short-lived. If an entry has been `no_bandwidth` across two reviews, the
honest move is usually to change `kind` to `normative` and accept it
explicitly, rather than to keep re-dating a decision nobody intends to make.
