# Specification: `mcp-client`

| Field | Value |
|---|---|
| **Capability id** | `mcp-client` |
| **Name** | MCP Client (stdio transport) |
| **Category** | protocols |
| **Lifecycle status** | `DESIGNED` |
| **Deciding ADR** | [ADR-0009](../docs/decisions/0009-mcp-client.md) — decision: **COMPATIBILITY** |
| **Research record** | [`research/mcp/mcp-client.md`](../research/mcp/mcp-client.md) |
| **Dependencies** | `tool-registry` (`TESTED`) |
| **Standards** | Model Context Protocol, revision `2025-06-18` (legacy era) |
| **Runtime dependencies** | **none** (ADR-0003, ADR-0009) |

Claims are labelled per charter §6: **FACT · OBSERVATION · INFERENCE · DESIGN OPINION**.

---

## 1. Problem and who needs it

> Connect to an MCP server over stdio, list its tools, call them, and project the
> results into the local tool registry — with a human decision point before any
> tool that has a side effect is invoked.

**This is the first capability whose subject is another system's protocol.** Every
capability below it defined its own boundary. This one has a boundary it does not
control, and the research record establishes what that costs
([`research/mcp/mcp-client.md`](../research/mcp/mcp-client.md)).

**Who needs it** (charter §7 — real demand):

| Consumer | Needs from this capability |
|---|---|
| `react-agent-loop` | Remote tools that look identical to local ones, via `ToolRegistry` |
| `integrations/agent_loop_end_to_end` | A second, external tool source to compose with |
| A harness author | To reach the MCP ecosystem without adopting an SDK |
| Charter §16 | Interoperability demonstrated rather than asserted |

---

## 2. The era decision — D-1, and it is the first decision

**FACT** (research §2): the protocol has forked. Revision `2026-07-28` removed the
`initialize` handshake and made every request carry its own version and
capabilities in `_meta`; `2025-11-25` and earlier still use the handshake. The
specification names the two eras — **Modern** and **Legacy** — and its
compatibility matrix states that a modern client against a legacy server
**fails** rather than degrades.

**Decision: this capability implements the LEGACY era only.**

*Why:*

1. **The installed base is legacy.** A modern-only client cannot complete a
   handshake with any server that exists today, so it would reach nothing. The
   taxonomy scopes this capability as *"a thin working client"*; a client that
   cannot connect to a deployed server is not working.
2. **`initialize` is the smaller, better-understood surface.** It is one
   request/response plus one notification, with `ServerCapabilities` returned
   inline. The modern path adds `server/discover`, per-request `_meta` on
   *every* call, a required `resultType` on every result, and the
   `input_required` multi-round-trip outcome. That is a larger machine serving
   the same Phase 1 purpose.
3. **The era is confined to one module.** Framing, process lifecycle, request
   correlation, the error mapping, the `Tool` descriptor, and the projection into
   `ToolRegistry` are **identical in both eras** (research §3.1.1 — the framing
   rule is byte-identical). Adding the modern path later touches `client.py` and
   nothing else.

**Consequence, stated plainly:** this client speaks to legacy servers. A server
that advertises `2026-07-28` and dropped `initialize` will reject the handshake,
and the client will report that as a named protocol error rather than retrying.
That is a real limitation of the capability, not a bug in it.

**Reversal condition:** when a server advertising `2026-07-28` is reachable for
testing, add the modern path behind the same `Transport`. The seam is `client.py`'s
handshake step; nothing below it changes.

---

## 3. Scope

### In scope

1. **Spawn** a server over stdio from an argv array, never a shell.
2. **Frame** newline-delimited JSON-RPC in both directions.
3. **Handshake** (`initialize` + `notifications/initialized`) and capability check.
4. **`tools/list`**, following `nextCursor` until exhausted.
5. **`tools/call`**, with an **approval decision before dispatch** (§7).
6. **Project** remote tools into a `ToolRegistry` under a **client-minted**
   namespace, so they are usable by anything that already consumes the registry.
7. **Shut down** the child deterministically, including its process group.

### Explicitly out of scope

| Out of scope | Why | Type |
|---|---|---|
| Modern era (`2026-07-28`) | §2 — the installed base is legacy | DEFER |
| Streamable HTTP transport | stdio only; the framing seam exists for it | DEFER |
| Resources, prompts, sampling, roots, logging | Tool use is the taxonomy's stated scope; the others are Deprecated | OUT OF SCOPE |
| `input_required` multi-round-trip | Legacy-era mechanism differs (server-initiated requests); not needed for tool use | OUT OF SCOPE |
| Automatic restart on crash | A restart policy is a caller decision (§9, D-10) | DEFER |
| Async / concurrent requests | ADR-0007 D-3, ADR-0008 D-3 | DEFER |
| An approval **UI** | A library has no UI; the *seam* is in scope, the surface is not | OUT OF SCOPE |
| Sandboxing the child process | Not claimed by `tool-registry` either (§8) | OUT OF SCOPE |
| OAuth / authorization | stdio servers inherit the caller's credentials; nothing to negotiate | OUT OF SCOPE |

---

## 4. Interfaces and data flow

### 4.1 Shape

```
  MCPClient(command, args, namespace, approvals=…)
        │
        ├── Transport  (protocol; StdioTransport is the Phase 1 implementation)
        │      send(bytes) / receive() -> bytes|None / stderr_tail() / close()
        │
        ├── framing     newline-delimited, compact, no embedded newline
        ├── jsonrpc     id correlation, request/response/notification
        └── approvals   consulted before every tools/call
```

### 4.2 The `Transport` protocol — D-2

```python
class Transport(Protocol):
    def send(self, line: bytes) -> None: ...
    def receive(self, timeout: float) -> bytes | None: ...
    def stderr_tail(self) -> str: ...
    def close(self, *, grace: float) -> None: ...
```

**Why a protocol rather than an import of `subprocess`:** every protocol test then
runs against a scripted double with no child process, and the real stdio path is
tested separately for exactly what it owns — spawning, framing, draining, killing.
This mirrors ADR-0007 D-1 (inject the socket) and ADR-0008 D-1 (inject the
dispatcher).

**`stderr` is not an error channel.** The spec forbids assuming it (research §3.2).
`stderr_tail()` exists so a *process death* can be explained; it is never consulted
to decide whether a call succeeded.

### 4.3 The approval seam — D-3, and this is the `AI-010` answer

```python
@dataclass(frozen=True)
class ApprovalRequest:
    tool_name: str          # the remote name, as the server reported it
    arguments: Mapping[str, object]
    namespace: str          # the client-minted namespace

class ApprovalPolicy(Protocol):
    def decide(self, request: ApprovalRequest) -> bool: ...
```

The client consults `approvals.decide(...)` **before** writing a `tools/call`
frame. A denial produces a `ToolFailure` with `kind=EXECUTION_FAILED` and a
message that says the call was **denied by policy**, which is model-visible
(the model should know its action was refused and can choose differently).

**No default permits anything.** `approvals=None` becomes `DenyAllApprovals()`.
To get an autonomous client a caller must write `AllowAllApprovals()` — a name
that reads as the decision it is.

**Why this exists at all.** The 2026-09-16 audit adjudicated `AI-010`
("consequential actions require human confirmation") a legitimate **DEFER** for
`react-agent-loop`, because that README declares approval gates a non-goal and the
loop dispatches **in-process, to code the caller wrote**. That reasoning does not
carry over here: this client dispatches to **processes we did not write**, and the
protocol's own tools page carries a `<Warning>` that there *"SHOULD always be a
human in the loop with the ability to deny tool invocations."* A declared non-goal
for one capability does not extend to a client talking to third-party servers.

**Honest limitation:** a policy that always returns `True` is indistinguishable
from no policy. The seam makes the decision *possible* and *visible*; it does not
make it *correct*.

### 4.4 Projection into `ToolRegistry` — D-4

`project_tools(client, registry)` registers each accepted remote tool as:

```
ToolId(namespace, remote_name)   # namespace is CLIENT-MINTED, never serverInfo.name
```

**FACT** (research §6.1, §7.4): the specification requires the client to
disambiguate collisions and warns that `serverInfo.name` is *not* guaranteed
unique and **must not** be relied on for security decisions. So the namespace is a
constructor argument — a local config key the caller chose — and the client never
reads the server's self-reported name into it.

Three projection rules, each of which can **exclude** a tool without failing the
listing (the spec's "one malformed tool must not prevent other valid tools"):

| Condition | Outcome |
|---|---|
| Name is not a legal `ToolId.name` | Excluded, counted, reason recorded |
| `inputSchema` exceeds the registry's documented subset | Excluded, counted, reason recorded |
| `inputSchema` is absent or `type != "object"` | Excluded — arguments are always objects |

**OBSERVATION and it is a real boundary defect, not a detail.** MCP permits
`[A-Za-z0-9_.-]` in names; `ToolId` permits `[a-z0-9._-]` (no uppercase). A server
offering `GetWeather` produces a name the registry cannot represent. The registry
is the authority, so the tool is excluded **by name** rather than silently
downcased — downcasing would make two distinct remote tools collide.

---

## 5. Invariants

1. **Every emitted frame is one line.** `encode_message` serialises with
   `separators=(",", ":")` and asserts the result contains no `\n` or `\r`.
   A violation raises rather than writing a corrupt stream (research §3.1).
2. **Every response is matched to its request by `id`.** A response with an
   unknown `id` is a protocol violation and terminates the session.
3. **The namespace is client-minted.** `serverInfo.name` never becomes a
   `ToolId` namespace.
4. **No shell.** The child is spawned from an argv array with `shell=False`.
   A `;` in a config value is an argument, not a command.
5. **A `tools/call` is never written without an approval decision.**
6. **`stderr` output never determines success or failure.**
7. **`close()` is idempotent** and always attempts to reap the child.

---

## 6. Failure modes

| Failure | Surface | Model-visible? |
|---|---|---|
| Server writes a non-JSON stdout line | `MCPProtocolError`; session terminated | n/a — raised |
| Server writes a JSON-RPC **error** for an unknown tool (`-32601`) | `ToolFailure(NOT_FOUND)` | **False** |
| Server rejects arguments (`-32602` from `tools/call`) | `ToolFailure(INVALID_ARGUMENTS)` | **True** |
| Server returns a result with `isError: true` | `ToolFailure(EXECUTION_FAILED)` | **True** |
| Approval policy denies | `ToolFailure(EXECUTION_FAILED)`, "denied by policy" | **True** |
| No response within the timeout | `MCPTimeoutError` | n/a — raised |
| Child exits mid-request | `MCPServerDiedError`, carrying `stderr_tail()` | n/a — raised |
| Child cannot be spawned | `MCPTransportError` | n/a — raised |

### 6.1 The error-mapping asymmetry, resolved — research §10 Q4

**FACT:** MCP files *invalid arguments* as a **protocol error** ("models are less
likely to be able to fix") while our `FailureKind.INVALID_ARGUMENTS` is
**model-visible** (ADR-0006 D-4 — "the model produced these arguments and *can*
correct them").

**Decision: the registry's taxonomy wins, and the divergence is recorded.**
A `-32602` returned from `tools/call` maps to `INVALID_ARGUMENTS` with
`model_visible=True`. The registry's axis — *can the model act on this?* — is the
one that survives contact with a loop, and MCP's own tools page uses the same axis
to partition its two mechanisms. The disagreement is about where *arguments*
belong, and on that one point MCP is being conservative in a direction that costs
the model a self-correction opportunity.

---

## 7. Security implications and trust boundaries

**The server is untrusted code that we execute.** Stated plainly, because it is
the whole risk.

| Boundary | Posture |
|---|---|
| Spawn | argv array, `shell=False`, no interpolation |
| Process group | `start_new_session=True` on POSIX; shutdown signals the **group**, so a wrapper script's grandchildren are reaped |
| `stdout` | Every line must be a JSON-RPC message; anything else terminates the session |
| `stderr` | Drained continuously into a bounded drop-oldest ring — **never** treated as an error signal, and drained so the OS pipe cannot fill and deadlock the child |
| Tool **annotations** | **Untrusted by default** (the spec's only client-side `MUST`); they are advisory claims by an untrusted party and are not consulted for any decision |
| `inputSchema` | Validated against the registry's subset; network `$ref` is never dereferenced and an external `$ref` is rejected, never treated as permissive |
| Consequential actions | Approval seam (§4.3), consulted before every dispatch |
| Child sandboxing | **Not provided.** See §11. |

**What this client does not protect against**, stated so it is not assumed: a
server that lies about what a tool does, a tool whose name is benign and whose
effect is not, or a model persuaded by a tool *result* to request a different
consequential call. The approval seam is the mitigation for the last of those, and
it only works if the policy reads the arguments.

---

## 8. Dependencies and standards

- **`tool-registry`** (`TESTED`) — the projection target. Not imported at module
  scope by `framing`, `jsonrpc`, or `transport`; only `projection.py` imports it.
- **Zero runtime dependencies.** Python standard library only: `subprocess`,
  `threading`, `json`, `signal`, `os`, `select`, `time`, `dataclasses`.
- **Standards:** Model Context Protocol, legacy revision `2025-06-18`; JSON-RPC 2.0.

---

## 9. Decisions carried into ADR-0009

| # | Decision |
|---|---|
| D-1 | **Legacy era only.** Reversal: a reachable modern server. |
| D-2 | Transport is an injected protocol; `StdioTransport` is the Phase 1 implementation. |
| D-3 | **Approval seam required; default denies.** This is the `AI-010` answer. |
| D-4 | Client-minted namespace; projection excludes tools it cannot represent. |
| D-5 | Error mapping follows `FailureKind`; `-32602` on `tools/call` is model-visible. |
| D-6 | A non-JSON stdout line terminates the session. |
| D-7 | `request_timeout_seconds = 30.0`, `shutdown_grace_seconds = 2.0`, `force_kill_seconds = 3.0` — **our numbers**, the spec supplies none. |
| D-8 | Sync-only. |
| D-9 | No automatic restart; the death is surfaced. |
| D-10 | `stderr` ring buffer: 64 KiB, drop-oldest. |

---

## 10. Testing strategy (charter §18)

No network. No real model. Two layers:

1. **Scripted transport.** Every protocol path — handshake, pagination, id
   correlation, each error code, approval denial, timeout, server death,
   malformed stdout — is exercised against an in-memory `Transport` double. This
   is where the failure paths live, and it is why the transport is a protocol.
2. **A real child process.** A small stdio server written to a temporary file and
   spawned with `sys.executable`. This is the only test that exercises spawning,
   real pipe framing, `stderr` draining, and shutdown. It is local; nothing
   leaves the machine.

**Required failure-path tests** (charter §21): non-JSON stdout terminates;
unknown `id` terminates; timeout raises; server death surfaces `stderr_tail`;
approval denial is model-visible and names the policy; an illegal tool name is
excluded without failing the listing; an out-of-subset schema is excluded the same
way; a `;` in an argument reaches the server literally.

**Benchmark plan (charter §19, deferred):** a future benchmark would measure
round-trips per `tools/list` page and the wall-clock cost of a `tools/call`
against a local echo server. Not a Phase 1 concern.

---

## 11. Known limitations, stated before implementation

1. **Legacy era only** (§2). This is the largest one.
2. **No automatic restart** (D-9). A crashed server ends the session.
3. **No child sandboxing.** The client constrains *how* the child is spawned, not
   *what* it may do once running. It is not a security boundary for the server.
4. **Approval is a seam, not a guarantee.** `AllowAllApprovals` is a supported
   configuration and it permits everything.
5. **The projection is lossy by design.** A remote tool the registry cannot
   represent is excluded, not adapted.
6. **The timeouts are choices.** `30.0` / `2.0` / `3.0` are documented defaults,
   not specification values.
7. **`stderr` can be truncated.** The ring is bounded; a chatty server's earliest
   output is dropped.
8. **No resources, prompts, sampling, roots, or logging.**

---

## 12. Out-of-scope summary

See §3. The short version: **one transport, one era, tools only, and a human
decision point that the caller supplies.**