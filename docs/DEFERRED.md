# Deferred Work Register

**Purpose.** The single home for work that is **correctly not done yet** — not
forgotten, not rejected, not "someday". Every entry records four things:

1. **what** the work is;
2. **why it is not being done now** — a specific current fact, not a vague
   sentiment;
3. **what would change** to make it worth doing (the *trigger*);
4. **what to do** when that happens (the *reversal*), so the upgrade is a
   planned step rather than a rediscovery.

**Why this file exists.** A recommendation that is right for a large system is
often wrong for a small one, and the usual outcomes are both bad: either the
recommendation is adopted early and adds cost with no benefit, or it is
dropped in conversation and rediscovered months later from scratch. Recording
it with a trigger converts "we decided not to" into "we will, when X is true" —
which is a decision a reader can act on.

**The distinction that keeps this honest.** An entry here is *deliberate*.
It is not the same as a rejected option (recorded in the relevant ADR's
"Options considered" section), and not the same as an accepted risk (recorded
in `ACCEPTED_RISKS.md`, which is about living with a defect). This register is
about **work that will become valuable**, deferred to a known trigger.

**Relationship to `make status`.** Each entry names the current measurable
fact that justifies deferral. When that fact changes, the entry is stale and
should be re-evaluated — `scripts/check_deferred.py` enforces the mechanical
parts (schema, required trigger/reversal, review date) and reports entries
whose trigger may have fired.

**Charter references:** §8 (decide before building — DEFER is one of the seven
decisions), §26 step 4 (rejected options must be recorded), §30 (phases).

---

## The register

```yaml
# Deferred work. Parsed by scripts/check_deferred.py.
#
# Schema (every field required unless marked optional):
#   id            stable identifier, DW-NNN, never reused
#   title         one line, human-readable
#   category      one of: scale | performance | operability | security |
#                 governance | tooling
#   current_fact  the measurable present-day fact that justifies deferral
#   why_now_wrong why doing it today would cost more than it returns
#   trigger       the condition that makes it worth doing
#   reversal      the concrete first step when the trigger fires
#   effort        small | medium | large  (the upgrade cost, honestly)
#   source        where the recommendation came from
#   review_by     YYYY-MM-DD, <=400 days out
#   adr           the ADR that records this deferral decision

version: 1

deferred:
  - id: DW-001
    title: "Signed releases and build provenance (SLSA attestation)"
    category: security
    current_fact: "Zero released artifacts. 0 git tags on the repository."
    why_now_wrong: >-
      Signing, provenance attestation and a release workflow all protect the
      integrity of a DISTRIBUTED artifact. With no tags, no published package
      and no consumers, there is nothing to protect: the work would be
      theatre, and unreviewable theatre at that, since no release process
      exists to attach it to.
    trigger: >-
      The first git tag, or the first artifact published outside this machine
      (PyPI, a container registry, or a GitHub Release).
    reversal: >-
      Build a release workflow with `actions/attest-build-provenance` for
      provenance and sigstore for signing, and verify with `cosign verify`.
      Both are free for public repositories; the cost is the workflow, not
      licensing.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (supply chain)"
    review_by: 2027-09-17
    adr: ADR-0020

  - id: DW-002
    title: "SBOM generation and publication"
    category: security
    current_fact: "Zero runtime dependencies; the distributed surface is source only."
    why_now_wrong: >-
      An SBOM's value is proportional to transitive dependency depth. This
      repository deliberately has ZERO runtime dependencies (pyproject.toml
      `dependencies = []`), so a generated SBOM describes an empty graph. It
      would be a step that produces a file nobody can act on.
    trigger: >-
      The first runtime dependency is added, OR the project starts being
      consumed as a package rather than cloned as source.
    reversal: >-
      Add `anchore/sbom-action` (Syft) to the release workflow, emitting
      CycloneDX, and attach it to the release. Re-evaluate at that point
      whether the tool is pinned by version AND checksum, per the CVE-2026-33634
      lesson already applied to the other CI tools.
    effort: small
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (supply chain)"
    review_by: 2027-09-17
    adr: ADR-0020

  - id: DW-003
    title: "Property-based testing (Hypothesis) for the parsing and redaction paths"
    category: scale
    current_fact: "415 example-based tests; the suite runs in about 1 second."
    why_now_wrong: >-
      Hypothesis earns its keep where inputs are wide and adversarial —
      parsers, serializers, redactors. The catalog has four such surfaces, and
      415 targeted tests already cover them with hand-built attack payloads.
      Adding a new test methodology with its own execution model, shrinking
      heuristics and flakiness profile is a significant change to the
      verification apparatus, and it should be argued on the surfaces that
      need it rather than adopted repository-wide.
    trigger: >-
      A defect is found that a hand-written example did not catch, on one of
      the parsing or redaction surfaces (JSON-RPC frames, tool schemas,
      streaming deltas, trace redaction).
    reversal: >-
      Add `hypothesis` as a DEV dependency and write property tests for that
      ONE surface first. Record the ADR at that point, with the defect that
      motivated it. Do not convert existing tests.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (testing)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-004
    title: "Mutation testing (mutmut) as a periodic quality signal"
    category: quality
    current_fact: "Coverage is 89.79% raw; the suite runs in about 1 second."
    why_now_wrong: >-
      Mutation testing is the strongest available answer to "do these tests
      actually assert anything?", but it is expensive in a way that scales
      badly at this size: mutmut has no incremental mode worth the name
      without a cache, so a full run is orders of magnitude slower than the
      suite it evaluates. Against 415 tests the signal is not worth the
      wall-clock in a pre-commit or CI path.
    trigger: >-
      Test COUNT exceeds roughly 2000, OR a change lands that is
      coverage-saturated but obviously under-asserted (high line coverage,
      low mutation score on inspection).
    reversal: >-
      Add `mutmut` as a dev-only tool, run it on a SCHEDULE (weekly, or
      manually before a phase gate), never on the commit path. Start with the
      catalog entry that has the weakest test-to-line ratio. Treat the score
      as a trend, not a gate — enforcing a mutation threshold on a young
      suite fails on correct code.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (testing)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-005
    title: "Merge queue / merge-group CI execution"
    category: operability
    current_fact: "One contributor (the maintainer); no git remote; no pull requests."
    why_now_wrong: >-
      A merge queue exists to catch the semantic conflict where two PRs each
      pass CI against the base branch but fail together after merge. That
      requires concurrent, independent PRs — which cannot occur with a single
      contributor and no remote. Enabling it now would add a serialization
      step that buys nothing.
    trigger: >-
      A second regular contributor, OR the repository gains a remote and starts
      receiving external branches (note: external contributions are currently
      NOT accepted per CONTRIBUTING.md — that policy would have to change
      first).
    reversal: >-
      Enable GitHub's merge queue on the default branch and require the
      `required` aggregator job (already present and statically named in
      .github/workflows/ci.yml, which is exactly what a merge queue needs).
    effort: small
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (CI)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-006
    title: "Required status checks and branch protection"
    category: governance
    current_fact: "No git remote; the repository has never been pushed to GitHub."
    why_now_wrong: >-
      Branch protection is configured server-side on GitHub. There is no
      remote, so there is nothing to protect and no API to configure. Writing
      the settings as code now would produce a configuration that cannot be
      applied or verified.
    trigger: >-
      The repository is pushed to a GitHub remote.
    reversal: >-
      Require the `required` aggregator job and pin the exact check name. The
      workflow already provides a statically named terminal job precisely
      because branch protection can only require checks that exist by a static
      name — a matrix or conditional job that never appears would block merges
      forever. Also enable "require branches to be up to date" only if a merge
      queue is not used (DW-005), since the two solve the same problem.
    effort: small
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (governance)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-007
    title: "Renovate instead of Dependabot for dependency updates"
    category: tooling
    current_fact: "No git remote; no automated dependency PRs exist yet."
    why_now_wrong: >-
      Renovate is strictly more capable than Dependabot (regex managers that
      can track the version pins inside shell steps, richer grouping, a real
      dependency dashboard, per-rule scheduling). But it is a GitHub App that
      requires installation against a hosted repository, and it needs a config
      file whose behaviour cannot be exercised without that remote. Dependabot
      is native, needs only a committed YAML file, and covers pip and
      github-actions — the two ecosystems actually present.
    trigger: >-
      The repository gains a remote AND the pinned in-workflow tool versions
      (gitleaks, actionlint, zizmor) need automated tracking that Dependabot
      cannot see, because they are not dependencies in a manifest.
    reversal: >-
      Install the Renovate app and add `renovate.json`. Round-trip the
      existing .github/dependabot.yml config into it rather than running both:
      two bots opening PRs for the same bump is how a repository learns to
      ignore both. The customManager regex for the workflow ENV pins is the
      specific thing Dependabot cannot express.
    effort: small
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (supply chain)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-008
    title: "Operational dashboards (gate trend, coverage trend over time)"
    category: operability
    current_fact: "A single local repository; no CI history; no hosted service."
    why_now_wrong: >-
      A trend line needs history. CI has never run, so there are zero data
      points, and the metrics that would be plotted (coverage, gate pass rate,
      dependency age) are currently either static or trivially known. Building
      a dashboard against an empty dataset measures nothing and creates a
      maintenance obligation in the meantime.
    trigger: >-
      At least 50 CI runs have completed on a remote, OR a metric has moved in
      a way nobody noticed.
    reversal: >-
      Start with the data already emitted rather than a new service: coverage
      is in the CI log, gate results are in the check runs. A single scheduled
      job that appends a row to a tracked CSV is enough to plot a trend and
      requires no third-party account. Escalate to a hosted dashboard only if
      the CSV proves insufficient.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (observability)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-009
    title: "Multi-version Python CI matrix (3.12 and 3.13 alongside 3.14)"
    category: operability
    current_fact: "One developer environment on Python 3.14; CI not yet run."
    why_now_wrong: >-
      A version matrix exists to prove a LIBRARY works for consumers on
      several interpreters. This repository is not consumed as a library — it
      is cloned and run in its own environment, which the maintainer controls.
      A matrix would multiply CI time to test interpreters nobody uses.
    trigger: >-
      Any catalog entry is published as an installable package, OR a second
      environment (a different machine, a contributor, a deployment target)
      runs a different Python minor version.
    reversal: >-
      Add a `strategy.matrix.python-version` to the workflow job and keep
      ONE combination as the required check (the aggregator job pattern
      already in place), so a failing non-default interpreter does not block
      every merge while it is being fixed. Note that the Makefile's
      `--python 3.14` in `make setup` is a separate, deliberate pin.
    effort: small
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (CI)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-010
    title: "Performant incremental type checking (Pyright/Basedpyright) alongside mypy"
    category: performance
    current_fact: "68 Python files; mypy strict completes in seconds."
    why_now_wrong: >-
      mypy is the charter-mandated checker (§13) and is fast at this size.
      Running a second type checker adds a second set of opinions on the same
      code; the usual motivation (mypy is slow on a large codebase) does not
      apply yet. Adopting one now would mean arguing about two sets of
      errors with one real benefit: speed we do not need.
    trigger: >-
      `make typecheck` exceeds roughly 30 seconds, OR the daemon workflow
      (dmypy) that currently suffices starts failing to keep up.
    reversal: >-
      First try `dmypy run` behind the existing `typecheck` target — a daemon
      keeps mypy's semantics and its strict config, so it adds no second
      opinion. Only if that is insufficient, adopt basedpyright as an
      ADDITIONAL signal and decide explicitly whether its findings are
      blocking or advisory. Do not silently relax mypy strict when adding it.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (tooling)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-011
    title: "Scancode-toolkit for file-level licence detection"
    category: governance
    current_fact: "63 installed packages, all metadata-resolvable; zero runtime deps."
    why_now_wrong: >-
      scripts/check_licenses.py reads DECLARED licence metadata (falling back
      to the shipped licence text). It cannot detect a package that declares
      MIT while vendoring GPL files inside. scancode-toolkit can, by scanning
      every file. It is a heavy dependency with its own licence-detection
      data, and at 63 packages with zero runtime dependencies the residual
      exposure is small.
    trigger: >-
      A runtime dependency is added whose licence is load-bearing for
      redistribution, OR any dependency is found to have mis-declared its
      licence.
    reversal: >-
      Run scancode-toolkit as a periodic check (not on the commit path) over
      the installed runtime dependency set only, and compare its findings
      against the allow-list. Keep check_licenses.py as the fast path.
    effort: medium
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (supply chain)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-012
    title: "Fuzzing the JSON-RPC and tool-schema boundary (AFL++/atheris)"
    category: security
    current_fact: "Vulnerable surface exercised by targeted tests with forged payloads."
    why_now_wrong: >-
      Fuzzing finds crashes in code that parses untrusted input at scale. The
      parsers here are small, pure-Python and already covered by tests that
      feed them deliberately malformed and hostile frames. A fuzzer needs a
      harness, a corpus and a triage process; the harness is the real cost,
      not the fuzzer.
    trigger: >-
      The MCP client is pointed at an untrusted or third-party server, OR a
      parsing defect is found in production that the existing hostile-input
      tests did not catch.
    reversal: >-
      Build ONE harness around the JSON-RPC frame decoder with atheris
      (Python-native, so it stays in the existing toolchain), seed the corpus
      with the existing attack-payload fixtures, and run it on a schedule.
      Do not fuzz the whole repository.
    effort: large
    source: "docs/audits/2026-09-17-phase-1-5-sota-comparison.md (security)"
    review_by: 2027-03-17
    adr: ADR-0020

  - id: DW-013
    title: "Semantic pattern detection in the study pipeline (AST or tree-sitter)"
    category: quality
    current_fact: >-
      Pattern extraction matches directory names and declared dependencies only.
      Measured on this repository it recovers all five real capabilities, and on
      LlamaIndex it recovers 10 strong categories, but it finds NOTHING in
      requests or Flask -- correctly, since those are HTTP libraries with no
      retrieval or tool-registry convention to find.
    why_now_wrong: >-
      The structural detector recognises AI-infrastructure CONVENTIONS and is
      blind to a project that names the same machinery differently, or that
      implements a pattern across files without a directory named after it.
      Closing that needs real parsing: either a hand-rolled AST walk, which
      would be silently wrong on the first non-trivial file and is the specific
      failure mode ADR-0021 rejects, or tree-sitter, which would add the first
      runtime dependency to a zero-dependency repository (charter §22) plus a
      parser surface fed the least trusted input available. Both costs are
      real; neither is justified while the reports are read by an agent session
      that can open the files itself.
    trigger: >-
      Two or more study reports are materially WRONG or unhelpful because the
      detector missed a pattern that reading the source would have found, OR
      the study target list shifts to projects whose layouts are not
      conventional Python packaging.
    reversal: >-
      Prefer the cheap step first: extend the fragment lists and add detectors
      for layouts the reports actually missed, since that is a data change in
      _RULES and costs nothing. Only add parsing if that proves insufficient,
      and if so prefer a hand-rolled ast walk over the STANDARD LIBRARY for
      Python targets, which are the majority of the target list, rather than a
      tree-sitter dependency. Re-open ADR-0021 Decision 3 if a third-party
      dependency is genuinely required.
    effort: large
    source: "ADR-0021 Decision 3; measured against llama_index, requests and flask"
    review_by: 2027-03-17
    adr: ADR-0021
```

---

## Entry template

```yaml
  - id: DW-013
    title: "One line describing the work"
    category: scale            # scale|performance|operability|security|governance|tooling|quality
    current_fact: "A measurable present-day fact that justifies deferral."
    why_now_wrong: >-
      Why doing this today would cost more than it returns.
    trigger: >-
      The condition that makes it worth doing. Be specific and observable.
    reversal: >-
      The concrete first step when the trigger fires.
    effort: medium             # small | medium | large
    source: "Where the recommendation came from."
    review_by: YYYY-MM-DD      # <= 400 days out
    adr: ADR-00NN
```

## How to use an entry

When a trigger fires, do **not** start by re-researching the topic. Start from
the `reversal` field: it names the first step, and the `source` field says
where the reasoning came from. Then delete the entry in the same change that
implements it — an implemented item left in the register is indistinguishable
from a deferred one, which defeats the register's only purpose.

If a trigger fires and the answer is still "not yet", change the
`current_fact` to the new reason. A `review_by` bump with no other edit is
refused by `scripts/check_deferred.py`, for the same reason the accepted-risk
register refuses it: bumping a date is the cheapest way to make a gate green,
and it is not a review.
