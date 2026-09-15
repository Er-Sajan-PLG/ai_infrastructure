# Engineering Standards

The normative rules for this repository. [`CHARTER.md`](../CHARTER.md) is the
constitution and the source of truth; this document is the **enforceable
summary** — each rule states how it is checked. A rule with no check is a
preference, and preferences are not allowed to be presented as standards
(charter §20).

Status of this document: **normative**. If it disagrees with `CHARTER.md`, the
charter wins and this file is the bug.

---

## 1. Honesty rules (non-negotiable)

| # | Rule | Charter | Enforced by |
|---|---|---|---|
| H1 | `status` reflects artifacts that exist | §4 | `make status` (exit 1), CI, pre-commit |
| H2 | A wrapper/adapter/prototype is never labelled an independent implementation | §10 | Human review + `PROVENANCE.md` |
| H3 | Research is never presented as implementation | §10 | Catalog entry contract (`make validate`) |
| H4 | Claims distinguish FACT / OBSERVATION / INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT | §6 | Human review (see §7 below) |
| H5 | Empty fields are empty; never optimistic | §14 | `make status` |

**H1 is the most important rule in the repository.** It is the one that decays
silently, and it is the one the tooling checks hardest.

## 2. Lifecycle rules

| # | Rule | Charter | Enforced by |
|---|---|---|---|
| L1 | Only the next stage may be worked on | §25.4 | Human review; drift check for artifacts |
| L2 | `RESEARCHED` requires recorded research | §5 | `make status` |
| L3 | `DESIGNED` requires `specifications/<id>.md` | §13 | `make status` |
| L4 | `DECIDED` requires a real decision (not `pending`) | §8 | `make status` |
| L5 | `IMPLEMENTED` requires an existing implementation path | §13 | `make status` |
| L6 | `TESTED` requires an existing test artifact | §18 | `make status` |
| L7 | `BENCHMARKED` requires benchmark artifacts + recorded methodology | §19 | `make status` + human review |
| L8 | `depends_on` references real ids; dependencies do not lag dependents | §24 | `make status` |

## 3. Code standards

| # | Rule | Charter | Enforced by |
|---|---|---|---|
| C1 | Python, type-hinted | §13 | mypy `strict = true` |
| C2 | Formatted (black; the ruff formatter is deliberately unused) | §13 | `make lint` |
| C3 | Linted (ruff, ruleset in `pyproject.toml`) | §20 | `make lint` |
| C4 | No runtime dependency without an ADR | §22 | Human review gate |
| C5 | Public functions/classes have docstrings explaining *why* | §13 | Human review (see §7) |
| C6 | Entries are standalone — importable without the studied repo's deps | §13 | Human review + a test that imports in isolation |
| C7 | No prints in library code (CLI scripts excepted) | §20 | ruff `T20` |

## 4. Testing rules

| # | Rule | Charter | Enforced by |
|---|---|---|---|
| T1 | Every implementation has tests | §18 | `make status` (L6); `make validate-strict` rejects an empty `tests/` |
| T2 | Failure modes are tested, not just the happy path | §18 | Human review (see §7) |
| T3 | A test that cannot fail is not a test | §18 | Human review |
| T4 | Tests are never weakened to obtain a pass | §28 | Human review; pre-commit refuses `--no-verify` |
| T5 | The suite passes before a status advance to `TESTED` | §18 | pre-commit, CI |
| T6 | Capability tests are actually collected and run | §18 | `testpaths` includes `catalog/`; guarded by a test (ADR-0004) |
| T7 | `tests/` and `examples/` must contain real content, not just exist | §13 | `make validate` (error in all modes) |

## 5. Documentation rules

| # | Rule | Charter | Enforced by |
|---|---|---|---|
| D1 | Category READMEs carry the required sections | §13 | `make validate` |
| D2 | Every catalog entry has `README.md` + `PROVENANCE.md` | §13 | `make validate` |
| D3 | Every significant decision has an ADR in the same session | §12 | pre-commit drift check on `docs/decisions/`; human review |
| D4 | External influences are registered in the research registry | §11 | Human review |
| D5 | `inspired-by` ≠ `derived-from`; conflation is a licensing risk | §11 | Human review + ADR-0002 |
| D6 | A session leaves a roadmap note | §25.10 | Human review |

## 6. Human review gates

These cannot be automated and must stop for a human (charter §22):

- Significant licensing risk, or setting `code_reused: true` — **Apache-2.0 is in force** ([ADR-0002](decisions/0002-license-selection.md)); reuse additionally requires `attribution_requirements` and a `NOTICE` update in the same change
- Copying or adapting substantial external code
- **Accepting an external contribution** — currently prohibited outright; see below
- Changing foundational architecture
- Adding a major dependency
- Security-sensitive infrastructure, or any trust-boundary / auth change
- Deleting or replacing mature infrastructure
- Declaring a capability production-ready
- Major compatibility commitments
- **Relicensing** — permitted for future versions only while no external contribution has been accepted

### Licensing rule

The repository is **Apache-2.0**. Two consequences for ordinary work:

1. `code_reused: true` in the research registry is permitted, but the entry must record `attribution_requirements`, and the required notice text must be added to `NOTICE` in the same change.
2. **External contributions are not accepted** ([`../CONTRIBUTING.md`](../CONTRIBUTING.md)). As sole copyright holder the maintainer can relicense future versions; the first accepted outside contribution removes that ability. Do not merge an outside PR.

## 7. What is deliberately not automated

Automation checks structure, not judgement. These require human or agent
review and cannot be delegated to a script:

- Whether research is actually sufficient (H4, D4)
- Whether a design is good (L3 content)
- Whether tests cover the real failure modes (T2)
- Whether an abstraction earns its complexity (charter §3)

Stating this explicitly prevents the opposite drift: *assuming a green pipeline
means the work is sound.* Charter §18: a successful demo is not evidence of
correctness.

---

## Rule-to-check map

```text
make lint        → C2, C3
make typecheck   → C1
make validate    → D1, D2, H3
make status      → H1, H5, L2..L8
make test        → T5
pre-commit       → the subset relevant to staged files
CI (make ci)     → all of the above + coverage
human review     → H2, H4, C4..C6, T2..T4, D3..D6, §6 gates
```

## Changing a rule

1. Change `CHARTER.md` first if the rule's basis changes — never this file alone.
2. Update the enforcing check in the same change, or move the rule to §7
   (not automated) explicitly.
3. Record the change as an ADR if it affects architecture or licensing.