# Phase Plans

Executable plans for each growth phase (charter §30). A phase plan is a **working document**, not a contract: it says what to do next, why, and how you'll know it's done. Revise it when evidence says otherwise.

| Phase | Focus | Status | Plan |
|---|---|---|---|
| 0 | **Foundation** *(not in charter — added by ADR-0005)* | ✅ Complete | [phase-0](phase-0-foundation.md) |
| 1 | Seed 5–10 categories with foundational patterns | ✅ Complete | [phase-1](phase-1-seed.md) |
| 1.5 | **Hardening** *(not in charter — added by ADR-0011)* | 📋 Planned | [phase-1.5](phase-1.5-hardening.md) |
| 2 | Build the study pipeline; 20–30 repos | Not started | [phase-2](phase-2-study.md) |
| 3 | Automate discovery of new patterns/categories | Not started | [phase-3](phase-3-discover.md) |
| 4 | Compose into systems; benchmark vs monoliths | Not started | [phase-4](phase-4-compose.md) |
| 5 | Sustain: community, re-study, deprecation | Not started | [phase-5](phase-5-sustain.md) |

## How to use a phase plan

1. Read the **exit criteria** first — that's what "done" means.
2. Take the **next unstarted capability** from the queue. Work one lifecycle stage per session (charter §25.4).
3. Before claiming a stage, check `make status` passes.
4. When the phase is complete, move to the next plan. Do not start Phase 2 work while Phase 1 exit criteria are unmet.

## Why a Phase 0 exists

Charter §30 starts at "Seed", but the repository needs a working environment, a taxonomy, an enforcement layer, and a license before any capability can be built honestly. That work was real and took several sessions. ADR-0005 records it as **Phase 0 — Foundation** so the phase model describes what actually happened instead of leaving that work uncounted.

## Rules that apply to every phase

- One lifecycle stage per session; never claim ahead of artifacts (charter §4).
- Every capability gets an ADR **before** code (charter §8, §12).
- Study targets get registered in `docs/registry/` (charter §11).
- `make check` and `make status` pass before you report success.
- If a phase's plan turns out wrong, change the plan and record why — in an ADR if it's architectural.