# Tools

> **Status: 1 study.** OpenAI function calling, LangChain/LangGraph, MCP and Semantic Kernel were surveyed for the `tool-registry` capability.

## What it is

Tool registries, tool calling, function execution, schemas, discovery, routing, permissions, validation, and failure handling.

## Why it exists

Tool calling is the narrow boundary between model intent and real side effects. Its schema, validation, and error semantics determine how safely everything above it composes.

## How it works

Research artifacts live at `research/tools/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

- [`tool-registry.md`](tool-registry.md) — the model-intent-to-execution boundary: declaration, selection, binding, validation, invocation.

## Variants & types

Not yet surveyed.

## Landscape

Four projects studied for `tool-registry`, all registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) with the charter §11 schema and all `code_reused: false`: OpenAI function calling, LangChain/LangGraph, Model Context Protocol, Microsoft Semantic Kernel.

**Key finding:** none of the four ships a genuine tool registry (ADR-0006).

## Our implementations

[`catalog/tools/tool_registry/`](../../catalog/tools/tool_registry/) — status `TESTED`. See [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

To be filled from evidence, not intuition.

## References & citations

None yet.
