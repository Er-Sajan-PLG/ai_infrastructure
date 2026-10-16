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
| [`tool-registry.md`](tool-registry.md) | `tool-registry` | ✅ TESTED — decided by [ADR-0006](../docs/decisions/0006-tool-registry.md) |
| [`model-provider-abstraction.md`](model-provider-abstraction.md) | `model-provider-abstraction` | ✅ TESTED — decided by [ADR-0007](../docs/decisions/0007-model-provider-abstraction.md) |
| [`react-agent-loop.md`](react-agent-loop.md) | `react-agent-loop` | ✅ TESTED — decided by [ADR-0008](../docs/decisions/0008-react-agent-loop.md) |
| [`mcp-client.md`](mcp-client.md) | `mcp-client` | ✅ TESTED — decided by [ADR-0009](../docs/decisions/0009-mcp-client.md) |
| [`execution-trace-recorder.md`](execution-trace-recorder.md) | `execution-trace-recorder` | ✅ TESTED — decided by [ADR-0010](../docs/decisions/0010-execution-trace-recorder.md) |
| [`infrastructure-scanner.md`](infrastructure-scanner.md) | `infrastructure-scanner` | ✅ TESTED — decided by [ADR-0029](../docs/decisions/0029-infrastructure-scanner.md) |
| [`vector-memory-store.md`](vector-memory-store.md) | `vector-memory-store` | ✅ TESTED — decided by [ADR-0033](../docs/decisions/0033-vector-memory-store.md) |
| [`basic-rag-pipeline.md`](basic-rag-pipeline.md) | `basic-rag-pipeline` | ✅ TESTED — decided by [ADR-0034](../docs/decisions/0034-basic-rag-pipeline.md) |
| [`config-and-settings.md`](config-and-settings.md) | `config-and-settings` | ⏸️ DEFERRED — decided by [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) ([DW-014](../docs/DEFERRED.md)) |
| [`response-cache.md`](response-cache.md) | `response-cache` | ⏸️ DEFERRED — decided by [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) ([DW-015](../docs/DEFERRED.md)) |
| [`agent-instruction-files.md`](agent-instruction-files.md) | `agent-instruction-files` | 📄 DOCUMENT — decided by [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) |
| [`guardrails.md`](guardrails.md) | `guardrails` | ⏸️ DEFERRED — decided by [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) ([DW-016](../docs/DEFERRED.md)) |
| [`rate-limiting.md`](rate-limiting.md) | `rate-limiting` | ⏸️ DEFERRED — decided by [ADR-0035](../docs/decisions/0035-discovered-capability-decisions.md) ([DW-017](../docs/DEFERRED.md)) |