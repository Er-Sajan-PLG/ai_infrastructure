# Agents & Orchestration

> **Status: 1 capability studied.** This directory is a declared research category (charter §2, ADR-0001).

## What it is

Agent runtimes, agent loops, planners, executors, supervisors, delegation, multi-agent systems, task scheduling, state machines, graph execution, long-running and background agents.

## Why it exists

Every AI system that acts rather than only answers needs a control loop: deciding what to do next, invoking capabilities, and terminating. This category studies how that loop is built and what breaks.

## How it works

To be documented once the first capability in this category is studied. Research artifacts are expected at `research/agents/<capability-id>.md` and must label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

## Variants & types

Not yet surveyed.

## Landscape

Five sources were studied for [`react-agent-loop`](react-agent-loop.md), all registered in
[`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) with the
charter §11 schema and `code_reused: false`:

| Source | What it contributed |
|---|---|
| ReAct (Yao et al., arXiv:2210.03629v3) | The pattern's shape; the evidence that repetition is its most common ReAct-specific failure and is left unmitigated |
| LangGraph react agent executor | A cap trip that yields a readable result; model-readable templated error text |
| OpenAI Agents SDK | Typed next-step values instead of boolean flags; a documented turn unit |
| smolagents | Recording *why* the loop stopped as a state flag; error kinds named by model-actionability |
| LangChain tool error surface | The model-actionability split, corroborating ADR-0006 D-4 independently |

## Our implementations

[`catalog/agents/react_agent_loop/`](../../catalog/agents/react_agent_loop/) — status `TESTED`. See [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

Documented per entry: [`react_agent_loop/README.md`](../../catalog/agents/react_agent_loop/README.md#when-to-use--when-not-to-use).

## References & citations

See [`react-agent-loop.md`](react-agent-loop.md) §8 for primary sources and recorded limitations.
