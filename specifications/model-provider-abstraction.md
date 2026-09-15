# Specification: `model-provider-abstraction`

- **Capability:** (category: models)
- **Status:** specified — implementation not started
- **Decision:** [ADR-0007](../docs/decisions/0007-model-provider-abstraction.md) — `IMPLEMENT`
- **Research:** [research/models/model-provider-abstraction.md](../research/models/model-provider-abstraction.md)
- **Depends on:** nothing

> This document describes what will be built. Where the implementation and this
> document disagree, one of them is a bug.

---

## 1. Problem and who needs it

Components must not hard-code one provider's SDK, error shapes, or streaming
model. Everything above this capability — agent loops, RAG pipelines, evaluation
harnesses — needs to make a model call and interpret the result.

The problem is not "call an LLM". It is that **three providers answer the same
question three different ways**, and every consumer that learns one provider's
answer inherits a vendor dependency it did not ask for.

## 2. Scope

**In scope.** A neutral representation of a chat request and response; streaming
as a fallible iterator of typed deltas; usage metadata with optional fields;
a normalised finish reason; a normalised error taxonomy carrying structured
retryability; three provider adapters (OpenAI-compatible, Anthropic, Gemini)
expressed as pure translation between neutral types and wire dictionaries.

**Out of scope (with reasons).**

| Excluded | Why | Type |
|---|---|---|
| HTTP transport | ADR-0007 D-1 — the decision that preserves zero dependencies | SEAM |
| Retry, backoff, circuit breaking | ADR-0007 D-4 — the caller owns policy; we classify, they act | SEAM |
| Async surface | ADR-0007 D-3 — honest absence beats a façade | LATER |
| Caching | Not a provider concern; belongs to a cache layer | LATER |
| Token counting / cost estimation | Requires vendor tokenizers — a dependency | OUT OF SCOPE |
| Embeddings, images, audio | Taxonomy says chat/completion | LATER |
| Completions (non-chat) endpoint | Chat serves every current consumer | LATER |
| Routing, fallback, load balancing | Belongs to a router above this layer | OUT OF SCOPE |
| Prompt templating | Belongs to `prompt-engineering` | OUT OF SCOPE |
| Tool *execution* | That is `tool-registry` | OUT OF SCOPE |

## 3. Design overview

The abstraction is a **shape translator** with a seam at the socket:

```
  caller                 capability                     injected
 ┌────────┐   ChatRequest   ┌──────────────┐  wire dicts  ┌───────────┐
 │ agent  │ ───────────────▶│   adapter    │ ────────────▶│ transport │
 │ loop   │                 │ (per provider)│              │ (caller's)│
 └────────┘◀───────────────└──────────────┘◀─────────────└───────────┘
             ChatResponse         │  parse
                                  ▼
                         neutral types only
```

The adapter's only job is translation. It never opens a socket, never sleeps,
never retries.

## 4. The neutral types

### 4.1 Messages — D-2

```python
Message(role: Role, content: tuple[Block, ...])
```

`Role` is a closed enum: `system`, `user`, `assistant`, `tool`.
`Block` is a closed union: `TextBlock(text)`, `ToolCallBlock(id, name, arguments)`,
`ToolResultBlock(tool_call_id, content)`.

**Why a block list and not a string.** The three providers store completion text
in three structurally different places — a string, typed blocks, and typed parts.
A block list is the only shape that round-trips all three without loss. A plain
string would force every adapter to guess, and would make tool calls and
reasoning content unrepresentable.

### 4.2 Request

```python
ChatRequest(
    model: str,
    messages: Sequence[Message],
    system: str | None = None,          # explicit, because providers differ
    max_output_tokens: int | None = None,
    temperature: float | None = None,
    tools: Sequence[Mapping] = (),      # opaque JSON Schema — D-8
    stream: bool = False,
    extra: Mapping[str, Any] = {},      # provider-specific escape hatch
)
```

`system` is a **separate field**, not a message with `role="system"`. Anthropic's
Messages API has no system role at all; the adapter raises a declared
translation error if a `system`-role message appears.

**Capability honesty.** `temperature` on Anthropic models that reject it is a
declared incompatibility, not a silent drop (D-7).

### 4.3 Response

```python
ChatResponse(
    text: str,                          # flattened from blocks
    blocks: tuple[Block, ...],          # everything, unflattened
    tool_calls: tuple[ToolCallBlock, ...],
    finish_reason: FinishReason,        # closed enum
    raw_finish_reason: str,             # D-6
    usage: Usage | None,
    model: str,
    provider: str,
)
```

### 4.4 Usage — D-5

```python
Usage(
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,           # None for Anthropic unless derivable
    reasoning_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
)
```

Every field optional, because every provider omits something different. An
explicit `is_complete()` reports whether totals could be established — callers
that must account for cost need to know when they cannot (D-5).

### 4.5 Streaming — D-9

```python
StreamDelta = TextDelta(text) | ToolCallDelta(index, id, name, arguments_fragment) \
            | UsageDelta(usage) | FinishDelta(finish_reason, raw)
```

The stream is an `Iterator[StreamDelta]` that **may raise mid-iteration**. This
is a documented property, not an accident: OpenAI raises on an error frame after
200 OK, and Anthropic sends a mid-stream `error` SSE event after 200 OK.

**Tool-call argument reassembly.** OpenAI fragments a JSON *string* across
chunks; Anthropic fragments `input_json_delta.partial_json`. The stream exposes
fragments and provides a documented accumulator, because a partial JSON string is
not parseable and pretending otherwise would produce corrupt arguments.

## 5. The error taxonomy — D-4

```
ProviderError(provider, model, status_code, request_id, retryable, message)
├── RateLimitError        (retryable, with retry_after if the provider sent one)
├── ContextLengthError    (not retryable — the caller must shorten)
├── AuthenticationError   (not retryable)
├── ContentPolicyError    (not retryable)
├── TransportError        (retryable — connection failed)
└── TimeoutError          (retryable)
```

**Rules.**

1. `retryable` is derived from structured signal only — status code and provider-specific rules. **Never** from message text.
2. Anthropic **529** → `RateLimitError`, retryable.
3. Anthropic spend-cap **429 with no `retry-after`** → `RateLimitError`, `retryable=False`. A retryable 429 that can never succeed is a busy-loop generator.
4. Mid-stream errors raise the same types as pre-stream errors. A caller writes one handler.
5. `request_id` is always propagated when the provider supplies it — it is the only way to resolve a vendor-side incident.

## 6. Security and trust boundaries

| Boundary | Rule |
|---|---|
| **Credentials** | The abstraction never reads an API key and never places one in an error. The injected transport attaches auth. |
| **Error leakage** | `ProviderError.message` is safe for logs and prompts; it never contains a raw response body or header dump. Mirrors ADR-0006 D-4. |
| **Prompt/response content** | Treated as untrusted data. Never `eval`'d, never interpolated into a shell. |
| **`extra` passthrough** | Explicitly documented as unvalidated; the caller accepts that the provider may reject it. |
| **Non-goal** | This is **not** a secret manager, a rate limiter, or a sandbox. |

## 7. Design decisions index

| ID | Decision | ADR |
|---|---|---|
| D-1 | No I/O in the abstraction; transport injected | ADR-0007 |
| D-2 | Plain frozen dataclasses, not framework classes | ADR-0007 |
| D-3 | Sync-only; async documented, not faked | ADR-0007 |
| D-4 | Errors classify by caller-actionable retryability | ADR-0007 |
| D-5 | All usage fields optional | ADR-0007 |
| D-6 | Closed finish-reason enum plus raw value | ADR-0007 |
| D-7 | Lossy translation declared, never silent | ADR-0007 |
| D-8 | No dependency on `tool-registry` | ADR-0007 |
| D-9 | Streams are fallible iterators | ADR-0007 |
| D-10 | Target Chat Completions, not Responses | ADR-0007 |

## 8. Public interface (provisional)

```python
class Transport(Protocol):
    def send(self, request: WireRequest) -> WireResponse: ...
    def stream(self, request: WireRequest) -> Iterator[str]: ...

def chat(request: ChatRequest, provider: Provider, transport: Transport) -> ChatResponse: ...
def stream(request: ChatRequest, provider: Provider, transport: Transport) -> Iterator[StreamDelta]: ...

class Provider(Protocol):
    name: str
    def build_request(self, request: ChatRequest) -> WireRequest: ...
    def parse_response(self, response: WireResponse) -> ChatResponse: ...
    def parse_delta(self, event: str, data: str) -> StreamDelta | None: ...
    def classify_error(self, status: int, body: bytes) -> ProviderError: ...
```

**Note on `parse_delta` returning `None`.** A stream carries non-content events
(`ping`, `message_start`). `None` means "no delta", not "end of stream" — the
terminator is the transport's EOF. Encoding the terminator per-provider would
push provider knowledge into the transport, which D-1 forbids.

## 9. Testing strategy (charter §18)

The overwhelming majority of tests need **no network and no model**, because the
transport is injected:

| Class | What it proves |
|---|---|
| Translation | Each adapter maps neutral → wire and back for every supported field |
| Round-trip | A captured real response parses to the neutral type and re-serialises stably |
| Streaming | Canned SSE frames produce the expected delta sequence; `[DONE]`, `message_stop` and bare EOF all terminate identically |
| **Argument reassembly** | Fragmented JSON tool arguments reassemble correctly — including a fragment split mid-token |
| Usage | All three access strategies produce `Usage`; absent usage yields `None`, never a zero that looks like a measurement |
| Errors | Each documented status maps to the right subclass; 529 retryable; spend-cap 429 not retryable; a mid-stream error raises |
| Leakage | A provider error body never appears in a model-facing message |
| Purity | No third-party imports (enforced by an import-scanning test) |

Fixtures are **captured real payloads**, committed as data. This is what makes
three providers' edge cases testable deterministically.

## 10. Benchmark plan

Deferred. The survey found no meaningful latency or throughput claim this
capability can make independently of transport. A benchmark measuring
*translation overhead* per response would be honest; a benchmark comparing
providers would be measuring the wrong thing. Deferred until the benchmark
harness capability exists.

## 11. Definition of done

- [ ] All neutral types implemented as frozen dataclasses, mypy strict clean
- [ ] Three adapters (OpenAI, Anthropic, Gemini) with captured-payload tests
- [ ] Streaming terminates correctly for all three termination styles
- [ ] Tool-argument reassembly proven with mid-token fragments
- [ ] Error taxonomy complete; retryability derived structurally
- [ ] No third-party import (asserted by test)
- [ ] `examples/` program demonstrating a full round-trip against a fake transport
- [ ] README and PROVENANCE
- [ ] Taxonomy → `TESTED`; `react-agent-loop` unblocked

## 12. Open questions for implementation

1. **Wire types.** Should `WireRequest` be a frozen dataclass or a plain dict? A dict is simpler for the transport Protocol; a dataclass is easier to assert on in tests. *Leaning:* frozen dataclass.
2. **`extra` precedence.** If `extra` contains a key the adapter also sets, which wins? *Leaning:* the adapter wins and logs nothing — but this needs a test either way, because ambiguity here is a silent-override bug.
3. **`is_complete()` naming.** A method on `Usage`, or a module function? Cosmetic, but the name should not imply the numbers are authoritative.
4. **Fixture provenance.** Captured real payloads may embed a `request_id` or an organization id. They must be scrubbed before commit, and the scrubbing should be a documented step rather than a manual habit.

These are implementation-level and do not change D-1..D-10.