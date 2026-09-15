# Protocols (catalog)

> **Status: 1 entry, `TESTED`.** This directory holds independent implementations at IMPLEMENTED or later (charter §4, §27).

## What it is

Protocol clients, servers, and adapters, including an MCP client and other interoperability layers.

## Why it exists

Standard-compatible interfaces with independent internal implementations (charter §16).

## How it works

Each entry documents its own architecture. The shared pattern in this category is
a **protocol seam**: the wire format is owned by the entry, and the transport is
an injected protocol, so every protocol path is testable with no network and no
real peer.

## Variants & types

| Entry | What it is |
|---|---|
| [`mcp_client`](mcp_client/) | An MCP client for the **legacy** era (`initialize` handshake, `2025-06-18` and earlier) over stdio, with a mandatory approval seam. `TESTED`, 44 tests. |

## Landscape

Four sources studied for `mcp-client`, registered in
[`../../docs/registry/RESEARCH_REGISTRY.md`](../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`: the MCP specification, both official SDKs, and
`mark3labs/mcp-go` as an independent client.

**The finding that shaped the category:** the protocol has forked. `2026-07-28`
removed the `initialize` handshake and made every request carry its own version
and capabilities; `2025-11-25` and earlier still use the handshake. The spec
names the eras and says a modern client against a legacy server **fails** rather
than degrades — so the era is a compatibility decision, not a preference.

## Our implementations

[`mcp_client`](mcp_client/) — `TESTED`. The only capability in this repository
whose subject is another system's protocol.

## When to use / When not to use

Use an entry in this category when you must interoperate with an established
protocol and want the implementation to remain independently testable — the
transport is a seam, so the protocol logic runs against doubles.

Do **not** expect an entry here to sandbox a remote peer. `mcp_client` constrains
*how* a server process is spawned, not *what* it may do once running.

## Entry contract

Every entry under this directory is a subdirectory containing:

```text
<capability_id>/
├── README.md          # Category documentation standard (charter §13)
├── PROVENANCE.md      # Original source, license, what was changed and why (§11)
├── <implementation>   # Python, type-hinted, ruff-linted, black-formatted
├── examples/          # Runnable usage examples
└── tests/             # Unit/integration tests (§18)
```

Validate with `python ../../scripts/validate_catalog.py`.

## References & citations

None yet.
