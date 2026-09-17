# Phase 2 — Study

**Status:** 🟨 In progress
**Charter basis:** §29 (automated study system), §30 — *"Build the study pipeline; point it at 20–30 major repos."*
**Depends on:** [Phase 1](phase-1-seed.md) complete; [Phase 1.5](phase-1.5-hardening.md) complete (the pipeline lands under the hardened gates)
**Architecture:** [ADR-0021](../decisions/0021-study-pipeline-architecture.md)

## Goal

Build the automated repository-study subsystem and use it to study major AI
frameworks, turning `study_pipeline/` from a declared seam into tested
infrastructure — then let it discover patterns the taxonomy does not yet have.

**This phase adds no capability.** It adds *machinery for finding* capabilities.
`TAXONOMY.md` gains entries only for patterns the pipeline actually discovers and
a session actually decides to adopt, each with its own ADR — never as part of the
pipeline work itself.

## The two-track structure (and why)

The seam's own README names the risk: *"pipeline becomes the project — cap
effort; the deliverable is knowledge, not tooling."* The response is to make the
two tracks **separately completable**, so the tooling cannot absorb the phase:

| Track | Deliverable | Done when |
|---|---|---|
| **2A — Pipeline** | Tested static-analysis machinery | It produces a correct report for a real repository |
| **2B — Breadth** | ≥20 studied repositories, reports committed | Reports exist and are registered |

Track 2A is a prerequisite for 2B, and **2A is complete before 2B begins in
earnest**. This is deliberate: a pipeline refined while reports accumulate is a
pipeline optimised against no fixed target.

## Exit criteria

### Track 2A — the pipeline

- [ ] `study_pipeline/` is importable, type-hinted (mypy strict), stdlib only — no runtime dependency added
- [ ] Components exist as tested modules: clone/inventory, pattern extraction, classification, report generation
- [ ] `make study` (thin wrapper over `scripts/study_repo.sh`) studies a real repository end-to-end
- [ ] **The no-execution guarantee is enforced by a test**, not a comment (ADR-0021 Decision 1): a test asserts nothing in a studied tree is imported, executed, or installed
- [ ] Unit tests cover every pure function with on-disk fixtures; `make check` passes **with no network access**
- [ ] `study_pipeline/tests/` collects — the Phase 1.5 `collectability` gate must accept it
- [ ] `.study-workspace/` is gitignored and pruned; no clone content is ever committed
- [ ] Provenance records the exact studied commit and `code_reused: false`

### Track 2B — breadth and discovery

- [ ] ≥20 repositories studied, each with a report in `study_pipeline/studied_repos/`
- [ ] Every studied repo registered in `docs/registry/RESEARCH_REGISTRY.md` with license at the studied version
- [ ] ≥3 **new** patterns discovered that are absent from the taxonomy, each proposed as a `DISCOVERED` entry **with a supporting ADR**
- [ ] Each report states trade-offs and what to *avoid*, not merely what exists
- [ ] Evidence classified per §6 (FACT / OBSERVATION / INFERENCE / DESIGN OPINION) for non-obvious claims

## Order of work

| # | Work | ADR | Depends on | Status |
|---|---|---|---|---|
| 1 | **ADR-0021** — architecture, no-execution rule, stdlib-only | 0021 | — | **DONE** |
| 2 | **Workspace + clone module** — `git clone --depth 1`, `rev-parse`, prune, gitignore | 0021 | 1 | ⬜ |
| 3 | **Inventory module** — layout, file counts, manifests, marker files | 0021 | 2 | ⬜ |
| 4 | **Pattern extraction** — candidate patterns and boundaries, statically | 0021 | 3 | ⬜ |
| 5 | **Classification** — map to taxonomy categories; propose new ones | 0021 | 4 | ⬜ |
| 6 | **Report generation** — the Markdown report, with provenance and §6 labels | 0021 | 5 | ⬜ |
| 7 | **CLI + `make study`** — thin wrapper; opt-in network E2E | 0021 | 6 | ⬜ |
| 8 | **The no-execution test** — the check that enforces Decision 1 | 0021 | 7 | ⬜ |
| 9 | **Study the first repository end-to-end** — proves 2A | 0021 | 8 | ⬜ |
| 10 | **Track 2B**: study ≥20 repositories, register each | — | 9 | ⬜ |
| 11 | **Propose ≥3 new patterns** as `DISCOVERED` entries + ADRs | — | 10 | ⬜ |

Items 1–9 are Track 2A. Items 10–11 are Track 2B and are **gated on 9 passing**.

## Method

1. **Clone & inventory** — `git clone --depth 1`, record the exact commit, build
   a structural map: top-level layout, file counts by extension, declared
   dependencies, marker files, test layout.
2. **Extract** — identify candidate infrastructure patterns and their boundaries,
   statically.
3. **Understand** — what problem it solves, why built that way, trade-offs. This
   step is **human- or agent-paced**, not automated; the pipeline supplies
   evidence and the session supplies judgement (§6).
4. **Propose** — a design sketch in the report. *Proposes only* — the pipeline
   writes no code at all (ADR-0021 Decision 2; §9; ADR-0002).
5. **Classify** — map to a taxonomy category, or propose a new one as
   `DISCOVERED`.
6. **Cite** — the studied commit and license, per §11.
7. **Log** — the study report: found, extracted, skipped and why.

## Target repositories

LangChain, LlamaIndex, AutoGen, CrewAI, DSPy, Haystack, MemGPT/Letta, OpenDevin,
SWE-agent, Semantic Kernel, OpenAI Swarm, Phidata, Mastra, Vercel AI SDK, plus
any that Phase 1 research surfaced (the `RESEARCH_REGISTRY.md` candidates are
themselves study targets).

## Risks to this plan

| Risk | Response |
|---|---|
| **Executing studied code.** A target's `conftest.py`/`setup.py` runs arbitrary code. | ADR-0021 Decision 1 forbids execution structurally — no `import`, `exec`, or install — and item 8 adds a test enforcing it. The workspace is never on `sys.path`. |
| **Laundering copied code as "extraction".** | ADR-0021 Decision 2: the pipeline writes no code at all, only Markdown proposals. `code_reused` is structurally always `false` because the pipeline cannot write to `catalog/`. Human review gate before anything enters the taxonomy. |
| **Clone size / disk exhaustion.** `--depth 1` still pulls large trees. | Workspace is gitignored and pruned per study; item 2 implements cleanup as a `finally`, not a happy-path step. A size guard refuses absurd targets with a message rather than filling the disk. |
| **"Pipeline becomes the project."** Named in the seam's own README. | Two-track structure above: 2A is complete at item 9 and 2B does not add pipeline features. Any pipeline change during 2B must increase report *quality or count*, or it waits. |
| **Network dependency makes `make check` flaky.** | Unit tests use on-disk fixtures; the network E2E test is opt-in and excluded by default. `make check` must pass with the network down. |
| **Structure-only depth is mistaken for full understanding.** | The limit is stated in ADR-0021's consequences with a reversal condition, and each report must distinguish what was *observed* from what was *inferred* (§6). |
| **Reports become a rubber stamp** — 20 files that say nothing. | Each report must state trade-offs and what to *avoid*; the ≥3-new-patterns criterion is a falsifiable test of whether the study produced knowledge. |
| **License contamination.** | Registry records license at the studied commit before any reuse; reports record the exact commit. |

## Explicitly out of scope

Recorded so a future session need not re-derive the refusals; each is argued in
[ADR-0021](../decisions/0021-study-pipeline-architecture.md):

Executing studied code in any form (sandbox, container, subprocess); automatic
code generation or "recreation" into `catalog/`; any LLM summarisation inside the
pipeline; adding a runtime dependency (tree-sitter, `pyyaml`, or similar);
GitHub-API-based study as a *replacement* for cloning; and any capability work —
`vector-memory-store` and `basic-rag-pipeline` stay `DISCOVERED` until the study
produces evidence that they are the right next components.

## Session protocol for this phase

1. One work item at a time, in the order above.
2. The no-execution rule is not negotiable and not configurable.
3. Report depth limits honestly; never present a structural fact as an
   understanding claim.
4. Any discovered pattern enters as `DISCOVERED` with an ADR — never directly as
   `IMPLEMENTED`.
5. `make check`, `make status`, and `make ci` pass at every commit.
