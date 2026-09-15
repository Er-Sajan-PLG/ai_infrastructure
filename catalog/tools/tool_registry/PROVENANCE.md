# Provenance — `tool-registry`

Charter §11 draws a hard line between **inspired-by / studied-from** and
**derived-from / contains-reused-code**. Conflation is a licensing risk. This
document states which this is, precisely.

## Summary

| Question | Answer |
|---|---|
| Does this contain code copied from another project? | **No** |
| Is it a derivative work of another project? | **No** |
| Was it informed by studying other projects? | **Yes** — documented below |
| Does it require a `NOTICE` update? | **No** |
| Does it require `attribution_requirements`? | **No** |
| Provenance class | **original** |

## What was studied

Four projects were surveyed in depth (session 6). All are registered in
[`docs/registry/RESEARCH_REGISTRY.md`](../../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`.

| Project | License | What was taken |
|---|---|---|
| OpenAI function calling | proprietary API (spec repo MIT) | **Concept:** caller-side validation is mandatory; correlation ids; opaque result envelope |
| LangChain / LangGraph | MIT | **Concept:** the injected-argument namespace and its forgery defence; the split between model-fixable and tool-failed errors |
| Model Context Protocol | MIT | **Concept:** the error taxonomy by model-visibility; always emit an explicit `$schema`; a registry's identity must outlive a connection |
| Microsoft Semantic Kernel | MIT | **Concept:** middleware over invocation (adopted as a pattern, deliberately re-placed); metadata separated from the callable |

**In every case the adoption is conceptual.** Ideas are not copyrightable; their
expression is. No source file, function body, docstring, comment, or test from any
of these projects was copied, paraphrased, or transliterated into this
implementation.

## Why no `NOTICE` update is required

Charter §11 and [`NOTICE`](../../../NOTICE) require a notice update when
`code_reused: true`. That flag is `false` for all four entries, and no license
obligation attaches to studying a permissively-licensed project or to
independently implementing a documented concept.

Two specific things were done to keep this defensible:

1. **Quoted evidence, not copied logic.** Where a surveyed project's source
   comment is cited (LangGraph's injection-stripping comment, MCP's error
   rationale), it appears in the **research record and documentation as a
   quotation with attribution** — never in the implementation source.
2. **No structurally-mirrored code.** Where a concept was adopted, the
   implementation is deliberately different in shape and named differently. The
   injected-argument feature is the clearest case: LangChain expresses it via
   `Annotated[..., InjectedToolArg]` and Pydantic; here it is an explicit
   `frozenset[str]` and a hand-written validator, with no shared types, no shared
   call signatures, and no shared error classes.

## Ideas adopted, and how they differ from their sources

| Idea | Source | Our implementation |
|---|---|---|
| Injected arguments not visible to a model | LangChain | Explicit `frozenset[str]` rather than `Annotated` marker magic; two derived schema views |
| Strip caller values for injected keys | LangGraph | Done in `invoke()` from an explicit set, not a runtime annotation scan |
| Errors split by model-actionability | OpenAI, LangChain, MCP | A typed `FailureKind` enum with a `model_visible` property, plus an explicit rule that internal exceptions never become failures |
| Stable identity outliving a connection | *absence* in all four | `ToolId(namespace, name)` frozen dataclass — `frozen=True` for hashability, `order=True` for deterministic enumeration |
| Explicit `$schema` in emitted schemas | MCP (learned from its breakage) | The subset is documented in the specification and enforced by the validator |
| Middleware over invocation | Semantic Kernel | *Not implemented in Phase 1* — recorded as a Phase 2+ consideration, deliberately on a standalone object rather than a god-object container |

**The last row is itself worth noting:** the decision *not* to implement
something is also a design act, and it is recorded rather than left implicit.

## Negative provenance — what was deliberately avoided

Recorded so a future session does not "helpfully" reintroduce them:

- **Pydantic as a dependency.** It is what LangChain and Semantic Kernel both use, and it is why both carry heavy coupling. This repository's foundational component has zero runtime dependencies (ADR-0003).
- **Docstring-derived schemas.** LangChain's own maintainers pushed back on expanding docstring parsing, and its two entry points disagree on defaults.
- **A name-encoded namespace.** Semantic Kernel's `"Plugin-function"` is parsed back; ours is a structured value that is never re-parsed.
- **Unconditional telemetry imports in the core type.** Semantic Kernel's `kernel_function.py` imports OpenTelemetry and instruments every call. This package imports nothing outside the standard library.

## Verification

- The implementation imports only `__future__`, `collections.abc`, `dataclasses`, `enum`, `re`, `types`, `typing`. This is asserted by a test (`test_no_third_party_imports`).
- No file in this directory contains code from any surveyed project.
- License status was confirmed at the version studied, per the registry rule that licenses change.

## Maintainer sign-off

Per charter §22, `code_reused: true` would require human review. It is `false`
here, so no gate is triggered — but the classification is recorded explicitly so
that the claim is auditable rather than assumed.