# Model Provider Abstraction

> **Status: `TESTED`.** A vendor-neutral chat interface for OpenAI, Anthropic and Gemini. Zero runtime dependencies — the transport is injected.

| | |
|---|---|
| **Capability** | [`model-provider-abstraction`](../../../TAXONOMY.md) (category: models) |
| **Specification** | [`specifications/model-provider-abstraction.md`](../../../specifications/model-provider-abstraction.md) |
| **Decision** | [ADR-0007](../../../docs/decisions/0007-model-provider-abstraction.md) — `IMPLEMENT` |
| **Research** | [`research/models/model-provider-abstraction.md`](../../../research/models/model-provider-abstraction.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — inspired-by, **not** derived-from |

## What it is

Everything above this capability needs to make a model call: agent loops, RAG
pipelines, evaluation harnesses. This provides **one request shape and one
response shape**, translated to and from three providers whose wire formats
disagree on nearly everything.

It owns the **shape** — messages, responses, usage, finish reasons, errors,
stream deltas. It does **not** own the **socket**.

## Why it exists

A consumer that learns one provider's answer inherits a vendor dependency it did
not ask for. The research found this is not hypothetical:

| | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| System prompt | a `system` **role message** | top-level `system` — **no system role exists** | `systemInstruction` |
|Assistant role| `assistant` | `assistant` | **`model`** |
| Text lives at | `choices[0].message.content` | `content[]` typed blocks | `candidates[0].content.parts[]` |
| Tool args | **JSON string** | parsed object | parsed object |
| Stream ends on | `data: [DONE]` | `message_stop` event | **nothing** |
| Overload signal | 503 | **529** | 503 |
| Total tokens | `total_tokens` | **absent** | `totalTokenCount` |

## How it works

```python
from model_provider import ChatRequest, Message, Role, TextBlock, chat
from model_provider.providers import OpenAIProvider
from model_provider.transport import RecordingTransport   # or your own

response = chat(
    ChatRequest(model="gpt-4o-mini",
                messages=[Message(Role.USER, (TextBlock("hello"),))]),
    provider=OpenAIProvider(),
    transport=my_transport,
    api_key="...",
)
print(response.text, response.usage.total_tokens)
```

Run the full tour: `python catalog/models/model_provider/examples/quickstart.py`

### The transport seam

```
 caller              this capability                injected
┌──────┐  ChatRequest  ┌───────────┐   wire dicts   ┌───────────┐
│ agent│ ─────────────▶│  adapter  │ ─────────────▶ │ transport │
└──────┘◀─────────────└───────────┘◀──────────────└───────────┘
         ChatResponse      │ parse
                           ▼
                    neutral types only
```

An adapter translates. It never opens a socket, never sleeps, never retries.

**Why this matters concretely.** LiteLLM provides the same breadth and pays for
it with 14 base dependencies including `boto3`, rooted in
`class RateLimitError(openai.RateLimitError)` — you cannot recognise an
OpenAI-shaped error without depending on the OpenAI SDK. Injecting the transport
is what makes zero dependencies possible *and* makes three providers' edge cases
testable against canned payloads with no network.

## Variants & types

### `Usage` — every field optional

| Provider | How usage is obtained |
|---|---|
| OpenAI, non-streamed | `usage` object in the response |
| OpenAI, streamed | **opt-in** via `stream_options.include_usage`; arrives on a final chunk with an **empty `choices` array** |
| Anthropic | split: `message_start` (input) + a **cumulative** `message_delta` (output); **no total field at all** |
| Gemini | `usageMetadata`, complete only on the last chunk |

`total_tokens` for Anthropic is **derived** when both parts are known and left
`None` otherwise. A missing count is unknown, never zero — conflating the two
corrupts cost accounting silently.

### Failure taxonomy — by caller-actionable category

| Failure | Retryable | Why |
|---|---|---|
| `RateLimitError` | **depends** | Retryable only when the provider offered a delay |
| `ContextLengthError` | never | The caller must shorten the input |
| `AuthenticationError` | never | Retrying identical credentials cannot succeed |
| `ContentPolicyError` | never | An identical request is refused identically |
| `TransportError` / `ProviderTimeoutError` | yes | The connection can be re-established |
| `ServerError` | yes | Includes Anthropic's non-standard **529** |

**The 429 rule is the one that matters.** Anthropic's spend-cap 429 carries no
`retry-after` and can never succeed; treating it as retryable produces an
unbounded loop. The same status code therefore yields **opposite** verdicts, and
the decision is made from structured signal only — never from message text.

### Streaming — a fallible iterator

The stream is an `Iterator[StreamDelta]` that **may raise mid-iteration**. Both
OpenAI and Anthropic can fail after a `200 OK`. A truncated answer is an
exception, never a shorter reply.

`ToolCallDelta` carries `arguments_fragment` — a **partial JSON string**.
Fragments are not individually parseable, so `ToolCallAccumulator` reassembles
them and raises on malformed JSON rather than inventing `{}`.

## Landscape

Registered reference projects (all `code_reused: false`, concepts only):
LiteLLM · OpenAI Python SDK (client-design reference) · LangChain `BaseChatModel` ·
LlamaIndex `LLM`. See [`docs/registry/`](../../../docs/registry/RESEARCH_REGISTRY.md).

**The finding that shaped this design:** LangChain requires one method and
*derives* async via `run_in_executor`; LlamaIndex declares eight abstract methods
and its async is a façade — `async def achat: return self.chat(...)` — which
looks asynchronous and blocks the event loop. This capability is therefore
**sync-only**, with async documented as a deliberate absence rather than faked.

## Our implementations

This is the only implementation in this category. See
[`TAXONOMY.md`](../../../TAXONOMY.md) §4.

## When to use / When not to use

**Use it when** you call more than one provider, or want provider quirks confined
to an adapter, or need to test model-interaction logic without a network.

**Do not use it when** you use exactly one provider and already hold its SDK —
the translation layer would add indirection and buy nothing.

**Limitations, stated plainly:**

- **No HTTP.** You supply a transport. A stdlib `urllib` transport is a documented exercise, not shipped — shipping one would make retry/timeout/proxy policy this capability's problem.
- **No retries.** It classifies (`retryable`, `retry_after`); you decide.
- **No async.** Use `asyncio.to_thread`. This is the decision most likely to be revisited — [ADR-0007](../../../docs/decisions/0007-model-provider-abstraction.md) D-3 names the condition.
- **Chat only.** Completions, Responses API, embeddings, images and audio are deferred.
- **Reasoning blocks are dropped**, not folded into text. Mapping reasoning into output text would corrupt the transcript; representing it properly needs a type the neutral model does not yet have.
- **Not a credential store, rate limiter, or sandbox.**

## References

- [`specifications/model-provider-abstraction.md`](../../../specifications/model-provider-abstraction.md) — the design
- [`docs/decisions/0007-model-provider-abstraction.md`](../../../docs/decisions/0007-model-provider-abstraction.md) — the decision and rejected alternatives
- [`research/models/model-provider-abstraction.md`](../../../research/models/model-provider-abstraction.md) — the survey