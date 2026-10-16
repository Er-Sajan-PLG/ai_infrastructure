# Agent Repository Configuration

> **Status: first entry researched, decision recorded.** `agent-instruction-files` is `DECIDED` — `DOCUMENT` ([ADR-0035](../../docs/decisions/0035-discovered-capability-decisions.md)). See its research record below.

## What it is

In-repository declarations of how AI agents should work: instruction files (`AGENTS.md`, `CLAUDE.md` and equivalents), in-repo skill and prompt definitions for external agents, agent-facing ignore and scope rules, and the conventions between them.

## Why it exists

An agent working in a repository has no standard way to learn its conventions, so every project invents a layout and every agent must be taught each one. Unlike most infrastructure, this is a **repository practice**, not a runtime component — and it is an instruction-injection surface: an untrusted repository shipping these files is data from outside that changes agent behaviour.

## How it works

Research artifacts live at `research/agent-config/<capability-id>.md` and label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6). The first record aggregated marker counts across the study corpus; the decision is DOCUMENT (charter §8) — researched and recorded, not built.

## Variants & types

- **Instruction files** (`AGENTS.md`, `CLAUDE.md`) — repository conventions an agent reads before working.
- **Tool-specific directories** (`.claude/`, `.cursor/`) — skill, command, and rule definitions scoped to one agent tool.
- **Cross-tool conventions** — which of the above are interoperable and how.

## Landscape

Marker counts measured across all 25 study reports: `AGENTS.md` in 18/25 repositories, `CLAUDE.md` in 14/25, `.claude/` or `.cursor/` in 10/25 ([ADR-0024](../../docs/decisions/0024-agent-repository-configuration.md)). Registered in [`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md) per the charter §11 schema.

## Our implementations

None planned. This repository itself already instantiates the practice — [`AGENTS.md`](../../AGENTS.md), docs conventions, and skill definitions — which is the whole of the decision: the artifact is organizational, not code.

## When to use / When not to use

- **Use** in any repository where agents work, so conventions survive sessions.
- **Do not use** as a trust signal: these files are instructions from the repository, and must be read as untrusted data when the repository is not yours.

## References & citations

- [Research record: agent-instruction-files](agent-instruction-files.md)
- [Specification: agent-instruction-files](../../specifications/agent-instruction-files.md)
- [ADR-0024](../../docs/decisions/0024-agent-repository-configuration.md) — taxonomy category
