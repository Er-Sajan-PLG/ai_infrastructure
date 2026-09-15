# USA Audit — Adjudicated (2026-09-16)

> Deterministic pass: `node dist/cli.js audit /home/sajan/Projects/ai_infrastructure --out /tmp/usa-now.md`
> USA **2.21.0** · ruleset `dc53586c` · commit `471b511a` · 2026-09-15T18:27Z
> **73.3/100** · MVP profile · 63 ✅ · 1 🔴 FAIL · 0 ⚠️ WRONG · CRITICAL 1 · HIGH 0 · MEDIUM 2 · LOW 16 · FUTURE 13 · 28 to review · **77.2%** automated
> Judgement queue worked below with `file:line` evidence, per the framework's Rule 4.

---

## 0. Correction to the first draft of this file

A first draft of this adjudication **mislabeled three of the four AI-era rules** — it read
`AI-003` as "unbounded context", `AI-007` as "output validation", and `AI-010` as
"secret handling". Those are not the rule definitions. The audit report prints the real
definitions at `usa-now.md:423-426`:

| Rule | Actual definition (verbatim from the report) |
|---|---|
| `AI-001` | Untrusted content cannot override instructions — LLM01 prompt injection |
| `AI-003` | Agents and tools run with least privilege — LLM03 excessive agency |
| `AI-007` | RAG retrieval is access-controlled per tenant — LLM09 vector/embedding weaknesses |
| `AI-010` | Consequential actions require human confirmation — ASI09 human-agent trust exploitation |

I read the IDs and assumed the definitions from the rule family rather than reading them.
**Every verdict below was then re-derived against the actual definition.** The first draft's
adjudications for `AI-003`, `AI-007`, and `AI-010` are void; the corrected verdicts are in
§2, and one of them (`AI-003`) is a **genuine finding the first draft would have buried.**

This is recorded rather than silently fixed because it is the same failure class this
repository has closed six times: **asserting a verdict without reading the evidence that
defines it.**

---

## 1. The tool's one CRITICAL is a false positive, and it is an instructive one

```
🔴 SEC-001 — No hardcoded credentials in source
   Where: integrations/agent_loop_end_to_end/system.py:167, :209
   Why:   2 occurrence(s): `api_key="scripted-key",`
```

**Verdict: FALSE POSITIVE.** Both occurrences are `api_key="scripted-key"` — the literal
placeholder handed to the integration's `ScriptedTransport`, which returns canned HTTP
responses from a list and **never opens a socket** (`scripted_transport.py:99-112`). There
is no credential, there is no service to authenticate to, and there is nothing to rotate.

**What the rule is actually asking, and why the tool cannot tell.** `SEC-001` is a
grep-shaped check for a credential-looking assignment. `api_key=` next to a string is the
exact shape it must catch. The tool has no way to know the string is a sentinel because
**sentinel-ness is a property of the call graph, not of the text** — the literal is only
safe because `build_demo()` wires it to a double.

**The correct disposition is not to silence it.** Moving the placeholder behind an
environment variable would make the linter happy and make the code *worse*: it would
imply the integration needs configuration it does not need, and a reader could not tell it
was a sentinel. Two honest options, neither taken yet:

1. Rename the local so the shape no longer matches — e.g. `fake_key_for_scripted_transport`
   — and let the scanner pass on its own terms.
2. Add a scanner allowlist entry naming the file and the reason.

**Recorded as adjudicated-false-positive with the reason, which is what the framework's
`suppressedReason` mechanism exists for.** Do not "fix" it by hiding a sentinel in the
environment.

---

## 2. The AI-era pack — worked rule by rule against its real definition

These four were marked **NOT APPLICABLE** in the previous audit
(`2026-09-15-usa-audit-foundation.md`: *"there is still no LLM-facing code. They activate
with the first capability"*). **They activated, correctly** — `react-agent-loop` landed.

### `AI-001` Untrusted content cannot override instructions — **PASS, with a named residual**

*Evidence:* `catalog/agents/react_agent_loop/loop.py` reads actions **only** from
`ChatResponse.tool_calls`. The loop never parses message text for an action. Observations
are placed in `ToolResultBlock` inside a `Message(role=TOOL, …)` — a **distinct channel**
from the assistant turn, which is what the rule asks for. Pinned by
`test_a_tool_result_cannot_forge_a_tool_call`, which feeds a tool result containing
`{"name": "delete_everything", …}` and asserts no such call is dispatched.

*Residual, stated in the capability's own README and not hidden:* a tool result cannot
**forge** an action; it can still **persuade** the model to take one. That is a
model-alignment property, not a control-flow one, and this repository does not claim to
solve it.

### `AI-003` Agents and tools run with least privilege — **🚫 MISSING. This is the real finding.**

*The rule asks:* "The tool/permission allowlist: what an agent can call, with which
credentials, and what is blocked by default."

*What exists:* **nothing.** Verified directly:

- `grep -rn "allowlist\|allow_list\|permitted\|permission\|deny"` across
  `catalog/agents/react_agent_loop/*.py` returns **no matches**.
- `RegistryDispatcher.schemas()` (`adapters.py`) advertises **every** registered tool:
  `for name, tool_id in sorted(self._by_name.items())`. There is no filter parameter.
- `run()` (`loop.py`) accepts `agent`, `model_caller`, `dispatcher`, and four numeric
  bounds. **There is no `tools=` parameter and no way for a caller to restrict the set.**

*Consequence.* An agent run against a registry of 50 tools is offered all 50. Nothing in
the capability lets a caller say "this task may read, not write." The dispatcher adapter is
the natural home for it — it already owns the name→`ToolId` map that `schemas()` iterates.

*Fix, and it is small:* an optional `allowed: frozenset[str] | None` on
`RegistryDispatcher.__init__`, filtering both `schemas()` and `dispatch()`. Blocked by
default is the rule's preference; **default-all-advertised is the current behaviour**, and
the difference should be an explicit constructor argument rather than an accident of the
adapter having one job.

**This is the highest-value actionable finding in the whole audit** — it is the only
security rule that is genuinely unmet rather than inapplicable or declared-out-of-scope.

### `AI-007` RAG retrieval is access-controlled per tenant — **NOT APPLICABLE (not yet)**

There is no retrieval in this repository. `vector-memory-store` and `basic-rag-pipeline`
are both `DISCOVERED` with no implementation. The rule becomes applicable the moment
`basic-rag-pipeline` is built, and it is worth recording **now** so it is a design input
rather than a retrofit: the taxonomy entry for `basic-rag-pipeline` should carry a
per-tenant scoping requirement from the start.

### `AI-010` Consequential actions require human confirmation — **DEFER, declared**

*The rule asks:* "For each irreversible action (payment, deletion, deployment, outbound
message): who or what approves it?"

*What exists:* nothing — and it is **declared out of scope in the capability's own README**:
*"Non-goal. This is not a sandbox, a rate limiter, or an approval gate. A dispatched tool
runs with full process privilege."*

That is a legitimate DEFER, not a silent gap, and the distinction matters: the repository
said what it does not do, in the artifact a consumer reads. It becomes a real requirement
when a capability dispatches something irreversible — which is why §5 below flags
`mcp-client` as the next capability and this as its first design question.

### `AI-011` Agent instruction files are scoped and safe — **PASS**

`AGENTS.md:26-32,45` forbids exactly the destructive patterns the rule names: never claim a
status without artifacts, never weaken a check to obtain a pass, **never commit with
`--no-verify`**, never merge outside PRs. The file is scoped to this repository and states
its precedence against the charter.

---

## 3. The two findings the tool got right, plus one it under-called

### `SUP-007` — no secret scanning anywhere — **GENUINE**

`grep -rniE "gitleaks|trufflehog|detect-secrets"` across `*.yml/*.yaml/*.toml/*.txt`
returns **nothing**. Confirmed. This matters more now than last session: the repository has
acquired a provider adapter that handles API keys. Fix: `gitleaks` pre-commit hook + CI job.

### `SUP-002` / `DEP-001` — CI install is not frozen — **GENUINE**

`.github/workflows/ci.yml:38` runs `uv pip install -r requirements-dev.txt` with no
`--frozen`. CI can pass on a toolchain nobody chose. Low-to-medium, cheap to fix.

### The under-call: `SUP-006` SAST, `SUP-004` dependency updates

Both are real absences, both downgraded to LOW by the MVP profile — **correctly**. A
repository with `[project].dependencies` empty and three first-party capabilities does not
need Dependabot yet. Not re-escalated; noted so the deferral is deliberate.

---

## 4. Findings that are mis-scoped or unreliable

| Rule | Tool says | Reality | Verdict |
|---|---|---|---|
| `S9 · Release` **0/10** | No release process | There are **no releases and no intent to have any**. Charter §30 puts this at Phase 1 (Seed). Release ceremony now is cargo cult (charter §3). | **NOT APPLICABLE** |
| `S12 · Documentation` **3.3/10** † | Low | 33.3% confidence, **†** = fewer than half the checks were verifiable. The repo ships a 322-line charter, 9 ADRs, 3 specifications, 4 research records, an 18-entry registry, 6 phase plans. Measurement artifact. | **UNRELIABLE** |
| `S14` **10/10** at 16.7% † | — | A 10/10 on 16.7% verification. Noise in the **optimistic** direction, and directly contradicted by §2's `AI-003` finding. | **UNRELIABLE** |
| `S13 · Accessibility/i18n` 0/10 | — | Library + CLI, no UI. Pack self-selected wrongly. | **NOT APPLICABLE** |
| `S10 · Dependencies` **10/10** † | — | 20% confidence. Correct by accident: zero runtime dependencies. | **TRIVIALLY TRUE** |

---

## 5. What the score actually measures, and the number to stop trusting

| | |
|---|---|
| 2026-09-15 recorded (empty `catalog/`) | **72.4** |
| Today — 3 `TESTED` capabilities, 1 integration, 302 tests, 89% coverage | **73.3** |
| Delta | **+0.9** |

**The repository went from zero capabilities to three tested, composed capabilities
including a working end-to-end system, and the score moved 0.9 points.**

The reason is structural: the score is dominated by **process** dimensions that were
already near-maximal when `catalog/` was empty — S1 structure 8.5, S2 security 8.1, S4
architecture 10, S5 code quality 10. The dimensions carrying capability signal (S9 release,
S12 docs, S14 AI-era) are either not applicable at Phase 1 or measured at a confidence too
low to trust.

**Track instead:** capabilities `TESTED` (0 → 3), tests (195 → 302), integrations (0 → 1),
registry entries (8 → 18). Those moved. The headline did not.

---

## 6. Vision alignment — charter section by section

### ✅ Aligned, with evidence

| Charter | Requirement | Evidence | Verdict |
|---|---|---|---|
| §1 | Capability-first, never copy-first | Every ADR opens with the problem, not a reference repo | **PASS** |
| §4 | Honest lifecycle | `make status` exits 1 when a claim exceeds disk; verified by removing `tests/` | **PASS** |
| §6 | Evidence labels | Research records use FACT / OBSERVATION / INFERENCE / UNKNOWN; unknowns recorded as UNKNOWN (`execution-trace-recorder.md` §11) | **PASS** |
| §8 | Decide before building | 9 ADRs, all `Accepted`; vocabulary: **REJECT 15 · DEFER 8 · IMPLEMENT 7 · ADAPT 3 · PROTOTYPE 1 · COMPATIBILITY 1** | **PASS — rejections outnumber implementations 2:1** |
| §11 | Inspired-by ≠ derived-from | 18 registry entries; **`^code_reused: true` count = 0**, all 18 are `false`; 3 of 3 catalog entries ship `PROVENANCE.md` | **PASS** |
| §13 | Entry contract | All 3 entries have README, PROVENANCE, examples, tests; `validate_catalog` 0 errors incl. `--strict` | **PASS** |
| §17 | Integration philosophy | `integrations/agent_loop_end_to_end/` composes 3 capabilities through public interfaces; proves the seam is real by implementing `Transport` from **outside** the package | **PASS** |
| §18 | Testing | 302 tests, 89% coverage, failure paths are the majority, no network in any test | **PASS** |
| §24.1 | Dependency-first sequencing | Checked every session; blocked `basic-rag-pipeline` correctly on `vector-memory-store` | **PASS** |
| §28 | Never weaken a test | `UnactionableToolError` raised rather than adding a fourth `StopReason`, which would have falsified ADR-0008's own definition of done | **PASS** |

### ⚠️ Two places the vision is at risk

**§16 Compatibility & Standards — seven capabilities in, nothing interoperates.** Charter
§16 says *"support useful established standards … with standard-compatible interfaces over
independent internal implementations."* The `execution-trace-recorder` research correctly
refuses to *claim* OTel conformance, but that also means no capability yet talks to
anything external. `mcp-client` is the only capability whose whole purpose is
interoperability; it is `DISCOVERED`, has **no unmet dependencies**, and has been passed
over three sessions running for capabilities with no consumers. Its own taxonomy note
argues for it: *"COMPATIBILITY candidate (charter §16) … a thin working client beats a
comprehensive never-finished one (§24.4)."*

**§22 Human review gates — one gate item has been open 14 sessions.** The contribution
policy. See §7.

---

## 7. Governance — what is working, and the one thing that is not

### Working, each proven to fail on reintroduction

| # | Gap that existed | Now caught by |
|---|---|---|
| 1 | Empty `tests/` accepted | `validate_catalog.py` |
| 2 | `testpaths` excluded `catalog/` | `tests/test_validate_catalog.py` |
| 3 | `research_records` non-empty but file missing | `scripts/repo_status.py` |
| 4 | 41 broken relative Markdown links | `scripts/check_links.py` |
| 5 | ADRs missing from the index | `check_adr_index()` |
| 6 | `integrations/` ungated — tests would never run | `tests/test_gate_coverage.py` |

The pattern the repo named is right: **presence was checked, validity was not.** Six fixes,
one class, each verified both ways.

### Not working: the contribution policy

`CONTRIBUTING.md` states external contributions are **not accepted**, because adopting a
CLA/DCO would forfeit the maintainer's ability to relicense future versions.
`docs/decisions/README.md` lists it under *"Open items requiring human decision."*

**This is a charter §22 human-review-gate item, and it has been open across 14 sessions.**
It blocks an entire class of work and it cannot be closed by a session — it needs the
maintainer to choose: adopt a CLA, adopt a DCO-with-relicense-grant, or confirm the
repository stays closed indefinitely. Any of the three is fine; *undecided* is the only
state that costs something.

### Also worth recording

`study_pipeline/` exists as `README.md` + an empty `studied_repos/` — Phase 2 machinery,
correctly unbuilt (charter §30). And `.usa/foundation.yaml` declares `testing.minCoverage:
0`; coverage is measured at 89% but **no threshold is enforced**, which
`pyproject.toml:70-72` acknowledges honestly. Setting it to something real is a
five-minute change worth making now that there is code to measure.

---

## 8. Decisions of record — the complete ledger

| ADR | Decision | Status |
|---|---|---|
| 0000 | ADR format | Accepted |
| 0001 | Knowledge/code plane split | Accepted |
| 0002 | Apache-2.0 (supersedes the Proposed state) | Accepted |
| 0003 | Toolchain & enforcement (ruff lints, black formats) | Accepted |
| 0004 | Close testing-enforcement holes | Accepted |
| 0005 | Name foundation work Phase 0; add phase plans | Accepted |
| 0006 | `tool-registry` — **IMPLEMENT** standalone JSON-Schema registry | Accepted |
| 0007 | `model-provider-abstraction` — **IMPLEMENT**, own the shape not the socket | Accepted |
| 0008 | `react-agent-loop` — **IMPLEMENT** a bounded dispatcher, not a reasoner | Accepted |

**Still binding and load-bearing:** ADR-0007 **D-3** (sync-only) names its own reversal
condition. ADR-0008 **D-5** (consecutive-repeat only) is a *stated limitation*, not an
oversight. ADR-0006's `model_visible=False` for `NOT_FOUND` is what forced ADR-0008's
raise-don't-return resolution.

**Absent, correctly:** no ADR for `execution-trace-recorder` — it is only `RESEARCHED`.
Next ADR number is **0009**.

---

## 9. Phase 1 status against its own exit criteria

| Criterion | Status |
|---|---|
| ≥5 categories with a `TESTED` capability | **🔴 3 of 5** — tools, models, agents (of 7 categories in use) |
| Each has research + ADR + spec + impl + tests + `PROVENANCE.md` | ✅ all three |
| `make status` clean | ✅ *"No governance drift detected"* |
| One end-to-end composition in `integrations/` | ✅ 25 tests, no network |
| Registry has real study records, not placeholders | ✅ 18 entries |
| Known limitations documented per capability | ✅ each README has a limitations section |

**Remaining:** `vector-memory-store` (DISCOVERED) · `basic-rag-pipeline` (DISCOVERED,
blocked on the former) · `mcp-client` (DISCOVERED, **unblocked**) ·
`execution-trace-recorder` (RESEARCHED, unblocked).

---

## 10. Verdict, and the four things worth changing

**The direction is aligned. The governance works — better than the score shows. The tests
are real, the decisions are recorded, and the rejections outnumber the implementations
two to one.**

Ordered by value:

1. **Build `mcp-client` next, not `basic-rag-pipeline`.** It is the only capability that
   exercises charter §16, it has no unmet dependencies, and nothing in this repository yet
   talks to anything external. Its own priority note already argues this. Its first design
   question is `AI-010` from §2.
2. **Add a per-run tool allowlist to `RegistryDispatcher`.** The only genuinely unmet
   security rule (`AI-003`). Optional constructor argument, ~10 lines, filters `schemas()`
   and `dispatch()` together.
3. **Adopt a contribution policy, or decide not to.** A §22 human-review item open 14
   sessions. This one needs the maintainer, not a session.
4. **Add `gitleaks`.** The one actionable supply-chain finding now that a provider adapter
   handles API keys.

**And stop reading the headline number.** 72.4 for an empty repository and 73.3 for three
tested capabilities is a score that measures the charter, not the code. Track capabilities,
tests, and integrations instead — those moved 0→3, 195→302, and 0→1 in the same window
where the score moved +0.9.

---

*Deterministic pass by USA 2.21.0; judgement queue worked by an agent, 2026-09-16.*
*Raw report: `2026-09-16-usa-raw.md`. Prior adjudicated audit: `2026-09-15-usa-audit-foundation.md`.*