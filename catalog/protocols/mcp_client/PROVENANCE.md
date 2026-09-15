# Provenance — `mcp-client`

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

Four sources were surveyed (session 16), all against primary material — the
specification repository at `main`, and the two SDKs' source files. All are
registered in [`docs/registry/RESEARCH_REGISTRY.md`](../../../docs/registry/RESEARCH_REGISTRY.md)
with `code_reused: false`.

| Source | License | Version studied | What was taken |
|---|---|---|---|
| Model Context Protocol | MIT | `schema/2026-07-28/schema.ts`, `basic/transports/stdio.mdx`, `server/tools.mdx`, `changelog.mdx`, and the `2025-06-18` counterparts | **Specification:** the framing rule, the `Tool`/`CallToolResult` shapes, the two-mechanism error model, the security guidance. A specification is not code; implementing it is the point |
| MCP Python SDK | MIT | `main`, `src/mcp/client/stdio.py`, `shared/jsonrpc_dispatcher.py`, `os/posix/utilities.py` | **Concept:** the POSIX process-**group** kill via `os.killpg` with `start_new_session=True`, and the `stderr` allowlist |
| MCP TypeScript SDK | MIT | `main`, `packages/client/src/client/stdio.ts` | **Concept:** an explicit documented read-buffer bound; explicit `shell: false` |
| mcp-go | MIT | `main`, `client/transport/stdio.go` | **Concept:** the continuously-drained drop-oldest `stderr` ring, serialised frame writes, the bounded shutdown escalation |

**In every case the adoption is conceptual.** Ideas are not copyrightable; their
expression is. No source file, function body, docstring, comment, or test from
any of these projects was copied, paraphrased, or transliterated.

The MCP specification is the clearest case: it is a *normative document* written
to be implemented. `jsonrpc.py`, `framing.py`, and `client.py` are written from
the specification's prose, not from any implementation of it.

## Why no `NOTICE` update is required

Charter §11 and [`NOTICE`](../../../NOTICE) require a notice update when
`code_reused: true`. That flag is `false` for all four entries, and no license
obligation attaches to studying a permissively-licensed project or to
independently implementing a published specification. The MCP specification
repository is MIT-licensed, and MIT permits independent implementation without
attribution — we cite it anyway, because the registry records what was studied.

## Ideas adopted, and how they differ from their sources

| Idea | Source | This implementation |
|---|---|---|
| Continuously drained `stderr` ring | mcp-go | Same mechanism, independently written: a `deque` of chunks with drop-oldest trimming under a lock, 64 KiB bound |
| Process-**group** kill | Python SDK | Same mechanism: `start_new_session=True` at spawn, `os.killpg` on shutdown. The Go and TypeScript clients kill only the direct child; we follow the SDK here |
| Bounded read buffer | TypeScript SDK | `MAX_LINE_BYTES = 10 MiB`, enforced in two places — the encoder and the reader's accumulator |
| Newline framing | The specification | `str.split` on `\n` with a carried buffer; **not** copied from any implementation |
| Error taxonomy | The specification + ADR-0006 D-4 | The spec's own model-actionability axis, mapped to the registry's existing `FailureKind` — one mapping table in `jsonrpc.py`, decided once |
| Approval seam | The specification's `<Warning>` | **Ours.** The spec asks for a human in the loop and defines no wire mechanism, so the seam is our own construction |

## Negative provenance — deliberately avoided

Recorded so a future session does not "helpfully" reintroduce them:

- **Adopting either official SDK.** The Python SDK needs `anyio`, `pydantic`,
  `httpx2`, `jsonschema`, and `opentelemetry-api` and is async-only; the
  TypeScript SDK's stdio entry requires `cross-spawn`. Both would need their own
  ADR under charter §22 (ADR-0009, rejected alternatives).
- **Vendoring `mcp-go`.** It is a structural reference in another language; no
  code was transliterated.
- **The modern era.** Deferred, not forgotten: the installed base is legacy and
  the seam is additive (ADR-0009 D-1).
- **Staying connected on a non-JSON stdout line** (the Python SDK's choice). A
  dropped message is indistinguishable from a slow one (ADR-0009 D-6).
- **Silently discarding a non-JSON stdout line** (the Go client's choice). Same
  failure mode, with no diagnostic at all.
- **Using `serverInfo.name` as the namespace.** The spec warns it is not unique
  and not trustworthy (ADR-0009 D-4).
- **Downcasing an illegal tool name.** It would collide two distinct remote
  tools; the registry is the authority.
- **Widening `tool-registry`'s schema subset** to accept more MCP schemas. ADR-0006
  says the response to a too-small subset is an ADR adding a dependency, not a
  quiet widening; the projection excludes instead.
- **Retrying a non-legacy protocol version.** The spec says the mismatch fails
  rather than degrades; it is reported as a named error.
- **Using a shell.** No `shell=True` anywhere; asserted by a test that a `;` in
  an argument reaches the server literally.

## Verification

- The package imports only the standard library: `json`, `os`, `select`,
  `signal`, `subprocess`, `threading`, `time`, `collections`, `collections.abc`,
  `dataclasses`, `types`, `typing`, and `__future__` — plus `tool_registry` in
  `projection.py` alone.
- `framing`, `jsonrpc`, `transport`, and `approvals` do **not** import
  `tool_registry`; only `client.py` (for the denial kind) and `projection.py` do.
  Charter §31: the protocol layers are usable without the registry.
- No file in this directory contains code from any surveyed project.
- Licenses were confirmed at the version studied, per the registry rule that
  licenses change.

## Maintainer sign-off

Per charter §22, `code_reused: true` would require human review. It is `false`
here, so no gate is triggered — but the classification is recorded explicitly so
the claim is auditable rather than assumed.