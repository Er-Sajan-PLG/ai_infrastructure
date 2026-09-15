# ADR-0009 — `mcp-client`: Implement the Legacy Era, and Put the Approval Before the Call

- **Status:** Accepted
- **Date:** 2026-09-16
- **Capability:** [`mcp-client`](../../TAXONOMY.md) (category: protocols)
- **Research record:** [`research/mcp/mcp-client.md`](../../research/mcp/mcp-client.md)
- **Specification:** [`specifications/mcp-client.md`](../../specifications/mcp-client.md)
- **Supersedes:** —

## Context

`mcp-client` is capability 5 of 7 and the first whose subject is **another
system's protocol**. Every capability below it defined its own boundary; this one
has a boundary it does not control. Its only dependency, `tool-registry`, is
`TESTED`, so it is unblocked, and the 2026-09-16 audit named it the next capability
to build because it is the only one that exercises charter §16 (interoperability)
and nothing in the repository yet talks to anything external.

Four sources were studied against primary material — the MCP specification, both
official SDKs, and `mark3labs/mcp-go` as an independent client. The findings that
forced this decision:

1. **THE PROTOCOL HAS FORKED, AND THE PREMISE THE SURVEY WAS LAUNCHED WITH WAS
   STALE.** The current revision is `2026-07-28`, not `2025-06-18`. It **deleted
   the `initialize` handshake** and made every request carry its own version and
   capabilities in `_meta`. The specification names the two eras — **Modern**
   (`2026-07-28`+) and **Legacy** (`2025-11-25` and earlier) — and its
   compatibility matrix states that a modern client against a legacy server
   **fails** rather than degrades. The era is therefore not a preference: it
   determines which servers a client can reach at all.

2. **The installed base is legacy.** No deployed server completes a modern
   handshake. A modern-only client would reach nothing.

3. **The reference that fits our dependency rule is the Go client, not an
   official SDK.** The Python SDK requires `anyio` (plus `pydantic`, `httpx2`,
   `jsonschema`, …) and is async-only; the TypeScript SDK's stdio entry needs
   `cross-spawn`. `mark3labs/mcp-go`'s stdio transport is **standard library
   only**, and adopting either official SDK would require its own ADR under
   charter §22.

4. **Two failure modes are silent on a cooperative server.** The Go client drains
   `stderr` continuously into a 64 KiB drop-oldest ring so the OS pipe cannot fill
   and deadlock the child. The Python SDK kills the whole POSIX process **group**
   via `os.killpg`, which *"reaches every descendant atomically, even ones whose
   parent already exited"* — neither the Go nor the TypeScript client does this,
   so both leak grandchildren. A naive implementation gets both wrong and no test
   on a well-behaved server notices.

5. **The error taxonomy converged with our own, on the same axis and for the same
   reason**, with one genuine mismatch: MCP files *invalid arguments* as a
   protocol error ("models are less likely to be able to fix") while our
   `INVALID_ARGUMENTS` is model-visible.

6. **The specification asks for a human in the loop, and we do not have one.**
   The tools page carries a `<Warning>`: *"there SHOULD always be a human in the
   loop with the ability to deny tool invocations."* The 2026-09-16 audit
   adjudicated `AI-010` a legitimate DEFER for `react-agent-loop` — but that loop
   dispatches **in-process, to code the caller wrote**. This client dispatches to
   **processes we did not write**.

7. **`inputSchema` loosened to all of JSON Schema 2020-12**, and the spec requires
   clients to support 2020-12 for schemas without an explicit `$schema`. Our
   registry implements a documented **subset** and rejects unknown keywords
   loudly (ADR-0006 D-2). Same shape as the `mappingproxy` boundary defect
   (session 13): two components correct in isolation, undefined at their seam —
   except this boundary is external and cannot be fixed by relaxing our own rule.

8. **The spec does NOT say what a client does with non-protocol stdout.** Both
   eras' transport pages were read in full and only the *server-side* prohibition
   exists. The three surveyed clients chose three different behaviours, none
   contradicting the standard. It is a decision we must make and document.

## Decision

**COMPATIBILITY** (charter §8) — implement a thin MCP client for the **legacy**
era over **stdio**, with the approval decision taken **before** the call is sent.

`COMPATIBILITY` and not `ADAPT`, because the whole point is to speak an existing
protocol rather than to wrap a library; and not `IMPLEMENT`, because we are
implementing *against* a specification we did not author, which is what that
decision value exists to distinguish.

### D-1. Legacy era only

`initialize` + `notifications/initialized`, with `ServerCapabilities` returned
inline.

*Why:* finding 1 and 2. The installed base is legacy, and the modern path is a
larger machine (`server/discover`, per-request `_meta`, a required `resultType`,
the `input_required` round-trip) serving the same Phase 1 purpose.

*Consequence, accepted:* a `2026-07-28`-only server cannot be reached. That is a
named, reported error, not a retry.

*Reversal:* when a modern server is reachable for testing, add the path behind the
same `Transport`. Only the handshake step changes — framing, correlation, the
error mapping, and the projection are identical in both eras (research §3.1.1).

### D-2. The transport is an injected protocol

```python
class Transport(Protocol):
    def send(self, line: bytes) -> None: ...
    def receive(self, timeout: float) -> bytes | None: ...
    def stderr_tail(self) -> str: ...
    def close(self, *, grace: float) -> None: ...
```

*Why:* every protocol path becomes testable with no child process, and the real
`StdioTransport` is tested for exactly what it owns. Same seam as ADR-0007 D-1 and
ADR-0008 D-1.

### D-3. The approval seam is required, and the default DENIES

`MCPClient` consults an `ApprovalPolicy.decide(ApprovalRequest) -> bool` **before**
writing a `tools/call` frame. `approvals=None` becomes `DenyAllApprovals()`.
A caller wanting autonomy writes `AllowAllApprovals()`.

*Why:* finding 6. This is the `AI-010` answer, and it is the reason this ADR
exists rather than a smaller one. The deferral for `react-agent-loop` was correct
*for that capability*; it does not carry to a client talking to third-party
processes. A denial is returned as a **model-visible** `ToolFailure` naming the
policy, because the model should know its action was refused.

*Why default-deny:* a library that permits by default has made the consequential
decision on the caller's behalf, and the caller never sees it. `AllowAllApprovals`
is a supported configuration; it is just spelled out.

*Honest limitation:* an always-permit policy is indistinguishable from no policy.
The seam makes the decision possible and visible, not correct.

### D-4. The namespace is client-minted, and the projection excludes what it cannot represent

`ToolId(namespace, remote_name)`, where `namespace` is a constructor argument —
never `serverInfo.name`.

*Why:* the specification requires the client to disambiguate collisions, warns
that `serverInfo.name` is not unique, and states on security grounds that
`clientInfo`/`serverInfo` are self-reported and **SHOULD NOT** be relied on for
security decisions (finding 7; research §6.2, §7.4).

Three exclusion rules, each of which drops a tool **by name with a reason** rather
than failing the listing: an illegal `ToolId.name` (MCP allows uppercase,
`ToolId` does not); an `inputSchema` outside the registry's subset; and a missing
or non-object root schema. The spec's own rule — *"one malformed tool must not
prevent other valid tools from being used"* — is adopted even though its stated
scope is Streamable HTTP.

*Rejected:* silently downcasing an illegal name. It would make two distinct remote
tools collide — a correctness bug purchased with convenience.

### D-5. The error mapping follows `FailureKind`, and the divergence is recorded

`-32601`/unknown tool → `NOT_FOUND` (`model_visible=False`); `-32602` on
`tools/call` → `INVALID_ARGUMENTS` (`model_visible=True`); `isError: true` →
`EXECUTION_FAILED` (`model_visible=True`).

*Why:* finding 5. The registry's axis — *can the model act on this?* — is the one
that survives contact with a loop, and MCP's own tools page partitions its two
mechanisms on the same axis. MCP files *invalid arguments* as a protocol error; we
do not, and the disagreement is recorded rather than smoothed over. On that one
point MCP is being conservative in a direction that costs the model a
self-correction opportunity.

### D-6. A non-protocol stdout line terminates the session

*Why:* finding 8. The spec is silent, so this is a real choice. Terminating fails
loudly and cannot silently desynchronise a stream by dropping messages — the
failure mode the Python SDK's stay-connected behaviour risks.

*Rejected:* logging and continuing (Python SDK) — a dropped message is
indistinguishable from a slow one. *Rejected:* silently discarding (Go) — the same
problem with no diagnostic at all.

### D-7. The timeouts are ours, and they are stated as ours

`request_timeout_seconds = 30.0`, `shutdown_grace_seconds = 2.0`,
`force_kill_seconds = 3.0`.

*Why:* the specification says to *"implement timeouts"* and to wait *"a reasonable
time"* for shutdown and gives **no numbers anywhere read**. Every timeout is a
client choice that must be documented. The Go client's 2 s/3 s escalation is the
structural reference.

### D-8. Sync-only

No `async def`, consistent with ADR-0007 D-3 and ADR-0008 D-3. The Go client shows
a blocking API with an explicit cancellation handle is a complete design, not a
compromise, and nothing in the protocol requires async.

### D-9. No automatic restart

A server death raises `MCPServerDiedError` carrying the `stderr` tail.

*Why:* the spec says the client *SHOULD* restart, and in the modern era a restart
is cheap because the protocol is stateless. But the legacy era **has** sessions
(finding 1), so a restart silently loses in-flight state, and a restart policy is
a caller decision. We surface the death; the caller decides whether to reconnect.
Recorded as a limitation, not hidden.

### D-10. `stderr` is drained into a bounded drop-oldest ring and is never an error signal

64 KiB, drop-oldest, drained by a daemon thread.

*Why:* finding 4. The drain prevents the OS pipe from filling and deadlocking the
child — a failure invisible on a quiet server. The bound prevents a chatty server
from exhausting memory. The prohibition on treating it as an error signal is
normative: the spec says clients *"SHOULD NOT assume `stderr` output indicates
error conditions."* Conflating "the process exited" with "something was written to
`stderr`" produces a diagnostic that misleads.

## Alternatives considered and rejected

| Alternative | Verdict | Reason |
|---|---|---|
| **Adopt the official Python SDK** | REJECT | `anyio` + `pydantic` + `httpx2` + `jsonschema` + `opentelemetry-api`, and async-only. Violates ADR-0003's zero-dependency rule; adopting it needs its own ADR (charter §22). |
| **Adopt the official TypeScript SDK** | REJECT | `cross-spawn` for stdio alone, and the client is not the same runtime as this repository. |
| **Vendor `mcp-go`'s transport** | REJECT | Cross-language. It is a **structural reference**, and `code_reused: false` is recorded. |
| **Modern era only** | REJECT | Finding 2 — reaches nothing deployed. |
| **Dual-era from the start** | DEFER | The only option that reaches both eras, and the most code. The seam makes it additive; ship what is reachable first. |
| **Stay connected on a bad stdout line** | REJECT | D-6 — a dropped message looks like a slow one. |
| **Silently discard a bad stdout line** | REJECT | D-6 — same, with no diagnostic. |
| **`serverInfo.name` as the namespace** | REJECT | The spec explicitly warns it is not unique and not trustworthy (D-4). |
| **Downcase an illegal tool name** | REJECT | Collides distinct tools; the registry is the authority (D-4). |
| **Widen the registry's schema subset** | REJECT | ADR-0006 says the correct response to a too-small subset is an ADR adding a dependency, not a quiet widening. The projection **excludes** the tool instead, by name. |
| **An approval UI** | REJECT | A library has no UI. The *seam* is in scope; the surface is not. |
| **Restart on crash** | DEFER | D-9 — a caller policy, and the legacy era has sessions to lose. |
| **Async / concurrent requests** | DEFER | ADR-0007 D-3, ADR-0008 D-3. |

## Consequences

**Positive.** The repository talks to an external system for the first time, and
charter §16 is demonstrated rather than asserted. The dependency posture is
preserved — standard library only — so the client is usable without an SDK and
testable with no network. The approval seam exists from the first commit, which is
the difference between `AI-010` "deferred" and `AI-010` "unmeetable without
redesign". The transport seam makes the modern era additive.

**Negative / accepted.**

- **Legacy only.** The largest limitation, and it is stated in the spec §2, the
  README, and here.
- **No child sandboxing.** The client constrains *how* the child is spawned, not
  *what* it may do. It is not a security boundary for the server.
- **The projection is lossy.** A tool the registry cannot represent is excluded.
- **Approval is a seam, not a guarantee.** `AllowAllApprovals` permits everything.
- **The timeouts are judgement, not measurement.** 30/2/3 are documented defaults
  with no benchmark behind them.
- **`stderr` can be truncated**, and a server that writes more than 64 KiB loses
  its earliest output.

**Reversal conditions.** D-1 when a modern server is reachable. D-8 when a
capability needs concurrent requests. D-9 when a caller needs supervised restarts.

## Charter compliance

- §8 — decision vocabulary used: **COMPATIBILITY**, with explicit **DEFER** and
  **REJECT** entries above.
- §12 — recorded in the same session as the research and the specification.
- §16 — the reason the capability exists: interoperating with an established
  protocol is an engineering feature, not a compromise.
- §20 — the security posture is stated, including what is **not** protected
  against (§7 of the spec).
- §22 — no runtime dependency added; no trust-boundary change beyond the approval
  seam, which *reduces* what runs without a decision.
- §31 — component independence: `framing`, `jsonrpc`, and `transport` do not
  import `tool_registry`; only `projection` does.

## Licensing

**No code was reused.** All four sources are registered with `code_reused: false`
(charter §11). `mcp-go` was read for structure — the stderr ring and the shutdown
escalation — not copied. Nothing here requires a `NOTICE` update.

## Taxonomy impact

`mcp-client` advances `RESEARCHED → UNDERSTOOD → DESIGNED → DECIDED`.

Artifacts: research record (session 16), specification
(`specifications/mcp-client.md`), this ADR. `decision: COMPATIBILITY`.
`status` becomes `DECIDED`; the implementation follows in
`catalog/protocols/mcp_client/`.