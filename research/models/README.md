# Models

> **Status: 1 study.** Provider wire formats (OpenAI, Anthropic, Gemini) and four existing abstractions were surveyed for `model-provider-abstraction`.

## What it is

Model and provider abstractions, routing, selection, fallback, catalogs, inference interfaces, local and remote serving, batching, streaming, structured generation, multimodal inference, embeddings, reranking.

## Why it exists

Every component above needs a model call. Normalizing provider differences, errors, and usage metadata is the abstraction everything else depends on.

## How it works

Research artifacts live at `research/models/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

- [`model-provider-abstraction.md`](model-provider-abstraction.md) — where three providers diverge, and why the abstraction owns shape rather than transport.

## Variants & types

Two families, per the survey: abstractions that **own the transport** (LiteLLM, DSPy, OpenAI SDK) and abstractions over **shape only** (LangChain, LlamaIndex, Haystack). Dependency weight follows this split exactly.

## Landscape

Not yet surveyed. External projects studied will be registered in [`../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) with the charter §11 schema.

## Our implementations

None. See [`../TAXONOMY.md`](../../TAXONOMY.md) §4 for capabilities in this category and their honest lifecycle status.

## When to use / When not to use

To be filled from evidence, not intuition.

## References & citations

None yet.
