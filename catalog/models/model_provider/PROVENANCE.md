# Provenance — `model-provider-abstraction`

Charter §11 draws a hard line between **inspired-by / studied-from** and
**derived-from / contains-reused-code**. This document states which this is.

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

Seven projects were surveyed (session 9), each at a pinned version, against
primary sources — raw GitHub source and official documentation. All are
registered in [`docs/registry/RESEARCH_REGISTRY.md`](../../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`.

| Project | Version studied | What was taken |
|---|---|---|
| LiteLLM | 1.102.0 | **Concept:** `provider/model` addressing ergonomics; a flat normalised error set with status/provider/model attributes; a repeated-chunk guard |
| OpenAI Python SDK | `main` | **Concept:** streams that can fail mid-iteration; separating connection/timeout failures from status failures |
| LangChain `BaseChatModel` | langchain-core 1.6.3 | **Concept:** one required method with everything else derived; async derived via an executor rather than duplicated |
| LlamaIndex `LLM` | llama-index-core 0.14.24 | **Negative finding:** what not to do (eight abstract methods; a fake async façade) |
| OpenAI Messages API (wire) | published OpenAPI spec | **Wire compatibility target** for the OpenAI adapter |
| Anthropic Messages API (wire) | `anthropic-version: 2023-06-01` + SDK source | **Wire compatibility target** for the Anthropic adapter |
| Google Gemini GenerateContent (wire) | `v1beta` + official SDK types | **Wire compatibility target** for the Gemini adapter |

**In every case the adoption is conceptual.** Ideas are not copyrightable; their
expression is. No source file, function body, docstring, comment, or test from
any of these projects was copied, paraphrased, or transliterated.

## Why no `NOTICE` update is required

Charter §11 and [`NOTICE`](../../../NOTICE) require a notice update when
`code_reused: true`. That flag is `false` for all seven entries, and no license
obligation attaches to studying a permissively-licensed project or to
independently implementing a documented wire format.

Two specific things keep this defensible:

1. **Wire formats are interfaces, not creative works.** Implementing a published
   HTTP+JSON API by reading its specification is interoperability, not copying.
   The payload fixtures in the tests are *shaped from documentation*, not lifted
   from any project's test suite.
2. **No structurally-mirrored code.** Where a concept was adopted, the
   implementation differs in shape and naming. The clearest case is error
   classification: LiteLLM achieves it by subclassing `openai.*` and matching
   substrings of `str(exception)` across ~2,753 lines. Here it is a small
   function over an explicit `ErrorSignals` record containing only structured
   fields — with message text deliberately *unavailable* to it.

## Ideas adopted, and how they differ from their sources

| Idea | Source | This implementation |
|---|---|---|
| `provider/model` addressing | LiteLLM | An explicit provider object; no string parsing, no detection cascade |
| Normalised error set | LiteLLM | A closed `ErrorKind` enum plus an `ErrorSignals` input that structurally *prevents* text matching |
| Streams that fail mid-iteration | OpenAI SDK | `ProviderStream`, which normalises foreign exceptions into `ProviderError` while passing genuine `ProviderError` through unchanged |
| One required method, rest derived | LangChain | The `Provider` protocol has a small required surface; nothing is faked |
| Async derived, not duplicated | LangChain | **Not implemented** — sync-only, with the absence documented (D-3) |
| Fallible iterators over callbacks | OpenAI SDK, LangChain | A single representation; no dual callback/generator path |
| Usage as an optional field bag | LlamaIndex (`additional_kwargs`) | Typed optional fields plus `is_complete()`, so "unknown" is expressible |

## Negative provenance — deliberately avoided

Recorded so a future session does not "helpfully" reintroduce them:

- **Subclassing another vendor's exception hierarchy.** LiteLLM's
  `class RateLimitError(openai.RateLimitError)` is why it can never shed the
  OpenAI SDK. Disqualifying for a zero-dependency primitive.
- **Owning HTTP transport.** The direct cause of LiteLLM's 14 base dependencies
  including `boto3`.
- **Text-matched error classification.** The ~2,753-line mapper is what
  `ErrorSignals` exists to make impossible.
- **Fake async.** LlamaIndex's `async def achat: return self.chat(...)` blocks the
  event loop while appearing asynchronous.
- **String-prefix provider detection.** LiteLLM's 894-line
  `get_llm_provider_logic.py`; this design has no detection at all, because the
  caller selects the provider explicitly.
- **`extra='allow'` smuggled fields.** LiteLLM carries delta fields this way,
  invisible to `mypy --strict` and to any schema.
- **Collapsing reasoning into output text.** Would corrupt the transcript; left
  unrepresented rather than misrepresented.
- **Silent schema downgrades.** LiteLLM strips JSON-Schema keywords a provider
  rejects. Here, an inexpressible request raises `TranslationError` before any
  bytes are sent.

## Verification

- The package imports only `__future__`, `collections.abc`, `dataclasses`, `enum`, `json`, `types`, and `typing`. Asserted by `test_no_third_party_imports`.
- No file in this directory contains code from any surveyed project.
- Licenses were confirmed at the version studied, per the registry rule that licenses change.

## Maintainer sign-off

Per charter §22, `code_reused: true` would require human review. It is `false`
here, so no gate is triggered — but the classification is recorded explicitly so
the claim is auditable rather than assumed.