# Study Pipeline

Automated repository-study subsystem (charter §29). **Not implemented — Phase 2.** This directory is a declared seam (charter §13, §30), not working machinery.

## Intended pipeline

```text
1. CLONE     a target open-source repository
2. ANALYZE   its structure — infrastructure patterns, abstractions, architectural decisions
3. EXTRACT   the core infrastructure logic, separated from application-specific code
4. UNDERSTAND why it was built this way; what problem it solves; what the tradeoffs are
5. RECREATE  a clean, standalone, well-documented version of each identified pattern
6. CLASSIFY  the recreation into a taxonomy category (charter §2, §14)
7. CITE      the original source (repo, authors, license) via PROVENANCE.md
8. LOG       a study report: what was found, what was extracted, what was skipped and why
```

## Planned components

| File | Role |
|---|---|
| `clone_and_analyze.py` | Fetch and structurally map a target repository |
| `pattern_extractor.py` | Identify candidate infrastructure patterns and their boundaries |
| `classifier.py` | Map extracted patterns to taxonomy categories and propose new ones |
| `recreator.py` | Produce skeleton implementations + provenance from an extraction |
| `report_generator.py` | Emit the study report into `studied_repos/` |

Entry point (planned): `./scripts/study_repo.sh <github_url>`

## Honesty constraints

- Step 5 **RECREATE** means `UNDERSTAND → ABSTRACT → DESIGN → IMPLEMENT → TEST`, never `COPY → RENAME → MODIFY` (charter §9). Automated extraction proposes candidates; it does not launder copied code.
- Any step that would import third-party source into `catalog/` is blocked by [ADR-0002](../docs/decisions/0002-license-selection.md) until a license is chosen by a human.
- Generated reports are proposals, not canonical knowledge; a human or agent session must review and commit findings (charter §6, §28).
- The pipeline is itself infrastructure: tested, documented, and versioned like everything else (charter §29).

## Status

Empty. `studied_repos/` contains no reports. Building this subsystem is Phase 2 work and is blocked in priority order behind the Phase-1 capabilities in [`../docs/roadmap.md`](../docs/roadmap.md).