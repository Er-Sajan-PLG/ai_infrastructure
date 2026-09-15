# MCP & Protocols

> **Status: 1 capability studied.** This directory is a declared research category (charter §2, ADR-0001).

## What it is

MCP clients, servers, registries, transports, authentication, protocol adapters, bridges, and interoperability layers.

## Why it exists

Interoperating with established protocols is an engineering feature, not a compromise (charter §16). MCP is the current ecosystem answer for tool/resource exposure.

## How it works

To be documented once the first capability in this category is studied. Research artifacts are expected at `research/mcp/<capability-id>.md` and must label claims FACT / OBSERVATION / INFERENCE / DESIGN OPINION (charter §6).

## Variants & types

Not yet surveyed.

## Landscape

Four sources were studied for [`mcp-client`](mcp-client.md), all registered in
[`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)
with the charter §11 schema and `code_reused: false`:

| Source | What it contributed |
|---|---|
| Model Context Protocol | The protocol itself: the two-era fork, the stdio framing rule, the tool schema, the two-mechanism error model, and the security guidance |
| MCP Python SDK (official client) | The POSIX process-group kill, the stderr allowlist, and the cancel-shielded shutdown |
| MCP TypeScript SDK (official client) | A documented 10 MB read-buffer cap, explicit `shell: false`, and backpressure via the drain event |
| mcp-go (independent client) | The only stdlib-only stdio transport surveyed — newline framing, a drop-oldest stderr ring, and a bounded shutdown escalation |

**The finding that shaped the design:** the protocol has forked. `2026-07-28` removed the
`initialize` handshake and made every request carry its own version and capabilities, while
`2025-11-25` and earlier still use the handshake. The spec names the two eras and its
compatibility matrix says a modern client against a legacy server **fails** rather than
degrades — so the era choice determines which servers a client can reach at all.

## Our implementations

None yet — `mcp-client` is `RESEARCHED`. See [`../../TAXONOMY.md`](../../TAXONOMY.md) §4.

## When to use / When not to use

To be documented when the capability reaches `IMPLEMENTED`.

## References & citations

See [`mcp-client.md`](mcp-client.md) §11 for sources, verification method, and the explicit list of what could not be verified.
