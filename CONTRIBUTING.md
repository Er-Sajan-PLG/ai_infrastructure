# Contributing

Contributions — human or AI agent — follow the charter. This file is the short version of the rules; [`CHARTER.md`](CHARTER.md) wins on any conflict.

## Golden rules

1. **Capability first, not repository first** (charter §1). Start from the problem and the landscape, never from "let's copy X".
2. **Decide before building** (§8). Every capability gets an explicit IMPLEMENT / ADAPT / COMPATIBILITY / PROTOTYPE / DOCUMENT / DEFER / REJECT decision, recorded in an ADR.
3. **Honest status** (§4). Lifecycle labels reflect artifacts that actually exist.
4. **Inspired-by ≠ derived-from** (§11). Register external projects and distinguish study from code reuse.
5. **Complexity earns its place** (§3). Answer the anti-cargo-cult questions before adding anything.

## Adding a capability

1. Add/update the entry in [`TAXONOMY.md`](TAXONOMY.md) (§14 schema — fill every field, `""` where absent).
2. Do the **next** lifecycle stage only. For research stages, record findings in `research/<category>/`. For DESIGNED, write `specifications/<id>.md`.
3. If you make or reverse an architectural decision, add `docs/decisions/NNNN-<slug>.md` (see ADR-0000 for the format) and link it from the taxonomy entry.
4. Add studied projects to `docs/registry/RESEARCH_REGISTRY.md` with the §11 schema. `code_reused: true` triggers a human review gate (§22).

## Implementation standards (charter §13)

- Primary language: **Python**, type-hinted, ruff-linted, black-formatted.
- Each catalog entry is a directory: `README.md`, `PROVENANCE.md`, `implementation.py` (or package), `examples/`, `tests/`.
- Standalone: runnable without the original studied repo's dependencies.
- Every implementation carries tests (§18); run them before claiming IMPLEMENTED → TESTED.
- Run `python scripts/validate_catalog.py` before committing catalog changes.

## Human review gates (charter §22)

Stop and ask before: copying/adapting substantial external code, major dependency additions, licensing uncertainty, trust-boundary or auth changes, deleting mature infrastructure, production-readiness claims, or major compatibility commitments.

## Style

- Docs: markdown, concise, evidence-labeled (FACT / OBSERVATION / INFERENCE / DESIGN OPINION / EXPERIMENTAL RESULT — §6).
- Commits: small, scoped to one capability or record.
