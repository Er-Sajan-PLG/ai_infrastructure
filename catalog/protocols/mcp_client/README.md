# MCP Client (stdio transport)

> **Status: `TESTED`.** Speaks the legacy MCP handshake over an injected
> transport, lists tools, calls them, and projects the results into the local
> tool registry. Zero runtime dependencies; the server process is the only thing
> outside the standard library, and it is spawned, not imported.

| | |
|---|---|
| **Capability** | [`mcp-client`](../../../TAXONOMY.md) (category: protocols) |
| **Specification** | [`specifications/mcp-client.md`](../../../specifications/mcp-client.md) |
| **Decision** | [ADR-0009](../../../docs/decisions/0009-mcp-client.md) — `COMPATIBILITY` |
| **Research** | [`research/mcp/mcp-client.md`](../../../research/mcp/mcp-client.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — inspired-by, **not** derived-from |
| **Depends on** | [`tool-registry`](../../tools/tool_registry/) (`TESTED`) |
| **Standard** | Model Context Protocol, revision `2025-06-18` (legacy era) |

## What it is

A thin MCP client for the **legacy** protocol era. It spawns a server over
stdio, performs the `initialize` handshake, lists the tools the server offers,
asks the server to run one, and registers the server's tools in a local
`ToolRegistry` so anything that already consumes the registry can use them.

It is the first capability in this repository whose subject is **another
system's protocol**. Every capability below it defined its own boundary; this one
has a boundary it does not control.

## Why it exists

Charter §16: interoperating with an established protocol is an engineering
feature, not a compromise. MCP is the current ecosystem answer for tool
exposure, so a working client reaches more tooling than any private protocol
would — and the taxonomy scopes it as a *thin working client* rather than a
comprehensive one that is never finished.

Two findings shaped the design, both from
[`research/mcp/mcp-client.md`](../../../research/mcp/mcp-client.md):

1. **The protocol has forked.** Revision `2026-07-28` removed the `initialize`
   handshake and made every request carry its own version and capabilities.
   `2025-11-25` and earlier still use the handshake. The specification names the
   two eras — Modern and Legacy — and its compatibility matrix says a modern
   client against a legacy server **fails** rather than degrades. The era choice
   therefore determines which servers a client can reach at all.
2. **The specification asks for a human in the loop.** Its tools page carries a
   `<Warning>` that *"there SHOULD always be a human in the loop with the ability
   to deny tool invocations."* This client dispatches to **processes we did not
   write**, so unlike `react-agent-loop` the deferral of `AI-010` does not carry
   over.

## How it works

```python
from mcp_client import MCPClient, project_tools
from tool_registry import ToolRegistry

registry = ToolRegistry()
client = MCPClient.from_command(
    "some-mcp-server", ["--flag"], namespace="remote",
    approvals=AllowAllApprovals(),   # the decision is spelled out
)
try:
    client.initialize()
    report = project_tools(client, registry)
    print(report.registered_count, "registered;", report.excluded_count, "excluded")

    result = registry.invoke(ToolId("remote", "echo"), {"text": "hi"})
finally:
    client.close()
```

Run the full tour — no network, no real server, scripted transport:

```bash
.venv/bin/python catalog/protocols/mcp_client/examples/quickstart.py
```

### The pieces

| Module | Owns |
|---|---|
| `framing.py` | Newline-delimited JSON. Compact serialisation, plus an assertion that no emitted line contains a newline. |
| `jsonrpc.py` | Envelopes, `id` correlation, and the error-code → `FailureKind` mapping. |
| `transport.py` | `Transport` protocol, `StdioTransport`: spawn, drain `stderr`, shut down the process group. |
| `approvals.py` | The `ApprovalPolicy` seam consulted before every dispatch. |
| `client.py` | The handshake, `tools/list` pagination, `tools/call`. |
| `projection.py` | Registering remote tools in a `ToolRegistry` — the only module that imports it. |

### Security posture

- **No shell.** The server is spawned from an argv array with `shell=False`, so a
  `;` in a config value is an argument, not a command.
- **The namespace is client-minted.** `ToolId(namespace, remote_name)` where
  `namespace` is a constructor argument. The spec warns that `serverInfo.name` is
  neither unique nor trustworthy and **must not** be relied on for security
  decisions, so it is never used as an identifier.
- **`stderr` is not an error signal.** It is drained continuously into a bounded
  drop-oldest ring — the drain prevents the OS pipe from filling and deadlocking
  the child, and the spec says clients *"SHOULD NOT assume stderr output
  indicates error conditions."*
- **Tool annotations are untrusted by default.** The spec's only client-side
  `MUST`. They are never consulted for a decision.
- **Approval is mandatory and the default denies.** `approvals=None` becomes
  `DenyAllApprovals()`. To get an autonomous client a caller writes
  `AllowAllApprovals()` — a name that reads as the decision it is.

## Our implementations

| Implementation | Notes |
|---|---|
| `mcp_client` | This entry. `TESTED`, 44 tests. |

### Least privilege — reusing the `AI-003` allowlist

The projection is not a capability grant. Projecting a server's fifty tools into
a registry does not mean a run should be offered all fifty; pass the registry to
`RegistryDispatcher(registry, allowed=frozenset({...}))` from `react-agent-loop`
to narrow what a model is offered. Remote tools are governed by the same
allowlist as local ones, because they are indistinguishable once projected.

## When to use / When not to use

**Use it** when you need tools from an MCP server that speaks the legacy
handshake, and you want them to look like local tools.

**Do not use it** when:

- the server advertises `2026-07-28` only — the modern era is **not implemented**
  (ADR-0009 D-1), and the client reports that as a named error rather than
  retrying;
- you need resources, prompts, sampling, roots, or logging — only tools are in
  scope;
- you expect the client to sandbox the server. It constrains *how* the child is
  spawned, not *what* it may do once running.

## Known limitations

Stated here so they are not assumed away (spec §11):

1. **Legacy era only.** The largest limitation. A modern-only server is
   unreachable by design, not by omission.
2. **No automatic restart.** A server death raises `MCPServerDiedError` carrying
   the `stderr` tail; reconnect policy is the caller's.
3. **No child sandboxing.** This is not a security boundary for the server.
4. **Approval is a seam, not a guarantee.** `AllowAllApprovals` permits
   everything.
5. **The projection is lossy by design.** A tool the registry cannot represent is
   **excluded**, not adapted. Two cases arise in practice: a remote name
   containing uppercase (MCP allows it, `ToolId` does not), and an `inputSchema`
   using a keyword outside the registry's documented subset — including an
   explicit `$schema`, which `tool-registry` rejects as an unsupported keyword.
   Widening that subset requires an ADR (ADR-0006), so exclusion is the honest
   response. `ProjectionReport.why(name)` returns the reason.
6. **The timeouts are choices.** `30.0` / `2.0` / `3.0` are documented defaults,
   not specification values — the spec supplies no numbers.
7. **`stderr` can be truncated.** The ring is bounded at 64 KiB; a chatty
   server's earliest output is dropped.
8. **Sync-only**, consistent with ADR-0007 D-3 and ADR-0008 D-3.

## Testing

44 tests, no network. Two layers:

- **Scripted transport** — every protocol path: handshake, pagination, `id`
  correlation, each error code, approval denial, timeout, server death,
  malformed stdout, and every projection exclusion.
- **A real child process** — a small stdio server written to a temp file and
  spawned with `sys.executable`. The only test that exercises spawning, real pipe
  framing, `stderr` draining, and process-group shutdown.

## References

- [`specifications/mcp-client.md`](../../../specifications/mcp-client.md)
- [`docs/decisions/0009-mcp-client.md`](../../../docs/decisions/0009-mcp-client.md)
- [`research/mcp/mcp-client.md`](../../../research/mcp/mcp-client.md) — four
  sources surveyed, all `code_reused: false`
- [`PROVENANCE.md`](PROVENANCE.md)