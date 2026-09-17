# ADR-0017: Structural checks — import-linter and a first-party collectability gate

- **Status:** Accepted
- **Date:** 2026-09-17
- **Phase:** 1.5 (Hardening)
- **Related:** [ADR-0013](0013-verification-breadth.md), [`../../CHARTER.md`](../../CHARTER.md) §31

## Context

Charter §31 requires catalog entries to be **independent and relocatable**: a
consumer adds `catalog/<category>/` to `sys.path` and imports the entry by its
bare name. Nothing enforced that. Two distinct holes existed:

1. **Cross-entry imports.** `react_agent_loop` composes `model_provider` and
   `tool_registry`; `mcp_client` composes `tool_registry`. Those are legitimate.
   What is not legitimate is an entry importing another entry's *internal*
   submodule, or a leaf entry acquiring a dependency on a peer. A per-file AST
   walk can see the first and is **blind to the transitive form**
   (`entry_a → shared_helper → entry_b`).
2. **Uncollectable tests.** A directory whose tests collect **zero items**
   reports success. An entry could ship a `tests/` directory that never runs a
   single test while every gate stayed green.

### The measured dependency graph

Established by measurement, not inspection:

```
react_agent_loop → model_provider, tool_registry
mcp_client       → tool_registry
model_provider, tool_registry, execution_trace_recorder : leaves
```

**Zero internal reach-ins.** Every cross-entry import goes through a public
interface. This measurement is what makes the contracts below expressible, and
it was not assumed.

## Decision

**1. Adopt `import-linter` for entry independence**, configured in the
`[tool.importlinter]` block of `pyproject.toml`.

**2. Keep a first-party collectability check** (`scripts/check_collectability.py`),
because no off-the-shelf tool answers "is this entry's `tests/` collectable?"

### The contracts, and why they are shaped this way

Three contracts, all currently KEPT (56 files, 220 dependencies analysed):

```toml
# 1. Leaves stay leaves
type = "independence"
modules = ["model_provider", "tool_registry", "execution_trace_recorder"]

# 2. Composing entries do not become mutually entangled
type = "independence"
modules = ["react_agent_loop", "mcp_client"]

# 3. No entry may depend on an integration
type = "forbidden"
source_modules = [all five entries]
forbidden_modules = ["agent_loop_end_to_end"]
```

**The important negative result:** the obvious contract — `forbidden` on
another entry's internal submodules — was **written first, and it fails on
correct code.** This was reproduced, not predicted. The reported chain was:

```
mcp_client.jsonrpc -> tool_registry (l.25)
tool_registry      -> tool_registry.ids (l.39)
```

import-linter builds the real import **graph**. Forbidding
`tool_registry.ids` therefore flags the entirely legitimate
`from tool_registry import X`, because `tool_registry/__init__.py` imports
`.ids` internally and the graph walk follows that edge. The chain is real; the
violation is not. **The caller did not reach in — the package did.**

That reproduction is why contracts 1 and 2 use `independence`, and it is why
the "no reaching into internals" rule is documented as a **review rule rather
than claimed as a standard** (charter §20). It is recorded as **AR-004** in
[`../risks/ACCEPTED_RISKS.md`](../risks/ACCEPTED_RISKS.md) so the gap is
visible rather than implied to be covered.

### Configuration location is load-bearing

`import-linter` reads `setup.cfg` and `.importlinter` as **INI**, and only
`pyproject.toml` as **TOML**. Placing the TOML block in a `.importlinter` file
fails with:

```
While reading from '<string>' : section '' already exists
```

That mistake was made and diagnosed in this repository. A `.importlinter` file
was created, failed, and deleted. The comment in `pyproject.toml` records it.

### Why `PYTHONPATH` is required

Entry packages are **not importable from a plain interpreter** — verified:

```
$ .venv/bin/python -c "import model_provider"
ModuleNotFoundError: No module named 'model_provider'
```

They resolve under pytest only because pytest's default `prepend` import mode
inserts each test file's rootdir into `sys.path`. Nothing else does. The
`independence` target therefore sets `PYTHONPATH` to the directories a
**consumer** is documented to use, derived from `$(wildcard
catalog/*/*/__init__.py)` rather than hard-coded, so it cannot go stale when an
entry is added.

### The collectability check

First-party, because nothing else does this. It:

- discovers entries by the presence of a `tests/` directory, and refuses to
  pass if it finds fewer than `MIN_EXPECTED_ENTRIES = 5` (anti-silent-skip);
- reads `python_files` from pytest's **own** config rather than hard-coding
  `test_*.py`;
- distinguishes exit code 5 (collected nothing) from another non-zero exit (a
  collection **error**) — two very different facts that must not be conflated;
- parses the per-file counts pytest actually prints (`path: 58`), not the
  summary line.

A first version looked for `"58 tests collected"`. `pytest -q --collect-only`
prints `path/to/test_x.py: 58`. It reported six false "collects ZERO tests"
failures, which would have led to deleting a working gate. The regex was fixed
against real output.

## Verification performed

Both gates were proved to have teeth by introducing a real violation and
confirming failure:

- **Independence:** adding `from execution_trace_recorder import TraceRecorder`
  to `tool_registry/__init__.py` (a leaf-to-leaf violation) made the gate exit
  2 with `tool_registry is not allowed to import execution_trace_recorder:
  - tool_registry -> execution_trace_recorder (l.30)`. Restored: 3 kept, 0 broken.
- **Collectability:** a probe entry with an empty `tests/` made the gate exit 1.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| Custom AST script for independence | **Rejected** | Cannot see transitive leakage, and reimplements a solved problem. `import-linter` detects chains a per-file walk misses. |
| `forbidden` on internal submodules | **Rejected after reproduction** | Fails on correct code — see above. Would have been a permanently-red gate or a permanently-disabled one. |
| Blanket `independence` over all five entries | **Rejected** | Wrong: `react_agent_loop` legitimately depends on two peers. The measured graph is what makes the correct grouping possible. |
| `pytest --collect-only` in a loop, no dedicated script | **Rejected** | That is what the script does; the script exists for the exit-code semantics, the pytest-config read, and the anti-silent-skip floor. |
| `import-linter` as a runtime dependency | **Rejected** | It is dev-only. The zero-runtime-dependency property is preserved; verified by `dependencies = []`. |
| Add a `sys.path` shim so entries import by full path | **Rejected** | Would break the documented consumer contract (bare-name import, charter §31). The `PYTHONPATH` approach matches how entries are actually consumed. |

## Consequences

**Positive.** Transitive leakage is detectable. Entry independence is enforced
rather than asserted. The two gates cost about a second combined and run in
pre-commit as well as CI.

**Negative / accepted costs.**

- Two new dev dependencies (`import-linter`, and `grimp` transitively).
- Static analysis sees **explicit** imports only. `importlib.import_module`,
  `__import__`, string-named modules and `__init__` re-export chains are
  invisible. Accepted and recorded as **AR-005**: the check makes *accidental*
  violations near-impossible and deliberate ones visible in review; it is not a
  security boundary.
- The internal-reach-in rule is a review rule, not a check (AR-004).
- `include_external_packages = true` is required because contract 3 names a
  module outside `root_packages`. Without it the contract would pass by never
  being evaluated — a silent no-op, which is worse than no contract.

## Compliance

- [`CHARTER.md`](../../CHARTER.md) §31 — component independence. This is the
  enforcement.
- §20 — the non-enforceable half is labelled a preference and recorded (AR-004),
  not claimed as a standard.
- §4 — every claim here is backed by a reproduction.
- Enforced by: `make independence`, `make collectability`, `make check-strict`,
  and the pre-commit hook.
