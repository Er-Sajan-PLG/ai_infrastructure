# Research: `mcp-client`

**Capability:** [`mcp-client`](../../TAXONOMY.md) (category: mcp)
**Status:** `RESEARCHED`
**Session:** 16
**Date:** 2026-09-16
**Depends on:** `tool-registry` (TESTED)
**Decision:** pending — see §10. **The era fork in §2 is the decision this record surfaces.**

---

## 1. The problem, stated precisely

The taxonomy entry is narrow and deliberately so: *"Connect to an MCP server over stdio, list
tools, call tools, surface results into the local tool registry."* The stated intent is a
**thin working client** over a **comprehensive never-finished one** (§24.4), and the stated
justification is charter §16: MCP is an established protocol, so interoperating with it is an
engineering feature rather than a compromise.

This is the first capability in the repository whose *reason to exist is another system's
protocol*. Every capability so far defined its own boundary. This one has a boundary it does
not control, and that changes what "researched" has to establish: not just what the protocol
does, but **how stable it is, and what it costs to be wrong about it.**

## 2. THE HEADLINE: the protocol has forked into two eras, and the handshake is gone

This is the finding that shapes every other decision below, and it **contradicts the premise
the survey was launched with.**

### 2.1 FACT: the current revision is `2026-07-28`, not `2025-06-18`

`https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/README.md`
names `schema/2026-07-28/schema.ts` as the current schema. That file exports:

```ts
export const LATEST_PROTOCOL_VERSION = "2026-07-28";
export const JSONRPC_VERSION = "2.0";
```

The `schema/` directory listing
(`https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/contents/schema`)
contains **six** entries: `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`,
`2026-07-28`, and `draft`. Five dated revisions in roughly twenty months.

**Relevant to how this research was commissioned:** the task prompt for the specification
survey asserted the current revision was `2025-06-18` and described an `initialize`-based
lifecycle. That was wrong, and had it not been checked against the repository listing, the
entire record would have documented a protocol two revisions stale. This is the same failure
class as the OTel "this page has moved" trap (session 14): **the thing that was true when the
question was written is not evidence that it is true when the question is asked.**

### 2.2 FACT: `2026-07-28` removed the handshake and made the protocol stateless

From `docs/specification/2026-07-28/changelog.mdx`, quoting the major-changes list verbatim:

> Make MCP stateless: remove the `initialize`/`notifications/initialized` handshake. Every
> request now carries its protocol version and client capabilities in `_meta`
> (`io.modelcontextprotocol/protocolVersion`, `io.modelcontextprotocol/clientCapabilities`).

> Remove protocol-level sessions and the `Mcp-Session-Id` header from the Streamable HTTP
> transport.

> Remove `ping`, `logging/setLevel`, and `notifications/roots/list_changed`.

> Add `server/discover`: servers MUST implement this RPC to advertise their supported protocol
> versions, capabilities, and identity.

> All results now carry a required `resultType` field: `"complete"` for ordinary results and
> `"input_required"` for multi round-trip request interim results.

The `versioning` page states the model outright:

> There is no negotiation handshake. Every request carries its protocol version, and the server
> accepts or rejects each request independently.

### 2.3 FACT: the two eras have names, and the spec defines a compatibility matrix

Verbatim from `docs/specification/2026-07-28/basic/versioning.mdx`:

> **Modern**: protocol versions that convey version, identity, and capabilities as per-request
> metadata (revision `2026-07-28` and later).

> **Legacy**: protocol versions that establish a session with an `initialize` handshake
> (`2025-11-25` and earlier).

> **Dual-era**: an implementation that supports both modern and legacy versions.

And the matrix has a row that matters enormously for a thin client:

> | Client | Server | Outcome |
> |---|---|---|
> | Modern | Legacy | **Fails.** The server may reject the request with an implementation-defined
> error, stay silent, or even process an era-ambiguous method under legacy semantics. On stdio,
> clients **SHOULD** send `server/discover` first to fail deterministically… |

**INFERENCE.** A modern-only client cannot talk to a legacy server. A legacy-only client cannot
talk to a modern server *at all* — legacy clients "have no fall-forward mechanism". So this is
not a stylistic choice about which version to prefer: **it determines which servers the client
can connect to**, and it is the ADR-level decision this record exists to surface (§10 Q1).

### 2.3.1 FACT: what `server/discover` actually returns, and what every request must carry

`DiscoverResult` is `{ supportedVersions: string[]; capabilities: ServerCapabilities;
instructions?: string }`. So one call answers the three questions a client has about an unknown
server — which versions, what it offers, and any human-readable guidance — which is why the
spec can make it mandatory for servers and still let clients skip it.

The per-request metadata table from `basic/index.mdx`, verbatim:

| Field | Type | Required |
|---|---|---|
| `io.modelcontextprotocol/protocolVersion` | string | **Yes** |
| `io.modelcontextprotocol/clientInfo` | Implementation | No |
| `io.modelcontextprotocol/clientCapabilities` | ClientCapabilities | **Yes** |
| `io.modelcontextprotocol/logLevel` | LoggingLevel | No |

> A request missing any required field is malformed; the server **MUST** reject it with JSON-RPC
> error code `-32602` (Invalid params).

> A server **MUST NOT** rely on capabilities the client has not declared. If processing a request
> requires a capability the client did not include in `io.modelcontextprotocol/clientCapabilities`,
> the server **MUST** return a [`MissingRequiredClientCapabilityError`] (`-32021`) whose
> `data.requiredCapabilities` lists the missing capabilities.

**INFERENCE.** Two consequences for a thin client. First, `clientCapabilities` is *required on
every request*, not once at connect — so a client that declares `{}` and then relies on a
capability is out of spec, and the failure arrives as `-32021` naming what it forgot. Second,
`-32602` for a malformed request is the *same* code MCP uses for invalid tool arguments (§5.1),
so a client that maps codes blindly cannot distinguish "my request was malformed" from "your
arguments were bad" — it must read the message, which is exactly the kind of thing that should
be decided in the ADR rather than discovered at runtime.

### 2.4 OBSERVATION: the spec now has a deprecation policy, and this is new

The changelog records adopting a *"feature lifecycle and deprecation policy defining the
Active, Deprecated, and Removed feature states, a minimum twelve-month deprecation window"*,
with a registry of deprecated features. Roots, Sampling, and Logging are already Deprecated
under it.

This matters for the decision because it means the *next* breaking change is at least
scheduled rather than arbitrary — but it also means the deprecation clock is already running on
three features, and a client built today should not adopt them (§7.3).

## 3. The transport: stdio, and the framing rule is exactly as load-bearing as expected

### 3.1 FACT: newline-delimited, with an explicit prohibition on embedded newlines

From `docs/specification/2026-07-28/basic/transports/stdio.mdx`, verbatim:

> Messages are delimited by newlines, and **MUST NOT** contain embedded newlines.

> The server **MUST NOT** write anything to its `stdout` that is not a valid MCP message.

> The client **MUST NOT** write anything to the server's `stdin` that is not a valid MCP
> message.

**This is the single most important sentence in the transport spec, and it is a prohibition
rather than an encoding rule.** JSON permits embedded newlines in strings (as escaped `\n`, but
also as literal newlines when not escaped). Because a message is one *line*, a JSON encoder that
pretty-prints, or that emits a literal newline inside a string, corrupts the stream. A
conforming client must serialise compactly and treat a received newline as an unconditional
message boundary.

**INFERENCE.** This makes `json.dumps` with default separators dangerous by default: Python's
default `separators=(', ', ': ')` is fine, but `indent=` or a `default` callback returning a
string containing a literal newline is not. The implementation must specify compact separators
*and* guarantee the encoded line is newline-free, ideally by asserting it rather than assuming.

### 3.1.1 FACT: the framing rule is IDENTICAL in the legacy era, verbatim

Independently confirmed against `docs/specification/2025-06-18/basic/transports.mdx`:

> - Messages are delimited by newlines, and **MUST NOT** contain embedded newlines.
> - The server **MUST NOT** write anything to its `stdout` that is not a valid MCP message.
> - The client **MUST NOT** write anything to the server's `stdin` that is not a valid MCP
>   message.

**OBSERVATION.** The framing rule is the *only* part of the transport that did not change across
the era fork. The 2026-07-28 text adds directionality rules (a server must not write JSON-RPC
*requests* to stdout; a client must not write *responses*) and generalises the framing off stdio,
but the three normative lines above are byte-identical. This is what makes the framing module
the safe place to start: it is the one component whose correctness does not depend on the era
decision (§10 Q1).

### 3.1.2 FACT: the spec does NOT say what a client does with non-protocol stdout

The 2026-07-28 tooling was asked specifically, and the answer is a genuine gap rather than a
gap in reading — **both** stdio transport pages were fetched in full:

> The server **MUST NOT** write anything to its `stdout` that is not a valid MCP message.

That is a prohibition on the *server*. There is **no client-side rule** — no detection, no
resynchronisation, no connection-teardown obligation. Every surveyed implementation therefore
had to choose for itself (§12): the Python SDK logs the parse failure and *continues*; the Go
client silently discards unparseable lines; the TypeScript client closes the transport. Three
implementations, three different behaviours, none of them contradicting the spec.

**INFERENCE.** This is a decision we must make and document, not a decision we can look up. The
divergence among the three implementations is the useful part: it shows the choice is a real
one with real consequences (a resync strategy can silently drop messages; a teardown strategy
can turn one bad byte into a lost session).

### 3.2 FACT: `stderr` is explicitly *not* an error channel

> The server **MAY** write UTF-8 strings to `stderr` for any logging purposes including
> informational, debug, and error messages.

> The client **MAY** capture, forward, or ignore the server's `stderr` output and **SHOULD NOT**
> assume `stderr` output indicates error conditions.

**INFERENCE.** This is a design instruction, not a courtesy. The obvious implementation —
capture stderr and surface it when the process dies — produces a *misleading* diagnostic,
because a server that logs to stderr normally will look like it was failing. The client must
distinguish "the process exited" from "something was written to stderr", and must not conflate
them.

### 3.3 FACT: the framing is not stdio-specific and the spec says to reuse it

> Custom transports that run over a reliable bidirectional byte stream (e.g., Unix domain
> sockets or TCP) **SHOULD** reuse the [stdio framing] rather than defining a new one: the stdio
> binding is just newline-delimited JSON-RPC over a byte stream, and only its process-lifecycle
> rules are specific to standard streams.

**INFERENCE.** The capability's stated scope is "stdio transport", but the spec has just told us
that the *framing* is transport-independent and the *process lifecycle* is the only
stdio-specific part. That is a clean seam: a framing module and a process-lifecycle module,
with the stdio transport being their composition. This is worth designing for even though Phase
1 only ships stdio, because it costs nothing at design time and the taxonomy entry already
anticipates more transports later.

### 3.4 FACT: shutdown is a four-step protocol, and EOF is the portable signal

> The client **SHOULD** initiate shutdown by:
> 1. Closing the input stream to the child process (the server).
> 2. Waiting for the server to exit.
> 3. If the server does not exit within a reasonable time, forcibly terminating the process
>    using the mechanism appropriate for the operating system.

> Servers **SHOULD** exit promptly when their standard input is closed or reads return
> end-of-file. This is the primary graceful-shutdown signal and the only portable one.

> If the server process exits unexpectedly, the client **SHOULD** restart it. Because the
> protocol is stateless, any in-flight requests are simply lost and the client can retry them
> against the fresh process.

**OBSERVATION.** "Because the protocol is stateless, any in-flight requests are simply lost" is
a *simplification that is only available in the modern era*. In the legacy era, in-flight
requests live in an initialized session; losing the process loses the session. The spec is
describing modern behavior here.

**UNKNOWN:** what "a reasonable time" is, in any unit. The spec does not say, and neither
does it say whether restart is a *client* obligation for the stdio transport or merely a
recommendation. **This is a timeout the client must choose and document, not one it can look
up.**

## 4. `tools/list` and `tools/call`

### 4.1 FACT: a tool descriptor

From `schema/2026-07-28/schema.ts`, the `Tool` interface (abridged to the decision-relevant
fields; full doc comments read at source):

```ts
export interface Tool extends BaseMetadata, Icons {
  description?: string;
  inputSchema: { $schema?: string; type: "object"; [key: string]: unknown };
  outputSchema?: { $schema?: string; [key: string]: unknown };
  annotations?: ToolAnnotations;
  _meta?: MetaObject;
}
```

with, verbatim on `inputSchema`:

> Tool arguments are always JSON objects, so `type: "object"` is required at the root. Beyond
> that, any JSON Schema 2020-12 keyword may appear alongside `type` — including composition
> keywords (`oneOf`, `anyOf`, `allOf`, `not`), conditional keywords (`if`/`then`/`else`),
> reference keywords (`$ref`, `$defs`, `$anchor`), and any other standard validation or
> annotation keywords.

> Defaults to JSON Schema 2020-12 when no explicit `$schema` is provided.

and on `outputSchema`:

> An optional JSON Schema object defining the structure of the tool's output returned in the
> `structuredContent` field of a `CallToolResult`. This can be any valid JSON Schema 2020-12.

**INFERENCE — and this is a direct hit on `tool-registry`.** The changelog records this as a
loosening: *"Loosen `inputSchema` and `outputSchema` to allow any JSON Schema 2020-12 keywords
… Add `$ref` resolution requirements and composition-keyword resource bounds."* Our registry
(ADR-0006 D-2) supports a **documented JSON Schema subset** and **rejects unknown keywords
loudly**. An MCP tool may therefore arrive carrying `oneOf`, `$ref`, `if`/`then`/`else`, or
`$defs` — all of which our validator will reject.

**This is the same shape of finding as the `mappingproxy` defect (session 13):** two components,
each correct in isolation, whose boundary is undefined. The difference is that this boundary is
*external*, so we cannot fix it by relaxing our own rule — we must decide how an external schema
that exceeds our subset is handled, and that decision belongs in the ADR.

### 4.1.1 FACT: the legacy schema type was structurally narrower, and the dialect was unpinned

Independently confirmed from `schema/2025-06-18/schema.ts`:

```ts
inputSchema: { type: "object"; properties?: { [key: string]: object }; required?: string[]; };
```

versus the 2026-07-28 form, which has an explicit index signature
(`{ $schema?: string; type: "object"; [key: string]: unknown }`).

**OBSERVATION.** So the schema-wide loosening is not merely editorial: in the legacy era the
*type* itself admitted only `properties` and `required`, and no draft was named anywhere read.
2026-07-28 pins the dialect explicitly. From `docs/specification/2026-07-28/basic/index.mdx`:

> **Default dialect**: When a schema does not include a `$schema` field, it defaults to
> JSON Schema 2020-12

> Clients and servers **MUST** support JSON Schema 2020-12 for schemas without an explicit
> `$schema` field

**INFERENCE.** "MUST support 2020-12" is a hard obligation on us, and our registry's documented
subset (ADR-0006 D-2) is a *subset of* that dialect. The mismatch in §4.1 is therefore not
optional to resolve: the spec names 2020-12 as the floor, and we do not implement the floor.

### 4.1.2 FACT: the spec constrains `$ref` and composition keywords for security

From `docs/specification/2026-07-28/basic/index.mdx`, verbatim:

> JSON Schema 2020-12 permits `$ref` to point at an absolute URI. Implementations **MUST NOT**
> automatically dereference `$ref` values that resolve to a network URI.

> Schemas that fail to validate due to an unresolved external `$ref` **SHOULD** be rejected
> rather than silently treated as permissive.

> Implementations **SHOULD** apply reasonable bounds, such as a maximum schema depth, a cap on
> the total number of subschemas, or a per-validation time budget, to prevent a malicious schema
> from acting as a Denial-of-Service vector against the validator.

**INFERENCE.** Two of these three are things our registry *already does for the right reason*.
`tool-registry` rejects unknown keywords loudly rather than ignoring them, and it was tested
against a 2000-deep schema that must fail cleanly rather than exhaust the stack (session 8).
So the spec's `$ref` and DoS guidance independently validates two choices ADR-0006 already made
— which is worth recording, because it means the subset is not merely a limitation, it is a
security posture the standard agrees with. The one genuinely new obligation is **never
dereference a network `$ref`**: if we ever widen the subset to accept `$ref`, that rule must
hold, and it should be stated in the ADR now rather than discovered later.

### 4.2 FACT: the tool *result*

```ts
export interface CallToolResult extends Result {
  content: ContentBlock[];
  structuredContent?: unknown;
  isError?: boolean;
}
```

`ContentBlock` is a union of `TextContent | ImageContent | AudioContent | ResourceLink |
EmbeddedResource`. `structuredContent` is *"any JSON value (object, array, string, number,
boolean, or null) that conforms to the tool's outputSchema if one is defined."*

### 4.3 FACT: `resultType` is now required on every result

```ts
export interface Result {
  _meta?: ResultMetaObject;
  resultType: ResultType;
  [key: string]: unknown;
}
```

> Servers implementing this protocol version MUST include this field. For backward
> compatibility, when a client receives a result from a server implementing an earlier protocol
> version (which does not include `resultType`), the client MUST treat the absent field as
> `"complete"`.

**INFERENCE.** A *required* field that may be *absent* is a compatibility rule disguised as a
schema rule. A modern client must therefore not model `resultType` as non-optional at the
boundary — it is required to *send*, and required to *tolerate the absence of*. The two
requirements point in opposite directions and both are normative.

### 4.4 FACT: a third outcome exists — `input_required`

`CallToolResultResponse` is typed `CallToolResult | InputRequiredResult`, and the tools page
shows `tools/call` returning `resultType: "input_required"` with an `inputRequests` map, then
being *retried* with `inputResponses` and an opaque `requestState`. The page is explicit:

> Note that the JSON-RPC `id` **MUST** be different between the initial request and the retry.

**INFERENCE.** This replaces the legacy server-initiated-request mechanism (`roots/list`,
`sampling/createMessage`, `elicitation/create`) with a *pull* model: the server no longer asks
the client for anything mid-call, it returns "I need input" and the client decides whether to
retry. For a thin Phase 1 client this is probably out of scope — but it must be *recognised and
refused*, not mistaken for a malformed result, or the client will surface a confusing error for
a legitimate server response.

## 5. The error model has two mechanisms, and the spec explains *why*

### 5.1 FACT: protocol errors vs tool-execution errors

The `CallToolResult.isError` doc comment states the distinction with its reason:

> Whether the tool call ended in an error. If not set, this is assumed to be false (the call was
> successful).
>
> Any errors that originate from the tool SHOULD be reported inside the result object, with
> `isError` set to true, _not_ as an MCP protocol-level error response. **Otherwise, the LLM
> would not be able to see that an error occurred and self-correct.**
>
> However, any errors in _finding_ the tool, an error indicating that the server does not
> support tool calls, or any other exceptional conditions, should be reported as an MCP error
> response.

And the tools page partitions them by *who can fix it*:

> **Protocol Errors** indicate issues with the request structure itself that **models are less
> likely to be able to fix**: Unknown tool · Malformed requests · Server errors

> **Tool Execution Errors** contain actionable feedback that language models **can use to
> self-correct and retry**: API failures · Input validation errors · Business logic errors

> Clients **SHOULD** provide tool execution errors to language models to enable self-correction.

Independently confirmed against the **legacy** revision
(`docs/specification/2025-06-18/server/tools.mdx`), which partitions them the same way:

> Tools use two error reporting mechanisms:
> 1. **Protocol Errors**: Standard JSON-RPC errors for issues like: Unknown tools / Invalid
>    arguments / Server errors
> 2. **Tool Execution Errors**: Reported in tool results with `isError: true`: API failures /
>    Invalid input data / Business logic errors

**OBSERVATION.** The two-mechanism split is stable across the era fork — the 2026-07-28 text
sharpens the *rationale* ("models are less likely to be able to fix" vs "actionable feedback
that language models can use to self-correct") but the partition itself is unchanged. Note also
that the legacy revision files **invalid arguments** under Protocol Errors, which is exactly the
asymmetry §5.2 flags: MCP is consistent across both eras that bad arguments are a *protocol*
error, while our `INVALID_ARGUMENTS` is model-visible.

### 5.2 OBSERVATION: this is the *same* axis `tool-registry` already chose, reached independently

ADR-0006 D-4 partitioned `ToolFailure` by **model-actionability**: `NOT_FOUND` never reaches a
model (`model_visible=False`); `INVALID_ARGUMENTS` and `EXECUTION_FAILED` do. MCP partitions its
two mechanisms on exactly that axis, and for exactly that reason.

**INFERENCE.** This is the strongest convergence in the whole survey, and it means the mapping
between the two error taxonomies is *structural rather than coincidental*:

| MCP mechanism | Our `FailureKind` | `model_visible` |
|---|---|---|
| JSON-RPC protocol error, unknown tool | `NOT_FOUND` | `False` |
| JSON-RPC protocol error, malformed request | `INVALID_ARGUMENTS` | `True` |
| result with `isError: true` | `EXECUTION_FAILED` | `True` |

The one place the two are *not* obviously aligned is "malformed request": MCP files it as a
protocol error (model less likely to fix) while we file `INVALID_ARGUMENTS` as model-visible.
**That asymmetry is a real question for the ADR, not a detail** — see §10 Q4.

### 5.3 FACT: MCP now partitions the JSON-RPC reserved range, and one code was renumbered

From `docs/specification/2026-07-28/basic/index.mdx`, "Error Codes", verbatim:

> JSON-RPC 2.0 reserves the range `-32000` to `-32099` for implementation-defined server errors.
> MCP partitions this range as follows:
> - **`-32000` to `-32019` — legacy.** Codes in this sub-range were allocated by implementations
>   before this policy was introduced. New codes **MUST NOT** be allocated in this sub-range …
> - **`-32020` to `-32099` — reserved for the MCP specification.** … Implementations **MUST NOT**
>   emit any code from this sub-range that is not defined by this specification

Allocated: `-32020` HeaderMismatch · `-32021` MissingRequiredClientCapability · `-32022`
UnsupportedProtocolVersion. And, verbatim:

> Implementations of this protocol version **MUST NOT** emit these codes: `-32002` — resource not
> found (2025-11-25 and earlier; replaced by `-32602`). Clients **SHOULD** still accept `-32002`
> from servers implementing earlier versions. `-32042` — URL elicitation required (2025-11-25
> only).

**OBSERVATION, and it is a trap worth recording.** The standard JSON-RPC codes are identical in
both eras (`-32700` PARSE_ERROR, `-32600` INVALID_REQUEST, `-32601` METHOD_NOT_FOUND, `-32602`
INVALID_PARAMS, `-32603` INTERNAL_ERROR). What changed is the MCP-specific layer: a code that
*was* meaningful (`-32002`) must no longer be emitted, while a client **SHOULD** still accept it
from older servers. A client must therefore hold **both** mappings simultaneously — emit `-32602`
or nothing, accept `-32002` on the way in — which is the kind of asymmetry that gets dropped when
someone reads only one revision. Separately, `-32002` is declared in *prose* in the legacy docs
but **not** as a constant in `schema/2025-06-18/schema.ts`; a client that only reads the schema
would not know it exists.

## 6. The tool-name collision problem — and it lands directly on our `ToolId`

### 6.1 FACT: uniqueness is scoped to *one server*, and collisions are expected

Verbatim from the tools page:

> Tool name uniqueness is scoped to a single server. Clients or proxies that aggregate tools
> from multiple servers **MAY** encounter naming collisions (for example, two servers each
> exposing a `search` tool) and **SHOULD** implement a disambiguation strategy such as
> prefixing tool names with a server identifier.

> The server `name` (from `serverInfo`) is not guaranteed to be unique across servers and
> **SHOULD NOT** be relied upon for disambiguation.

Naming constraints, verbatim: *"Tool names SHOULD be between 1 and 128 characters"*, and
*"The following SHOULD be the only allowed characters: uppercase and lowercase ASCII letters
(A-Z, a-z), digits (0-9), underscore, hyphen, and dot."*

### 6.2 OBSERVATION: this is precisely the problem `ToolId(namespace, name)` was built for

ADR-0006 D-1 chose a frozen `ToolId(namespace, name)` dataclass, with the recorded reasoning
that *"identity must outlive a connection; MCP's dies on restart, SK's parses a flattened
name."* Session 6 established that MCP's tool identity is connection-scoped.

**That finding is now confirmed and sharpened by the current spec, which is *more* explicit than
the version studied in session 6.** MCP says the client must mint the disambiguation, and warns
that the obvious key (server name) is not guaranteed unique.

**INFERENCE.** Our `namespace` is the right shape, and the spec independently arrives at
"prefix with a server identifier" — but it also tells us **not to trust `serverInfo.name` as
that identifier.** The namespace must be a *client-chosen, client-stable* identifier (a local
config key, a path, a hash of the launch command), not a value the server reports about itself.
This mirrors ADR-0008 D-6's posture: never let the model-facing side own a security-relevant
name.

## 7. Security: the spec is more prescriptive than expected, and one item is already a known gap

### 7.1 FACT: a human in the loop is specified — and we currently do not have one

The tools page carries a `<Warning>` block, verbatim:

> For trust & safety and security, there **SHOULD** always be a human in the loop with the
> ability to deny tool invocations.
>
> Applications **SHOULD**:
> - Provide UI that makes clear which tools are being exposed to the AI model
> - Insert clear visual indicators when tools are invoked
> - Present confirmation prompts to the user for operations, to ensure a human is in the loop

and the security-considerations section:

> Clients **SHOULD**: Prompt for user confirmation on sensitive operations · Show tool inputs to
> the user before calling the server, to avoid malicious or accidental data exfiltration ·
> Validate tool results before passing to LLM · Implement timeouts for tool calls · Log tool
> usage for audit purposes

**The connection to our own audit is direct.** The 2026-09-16 audit's `AI-010` ("Consequential
actions require human confirmation") was adjudicated **DEFER**, on the grounds that
`react-agent-loop`'s README declares approval gates a non-goal. That deferral was correct *for
that capability*. But `mcp-client` is the capability that **dispatches to processes we did not
write**, and the protocol we are implementing *asks for* a human in the loop. A declared
non-goal in the loop does not carry over to the client that talks to a third-party server.

**INFERENCE.** This does not obligate Phase 1 to ship an approval UI — this is a library, and
the spec says "applications SHOULD". But it does mean the *seam* must exist: the client should
route a call through a decision point that a caller can supply, rather than dispatching
unconditionally. Otherwise the capability quietly contradicts the protocol it implements, and
`AI-010` moves from "deferred" to "unmeetable without redesign".

### 7.2 FACT: tool annotations are untrusted by default

> For trust & safety and security, clients **MUST** consider tool annotations to be untrusted
> unless they come from trusted servers.

**OBSERVATION.** `MUST`, not `SHOULD` — and it is the only `MUST` on the client side of the
tools page. A server's `annotations` (e.g. hints about whether a tool is read-only or
destructive) are *advisory claims by an untrusted party*. This is `AI-001`'s shape again: the
distinction between what data can *say* and what it can *do*.

### 7.3 FACT: `x-mcp-header` is Streamable-HTTP-only, and may be ignored on stdio

The `x-mcp-header` mechanism mirrors tool parameters into HTTP headers, and:

> Clients using other transports (e.g., stdio) **MAY** ignore `x-mcp-header` annotations
> entirely.

**INFERENCE.** For a stdio client this is a no-op, but the *validation* requirement is not
obviously a no-op: the spec says clients using Streamable HTTP **MUST reject** tool definitions
whose `x-mcp-header` values violate constraints, and **MUST exclude** the invalid tool from
`tools/list` rather than failing the whole listing. "One malformed tool must not prevent other
valid tools from being used" is a robustness principle worth adopting for stdio too, even
though the specific header constraints do not apply.

### 7.4 FACT: four more constraints the current revision adds, all client-side

Verbatim from `docs/specification/2026-07-28/basic/index.mdx` and `server/tools.mdx`:

> JSON Schema 2020-12 permits `$ref` to point at an absolute URI. Implementations **MUST NOT**
> automatically dereference `$ref` values that resolve to a network URI.

> Schemas that fail to validate due to an unresolved external `$ref` **SHOULD** be rejected
> rather than silently treated as permissive.

> Implementations **SHOULD** apply reasonable bounds, such as a maximum schema depth, a cap on
> the total number of subschemas, or a per-validation time budget, to prevent a malicious schema
> from acting as a Denial-of-Service vector against the validator.

> Consumers of icon metadata **MUST** take appropriate security precautions … Clients **MUST**
> reject icon URIs that use unsafe schemes and redirects, such as `javascript:`, `file:`, `ftp:`,
> `ws:`, or local app URI schemes. … Fetch icons without credentials.

> `io.modelcontextprotocol/clientInfo` and `io.modelcontextprotocol/serverInfo` are self-reported
> by the sender and are not verified by the protocol. … Implementations **SHOULD NOT** … rely on
> them for security decisions.

**INFERENCE — and two of these are things `tool-registry` already does for the right reason.**
ADR-0006 D-2 rejects unknown keywords loudly rather than ignoring them, and the registry was
tested against a 2000-deep schema that must fail cleanly rather than exhaust the stack
(session 8). The spec's `$ref` and DoS guidance independently converges on both choices, which
is worth recording because it means the documented subset is not merely a limitation — it is a
security posture the standard agrees with. The genuinely **new** obligations are: never
dereference a network `$ref`; reject an unresolved external `$ref` rather than treating it as
permissive; and never treat `serverInfo.name` as trustworthy. The last one lands directly on
§6.2 — the namespace must be client-minted, and the spec has now said so on security grounds
rather than merely for disambiguation.

## 8. What the specification does NOT settle

Stated as OBSERVATION only where the reading supports it:

1. **Timeouts.** The spec tells clients to *"Implement timeouts for tool calls"* and to wait *"a
   reasonable time"* for a server to exit during shutdown. It gives **no numbers** anywhere
   read. Every timeout is a client choice that must be documented.

   Independently confirmed for the **legacy** era, which is *more* explicit but still gives no
   values (`docs/specification/2025-06-18/basic/index.mdx`): *"Implementations SHOULD establish
   timeouts for all sent requests, to prevent hung connections and resource exhaustion"*, and on
   expiry the sender *"SHOULD issue a [cancellation notification] for that request and stop
   waiting for a response"*, with timeouts *"configurable on a per-request basis"* and a maximum
   enforced *"regardless of progress notifications"*. **OBSERVATION:** no equivalent timeouts
   section was found in the 2026-07-28 pages fetched, so the current revision's timeout guidance
   is **UNVERIFIED** — do not cite the legacy text as if it were current.

   The one *number* that appears anywhere is an SDK choice, not a spec value: the official Python
   SDK sets `DISCOVER_TIMEOUT_SECONDS = 10.0` and leaves `read_timeout_seconds` at `None`
   (§12.6). That is a data point about what a mature client picked, not a requirement.
2. **Process ownership beyond shutdown.** The spec specifies the shutdown *sequence* but not who
   owns restart policy, how many times a crash is retried, or whether a crash is surfaced as an
   error. It says only that the client *SHOULD* restart.
3. **Concurrency and correlation.** Nothing read specifies how many requests may be in flight,
   or that responses must be matched to requests by `id` beyond JSON-RPC's own rule. The
   correlation requirement is inherited from JSON-RPC, not restated.
4. **Process supervision on stdio.** The spec mandates the subprocess model and the shutdown
   sequence, but says nothing about sandboxing the child, environment scrubbing, or whether the
   client should constrain what the server may do. §7.1's human-in-the-loop is the nearest it
   comes, and it is `SHOULD`.
5. **The `_meta` reserved-prefix rule.** `MetaObject` documents that *"Any prefix where the
   second label is `modelcontextprotocol` or `mcp` is reserved for MCP use"*, with reverse-DNS
   recommended. The full validation and rejection rules for a malformed `_meta` key were not
   read in this session.

## 9. Synthesis: what this implies for our design

Nine points, each traceable to evidence above.

1. **The capability's intent survives; its protocol target does not.** "Thin stdio client that
   surfaces tools into the local registry" is still exactly right. What changed is that the
   protocol it speaks has a **two-era fork**, and the client must declare which era it speaks.
   §2.

2. **The era choice is the ADR's central decision, not a detail.** Modern reaches modern
   servers only; legacy reaches legacy only; dual-era costs both paths. §2.3, §10 Q1.

3. **`server/discover` is mandatory for a modern client and is also the probe.** Servers MUST
   implement it; clients MAY call it — but on stdio a client that wants deterministic failure
   against a legacy server *should* probe first, because otherwise the legacy server may process
   an era-ambiguous method like `tools/call` under legacy semantics. §2.3.

4. **Framing is newline-delimited and the prohibition is on *content*, not encoding.** Compact
   serialisation plus an assertion that no emitted line contains a newline. §3.1.

5. **`stderr` is not an error channel, and the client must not treat it as one.** §3.2.

6. **Framing and process lifecycle are separable, and the spec says so.** Design the seam even
   though Phase 1 ships only stdio. §3.3.

7. **The error mapping is structural, with one genuine mismatch.** MCP's two mechanisms and our
   `FailureKind` partition on the same axis for the same reason — except "malformed request",
   which MCP calls a protocol error and we call model-visible. §5.

8. **The namespace must be client-minted.** The spec requires the client to disambiguate and
   explicitly warns that `serverInfo.name` is not a safe key. `ToolId(namespace, name)` is the
   right shape; the *value* of `namespace` must be the client's, not the server's. §6.

9. **The human-in-the-loop seam must exist, even if Phase 1 ships no UI.** This is where the
   capability intersects our own `AI-010` deferral, and the deferral does not carry over to a
   client talking to third-party processes. §7.1.

## 10. Open questions carried to the decision

1. **Which era?** Modern-only, legacy-only, or dual-era. This is the ADR's first decision and
   everything else is downstream of it. Noting that dual-era is the only option that reaches
   the installed base, and also the most code.
2. **How is an `inputSchema` that exceeds our subset handled?** Reject the tool, accept and
   validate loosely, or accept with a declared reduced guarantee. §4.1.
3. **What is the timeout policy?** No number is in the spec. §8.1.
4. **How is MCP's "malformed request = protocol error" reconciled with our model-visible
   `INVALID_ARGUMENTS`?** §5.2.
5. **What is the approval seam?** A callback, a protocol, a policy object — and does Phase 1
   ship it or only reserve it? §7.1.
6. **What does the client do with `resultType: "input_required"`?** Refuse explicitly, or
   support the retry? §4.4.
7. **Is restart-on-crash in Phase 1, and is it bounded?** §3.4, §8.2.
8. **Does `structuredContent` become a `ToolResult` value, and how does it compose with
   `content` blocks?** §4.2.
9. **Is the client sync-only like the rest of the repository?** ADR-0007 D-3 chose sync-only and
   named its own reversal condition. A subprocess client is a place that condition could be
   tested — but nothing in the spec requires async.

## 11. Method and limitations

**Verified directly, by me, from primary source (fetched 2026-09-16):**

- `schema/` directory listing and `schema/2026-07-28/` directory listing (GitHub contents API)
- `README.md` (repository root)
- `schema/2026-07-28/schema.ts` (98,426 bytes; read in part, plus targeted extraction of
  `Tool`, `CallToolResult`, `ListToolsResult`, `ClientCapabilities`, `ServerCapabilities`,
  `Result`, `DiscoverResult`, JSON-RPC and error-code definitions)
- `docs/specification/2026-07-28/changelog.mdx`
- `docs/specification/2026-07-28/basic/versioning.mdx`
- `docs/specification/2026-07-28/basic/transports/index.mdx`
- `docs/specification/2026-07-28/basic/transports/stdio.mdx`
- `docs/specification/2026-07-28/server/tools.mdx`

**Delegated to a background subagent (report pending at time of writing, to be merged):** a
second pass over the specification including the 2025-06-18 legacy revision, and a survey of the
official Python and TypeScript SDK client implementations (§12 placeholder below). Where the two
overlap, the subagent report is corroboration or contradiction, not a substitute.

**Could not verify:**

- **The SDK implementations.** No client implementation was read by me. Every claim about *how
  existing clients are built* — dependencies, subprocess spawning, framing code, timeout
  defaults — is absent from this record rather than guessed. §12.
- **`docs/specification/2026-07-28/basic/transports/streamable-http.mdx`** was not fetched.
  Streamable HTTP is out of scope for a stdio client, so this is deliberate, but it means
  nothing here should be cited about the HTTP transport.
- **The deprecated-features registry** (`/specification/2026-07-28/deprecated`) was not fetched.
  §2.4 rests on the changelog's prose, not on the registry itself.
- **`docs/general/recording-errors.mdx`** — not relevant here; noted only because the OTel
  survey had an analogous gap.
- **The exact `_meta` key validation and rejection rules.** §8.5.

**A method finding worth keeping.** The specification survey was commissioned with a premise
that was two revisions out of date, and the `README.md` plus directory listing contradicted it
within the first two fetches. **A research task carries its commissioner's assumptions, and
those assumptions are exactly as likely to be stale as the code under study.** Checking the
premise is not extra diligence; it is the first step of the research.

---

## 12. Client implementations: three references, and only one survives our dependency rule

Surveyed from primary source: the official Python SDK, the official TypeScript SDK (branch `main`,
now a pnpm monorepo), and `mark3labs/mcp-go` as an independent client.

### 12.1 FACT: the two official SDKs cannot meet our zero-runtime-dependency rule

**Python SDK** (`pyproject.toml`): `anyio`, `httpx2`, `pydantic`, `starlette`,
`python-multipart`, `sse-starlette`, `uvicorn`, `jsonschema`, `pyjwt[crypto]`,
`typing-extensions`, `typing-inspection`, `opentelemetry-api`. The stdio transport alone
needs `anyio` for pipes, streams, and process management.

**TypeScript SDK** (`packages/client/package.json`): `cross-spawn`, `eventsource`,
`eventsource-parser`, `jose`, `pkce-challenge`, `zod`. The stdio module imports
`spawn from 'cross-spawn'` explicitly, and the package's own comment says the stdio entry
is kept separate *"so that bundling ... for browser or Cloudflare Workers targets does not
pull in `node:child_process`, `node:stream`, or `cross-spawn`."*

**OBSERVATION.** Both are dependency-heavy for reasons that are not gratuitous — `anyio`
buys structured cancellation, `zod`/`pydantic` buy schema validation. But it means neither
can be a template for a repository whose `[project].dependencies` is empty, and adopting
either would require an ADR (charter §22).

### 12.2 FACT: the Go client is the reference that fits

`mark3labs/mcp-go`, `client/transport/stdio.go`: imports are stdlib only (`bufio`, `bytes`,
`context`, `encoding/json`, `errors`, `fmt`, `io`, `io/fs`, `log/slog`, `os`, `os/exec`,
`runtime`, `strings`, `sync`, `syscall`, `time`) plus an in-repo package. **Its stdio
transport is genuinely zero-third-party-dependency**, and it is the closest existing design
to what we can build.

Its four decisions worth recording:

1. **Framing:** `c.stdout = bufio.NewReader(stdout)`; `line, err := c.stdout.ReadString('\n')`;
   `line = strings.TrimRight(line, "\r\n")`. Newline boundary, `\r\n` tolerated.
2. **Correlation:** `responses map[string]chan *JSONRPCResponse` under a `sync.RWMutex`, keyed
   by `request.ID.String()`; `SendRequest` selects over `c.done`, `ctx.Done()`, and the
   response channel — so a per-request timeout is the caller's context, not a library default.
3. **`stderr`:** default `io.Discard`, drained continuously into a **64 KiB drop-oldest ring
   buffer**. The doc comment states the reason precisely: *"the transport drains stderr
   continuously so that the OS pipe (about 64KB) can never fill up and block the child
   process, which would deadlock the whole stdio channel."*
4. **Shutdown:** `gracefulShutdownTimeout = 2 * time.Second`, `forceKillTimeout = 3 * time.Second`;
   close stdin → wait 2s → POSIX `SIGTERM` (Windows kills immediately) → wait 3s → `Kill()`.
   Idempotent via `closeOnce`.

**INFERENCE.** Items 3 and 4 are the two most valuable findings in this section, because both
describe failure modes that a naive implementation gets wrong *silently*. An undrained stderr
pipe deadlocks the child, and a child that never exits because nothing escalated past a
polite request leaks a process. Neither is visible in a passing test on a cooperative server.

### 12.3 FACT: the Python SDK's process-group kill is the one behaviour worth copying

`os/posix/utilities.py`: `os.killpg(pgid, signal.SIGTERM)` with `pgid = process.pid`, poll
until dead, then `os.killpg(pgid, signal.SIGKILL)` — enabled by `start_new_session=True` at
spawn time.

**OBSERVATION.** Neither the TypeScript client nor the Go client reaps grandchildren — both
kill only the direct child. The Python docstring names exactly the leak this avoids: `killpg`
*"reaches every descendant atomically, even ones whose parent already exited."*

**INFERENCE.** For an MCP server that is a shell wrapper, a launcher script, or anything that
itself spawns children, killing only the direct child leaks processes. This is worth adopting
regardless of the dependency posture, and it costs one keyword argument at spawn.

### 12.4 FACT: no implementation uses a shell

All three pass an argv array — Python via `anyio.open_process([command, *args], ...)`, Go via
`exec.CommandContext(ctx, c.command, c.args...)`, TypeScript with an explicit `shell: false`.
None interpolates a command string.

**INFERENCE.** This is a security property we should match deliberately rather than
incidentally, and it is worth a test: a config value containing `; rm -rf /` must be passed as
a literal argument, not interpreted.

### 12.5 FACT: the three clients disagree on what to do with bad stdout — and the spec permits all three

| Client | On an unparseable stdout line |
|---|---|
| Python SDK | logs the parse failure, returns it as an *exception value* on the read stream, **stays connected** |
| Go client | silently `continue`s, discarding the line |
| TypeScript client | throws out of `readMessage()` → `onerror` → **closes the transport** |

**OBSERVATION.** This is exactly the gap identified in §3.1.2. The spec prohibits the *server*
from writing non-protocol bytes to stdout and specifies **no client behaviour** for when it
happens. Three implementations, three different answers, none contradicting the standard.

**INFERENCE.** We must choose and document. The Python SDK's choice is the most defensible for
a client that wants to survive a chatty server; the TypeScript choice is the most defensible
for one that wants to fail loudly rather than risk desynchronisation. The choice should be
explicit in the ADR rather than inherited by accident from whichever we imitate.

### 12.6 FACT: dependency-posture summary

| Client | Runtime deps for stdio | Sync or async |
|---|---|---|
| Python SDK | `anyio` (+`pydantic`, `httpx2`, `jsonschema`, …) | **async-only** — every entry point is `async def`, no sync client exists |
| TypeScript SDK | `cross-spawn` | Promise-based |
| Go client | **none** (stdlib only) | blocking call taking a `context.Context` |

**OBSERVATION.** The Python SDK being async-only is directly relevant to ADR-0007 D-3, which
chose sync-only for the model providers and named its own reversal condition. A subprocess
client is the natural place that condition could be tested — but note that the Go client shows
a blocking API with an explicit cancellation handle is a complete design, not a compromise.
Nothing in the protocol requires async.

### 12.7 UNKNOWN: what was not read

- **TypeScript `ReadBuffer` internals** (`packages/core-internal/src/shared/stdio.ts`) — the
  newline-vs-`Content-Length` boundary logic. The 10 MB `maxBufferSize` default is confirmed;
  the framing mechanism is inferred from the spec and the other two clients, **not read**.
- **TypeScript request correlation and error taxonomy** — `protocol.ts` (87 KB) and the errors
  directory were not fetched.
- **TypeScript v1.x stdio** — superseded on `main` by the v2 monorepo; would need a tag.
- **Concrete versions** — the Python SDK's `pyproject.toml` uses `dynamic = ["version"]`
  (uv-dynamic-versioning), so no literal version is readable; the Go module tag was not read.
  Only the TypeScript versions are pinned facts: root `2.0.0-alpha.0`, `packages/client` `2.0.0`.
- **Whether any TypeScript code path uses `shell: true`** — none in the stdio file read, but
  not all client files were read.
