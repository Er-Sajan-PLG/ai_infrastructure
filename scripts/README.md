# Scripts

Utility and maintenance scripts (charter §13).

| Script | Purpose | Status |
|---|---|---|
| [`validate_catalog.py`](validate_catalog.py) | Enforce the catalog entry contract (README + PROVENANCE present, required sections, category docs) | **Working** — tested by `../tests/test_validate_catalog.py` |
| `study_repo.sh` | Study-pipeline entry point: `./scripts/study_repo.sh <github_url>` (charter §29) | Not implemented — Phase 2 |

## Usage

```bash
python scripts/validate_catalog.py            # validate the catalog
python scripts/validate_catalog.py --strict   # missing examples/tests become errors
```

Exit code is `0` when valid, `1` on violations. Run this before committing any change under `catalog/` (see [`../AGENTS.md`](../AGENTS.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md)).

## Rules

- Scripts are infrastructure: they carry tests under `../tests/` and are documented here.
- Keep scripts dependency-light; the validator uses only the standard library.
- Generated files are not a source of truth (never treat a script's output as canonical).