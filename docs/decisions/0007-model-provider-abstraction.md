# ADR-0007 — `model-provider-abstraction`: Own the Shape, Not the Socket

- **Status:** Accepted
- **Date:** 2026-09-15
- **Capability:** [`model-provider-abstraction`](../../TAXONOMY.md) (category: models)
- **Research record:** [`research/models/model-provider-abstraction.md`](../../research/models/model-provider-abstraction.md)
- **Supersedes:** —

## Context

`model-provider-abstraction` is capability 2 of 7. Two other capabilities
(`react-agent-loop`, `basic-rag-pipeline`) depend on it, so it blocks the first
composition. The taxonomy scopes it narrowly: *"a minimal, vendor-neutral
interface for chat/completion calls with streaming, error normalization, and
usage metadata."*

Three providers were surveyed against primary sources, plus four existing
abstractions. The findings that forced this decision:

1. **The three providers barely agree on anything.** System prompts have three mechanisms (OpenAI: a `system` role message; Anthropic: a top-level `system` parameter with *no* system role at all; Gemini: `systemInstruction`). Completion text lives in three different structures. Stream termination differs: OpenAI sends a `data: [DONE]` sentinel, Anthropic sends a `message_stop` event, Gemini sends nothing.

2. **Tool arguments are encoded differently.** FACT, verified against OpenAI's published OpenAPI spec: `arguments` is `type: string`, *"A JSON string of the arguments."* The other two return parsed objects — and OpenAI **fragments the JSON string across stream chunks**.

3. **Usage in streaming requires three different strategies**, and on OpenAI it may be absent entirely (opt-in via `stream_options: {"include_usage": true}`, delivered on a final chunk with an *empty* `choices` array). FACT, verified against the same spec. Anthropic splits it across `message_start` and a cumulative `message_delta`, with **no** `total_tokens` field. FACT, verified against the Anthropic SDK source.

4. **Owning transport is what makes an abstraction heavy.** FACT, verified by fetching LiteLLM's `pyproject.toml`: 14 base dependencies including `openai`, `httpx`, `tiktoken`, `pydantic`, `aiohttp` and **`boto3`**. The root cause is visible in its error classes — `class RateLimitError(openai.RateLimitError)`: to recognise an OpenAI-shaped error you must permanently depend on the OpenAI SDK.

5. **Interface burden predicts integration pain.** LangChain requires one method and *derives* async via `run_in_executor`; LlamaIndex declares eight abstract methods, and its async is a façade (`async def achat: return self.chat(...)`) that looks asynchronous and blocks the event loop.

## Decision

**IMPLEMENT** a standalone, zero-runtime-dependency provider abstraction whose
job is to own *shape* — messages, responses, usage, finish reasons, errors,
stream deltas — while the *socket* belongs to an injected transport.

### D-1. The abstraction does not perform I/O

A `Transport` protocol is injected. It sends a request and yields response lines;
the adapter parses them. The abstraction never opens a socket, never sets a
timeout, never retries, never reads an environment variable for an API key.

*Why:* this is the single decision that preserves zero dependencies (finding 4)
and it makes three providers' edge cases exhaustively testable against canned
bytes with no network (charter §18).

*Acknowledged cost:* a caller must supply a transport to make a real call. We
provide a stdlib `urllib`-based transport as an example, not as a dependency.

### D-2. Messages are plain frozen dataclasses, not framework classes

A neutral `Message` with a role and a list of typed content blocks; an optional
system slot on the request. **Not** Pydantic, **not** vendor types.

*Why:* LangChain and LlamaIndex both own their message classes and both pay with
converters and heavy dependencies. The neutral shape must round-trip all three
providers (research §4.2).

### D-3. Sync-only core; async is documented, not faked

No `async def` surface in this capability.

*Why:* finding 5. LlamaIndex's fake async is the clearest anti-pattern in the
survey — it misleads callers and blocks the event loop. OpenAI's full duplication
is affordable only because a code generator writes it. LangChain's derived-async
is the good pattern but requires owning an executor policy, which is agent-loop
concern, not primitive concern. Documentation names `asyncio.to_thread` as the
supported path. Revisiting this requires a new ADR (see Consequences).

### D-4. Errors: one root, a few caller-actionable subclasses

`ProviderError` carries `provider`, `model`, `status_code`, `request_id`, and a
`retryable` flag. A small set of subclasses names the failures a caller can
*act* on: rate limit, context length exceeded, authentication, content policy,
transport failure, timeout.

*Why:* LiteLLM's mapper is ~2,753 lines largely matching substrings of
`str(exception)`. Our `tool-registry` already established the governing principle:
classify by what the caller can do about it (ADR-0006 D-4).

**Required detail:** `retryable` must be set from structured signal (status plus
provider-specific rules), never from message text. Anthropic's non-standard
**529** must be treated as retryable; its spend-cap 429 (which carries no
`retry-after`) must not.

### D-5. Usage fields are all optional

An `Usage` record with every field optional, including `total_tokens` (absent
from Anthropic; must be summed when both parts are present).

*Why:* finding 3. A streaming API that promises usage in every chunk would be
lying about all three providers.

### D-6. Finish reasons: closed enum plus the raw value

A small closed enum (`stop`, `length`, `tool_use`, `content_filter`, `error`,
`unknown`) alongside the provider's original string.

*Why:* Gemini exposes 18+ values and OpenAI 5; they cannot be merged losslessly.
Discarding the raw value would make provider debugging impossible.

### D-7. Lossy translation is declared, never silent

Where a neutral feature cannot be expressed on a provider, the adapter reports it
rather than dropping it.

*Why:* LiteLLM silently strips JSON-Schema keywords Anthropic rejects. Our
`tool-registry` rejects unsupported schema keywords **loudly and by name**
(ADR-0006 D-2). Quiet permissiveness converts an unverified boundary into an
apparently-verified one, and the same argument applies here.

### D-8. This capability does not depend on `tool-registry`

Tool schemas appear in this interface only as opaque JSON Schema mappings.

*Why:* charter §31 independence. A provider abstraction that imports the tool
registry cannot be used by anything that does not want one.

### D-9. Streaming deltas are a closed, typed set

A normalized `StreamDelta`: text, tool-call fragment, usage, finish. The stream
is a **fallible iterator** — it can raise mid-iteration.

*Why:* OpenAI raises `APIError` *mid-iteration* on an error frame; a stream that
can only fail before the first chunk would silently truncate output. Conversely
Anthropic delivers mid-stream errors as an SSE `error` event after a 200,
bypassing HTTP error handling entirely — both must surface the same way.

### D-10. Targeting Chat Completions, not the Responses API

The OpenAI adapter targets Chat Completions. OpenAI now steers integrators toward
the Responses API, whose event model differs again.

*Why:* this is a *provider-adapter* decision, which is the entire point of the
seam. The neutral core is unaffected; adding a Responses adapter later is
additive and needs no change to D-1..D-9.

## Alternatives considered and rejected

| Alternative | Verdict | Reason |
|---|---|---|
| **Adopt LiteLLM as the abstraction** | REJECT | 14 base dependencies including `boto3`; errors subclass the OpenAI SDK, so the coupling is permanent; violates ADR-0003's zero-dependency rule and charter §31 independence. |
| **Adopt LangChain's `BaseChatModel`** | REJECT | Owns message types, pulls in `langsmith`/`tenacity`, and does ~eleven jobs on one object. Not separable from the framework. |
| **Vendor SDKs behind a thin protocol** | REJECT | Still ships the SDK; the "zero dependency" property is lost the moment any adapter is importable. |
| **Own HTTP with `urllib`** | REJECT for now | Feasible (SEAM), but makes retry/timeout/proxy/TLS policy the primitive's problem, contradicting D-4's premise that the caller owns retry policy. Requires an ADR. |
| **Async as a duplicated surface** | REJECT | Only affordable with a code generator. Hand-maintained duplication drifts. |
| **Async derived via executor (LangChain's approach)** | DEFER | The correct pattern, but the executor policy belongs to the agent loop. Revisit when `react-agent-loop` needs it. |
| **Pydantic message models** | REJECT | Adds a runtime dependency; our `tool-registry` already validates schemas by hand, and consistency matters. |
| **Completions (non-chat) endpoint** | DEFER | The taxonomy says "chat/completion". Chat is what all three survey targets and every downstream capability actually use. Adding it later is additive. |
| **`stream_options`-style provider-specific passthrough** | ADAPT | A single explicit `extra` mapping for provider-specific parameters, so the neutral surface stays honest while escape hatches remain possible. |

## Consequences

**Positive.** Zero runtime dependencies preserved. The neutral core is testable
against all three providers' quirks with no network. Provider churn is confined
to adapters — which the survey identifies as exactly where it belongs. Adapters
can be added without touching the core.

**Negative / accepted.**

- **A caller must supply a transport.** Mitigated by a documented stdlib example.
- **No async surface.** Callers needing concurrency use `asyncio.to_thread`. This is honest but is a real ergonomic cost, and it is the most likely decision to be revisited.
- **No retry policy.** The abstraction classifies (`retryable`) but does not act. A caller must implement backoff. `retry_after` is exposed when a provider supplies it.
- **Streaming and non-streaming are separate code paths.** The survey found no library that unifies them cleanly; we do not pretend to.
- **Chat only.** Completions, Responses, and embeddings are deferred.

**Reversal conditions.** D-3 (async) should be revisited when `react-agent-loop`
demonstrates a concrete need — that is the earliest point at which the executor
policy question can be answered with evidence instead of speculation. D-10
(Responses API) should be revisited if OpenAI deprecates Chat Completions.

## Charter compliance

- §8 — decision vocabulary used: **IMPLEMENT**, with explicit **DEFER** and **REJECT** entries above.
- §12 — recorded as an ADR in the same session as the research.
- §22 — no runtime dependency added, so no dependency gate is triggered. Had D-1 been resolved the other way (`urllib` transport), this would have required human review.
- §31 — component independence preserved: no dependency on `tool-registry`, no vendor SDK, no import-time I/O.