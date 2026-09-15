# Specifications

Designs that exist **before** code — the DESIGNED stage of the capability lifecycle (charter §4). A specification here means the capability has been researched, understood, and decided (ADR accepted), but not yet implemented.

## Rule

A spec is not implementation (charter §10). Do not add code to this directory.

## Naming

`<capability-id>.md`, matching the `id` in [`../TAXONOMY.md`](../TAXONOMY.md). A spec must state:

- Capability id, name, lifecycle status, and the ADR that decided it
- Problem statement and who needs it (charter §7)
- Interfaces and data flow
- Invariants and failure modes
- Security implications and trust boundaries
- Dependencies (taxonomy `depends_on`) and standards
- Testing strategy (§18) and benchmark plan if meaningful (§19)
- What is explicitly out of scope

## Status

| Specification | Capability | Status |
|---|---|---|
| Specification | Capability | Status |
|---|---|---|
| [`tool-registry.md`](tool-registry.md) | `tool-registry` | ✅ TESTED — decided by [ADR-0006](../docs/decisions/0006-tool-registry.md) |
| [`model-provider-abstraction.md`](model-provider-abstraction.md) | `model-provider-abstraction` | ✅ TESTED — decided by [ADR-0007](../docs/decisions/0007-model-provider-abstraction.md) |
| [`react-agent-loop.md`](react-agent-loop.md) | `react-agent-loop` | ✅ TESTED — decided by [ADR-0008](../docs/decisions/0008-react-agent-loop.md) |
| [`mcp-client.md`](mcp-client.md) | `mcp-client` | ✅ TESTED — decided by [ADR-0009](../docs/decisions/0009-mcp-client.md) |