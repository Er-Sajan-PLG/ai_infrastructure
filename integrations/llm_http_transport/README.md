# Integration: LLM HTTP Transport

> **Status: offline-verified.** A stdlib-only transport implementation for `model-provider-abstraction`, with tests. The tests exercise request/response mapping with network calls stubbed; live vendor compatibility has not been verified.

| | |
|---|---|
| **Kind** | Integration (charter §17, §31) |
| **Composes** | [`model-provider-abstraction`](../../catalog/models/model_provider/) (`TESTED`) |
| **Decision** | [ADR-0028](../../docs/decisions/0028-llm-http-transport.md) |
| **Reproduce** | `make check` — or `.venv/bin/pytest integrations/llm_http_transport -q` |
| **Tests** | Offline mapping and boundary tests in [`tests/`](tests/) |

## What this proves

ADR-0007 left a named debt: *"a caller must supply a transport … Mitigated by a documented stdlib example"* — and the example never existed. The only `Transport` implementations were test doubles. This adds the missing stdlib transport implementation and basic live-call path with zero new dependencies. Offline tests validate local mapping and composition only; they do not establish live vendor compatibility.

```
  ChatRequest
      │
      ▼
┌──────────────────────────────┐
│ OpenAI/Anthropic/Gemini      │   the real adapter: real encoding,
│ Provider.build_request       │   real parsing, real error classification
└──────────────┬───────────────┘
               │ WireRequest (headers carry the key; the adapter put it there)
               ▼
┌──────────────────────────────┐
│ UrllibTransport              │   ← the new socket: urllib.request, sync,
│ send() / stream()            │      no retry, no parsing, no logging
└──────────────┬───────────────┘
               │ HTTPS
               ▼
        provider endpoint
```

Every layer above the socket is the real implementation: the composition tests drive the **real `OpenAIProvider`** over this transport with `urlopen` stubbed, proving the adapter-to-transport contract holds for genuine wire bytes — including a 401 classifying as `AuthenticationError` across the seam.

## What the tests actually check

| Area | Representative assertion |
|---|---|
| Seam conformance | `isinstance(UrllibTransport(), Transport)` at runtime |
| Byte fidelity | method, URL, headers (incl. `Authorization`), body forwarded exactly |
| Status is data | a scripted 429 is **returned** as `WireResponse`, not raised |
| Failure classification | `URLError` and read-side `OSError` → `TransportError`; bare and wrapped timeouts → `ProviderTimeoutError` |
| Credential hygiene | a forced failure's message contains neither the key nor `Bearer` |
| Streaming | raw lines yielded with endings intact; mid-stream failure surfaces; reply always closed |
| Streaming limit | non-2xx on stream open raises `TransportError` with the status (stated, not hidden) |
| Key resolution | mapped env var read; missing/blank → `MissingApiKeyError` naming the variable; unknown provider → `ValueError` |

## Limits — stated, not implied

- **The offline suite proves local mapping, not the vendors.** These tests prove the transport carries bytes faithfully and classifies faked failures; they say nothing about whether a provider's live API matches its documented shape. Live vendor verification remains future work.
- **No retry, no pooling.** The caller owns retry policy (ADR-0007 D-4); `urllib` opens a connection per call. Pooling waits for a measured bottleneck, not a hunch.
- **Non-2xx stream opens are `TransportError`, not classified errors.** The streaming return type is lines, so there is no channel for status-as-data. Callers needing classification on that path should open via `send()` first.
- **One timeout for connect and read.** stdlib semantics; a caller needing split timeouts must say so with evidence.
- **Not a framework.** This is a socket and a key lookup. It is not intended to grow retry, caching, or routing; those are callers above this layer.

## Reproducing

```bash
make setup                                                       # once per clone
.venv/bin/pytest integrations/llm_http_transport -q              # offline tests, no network
python integrations/llm_http_transport/examples/quickstart.py    # offline by default; no network call
AI_INFRASTRUCTURE_LIVE_TEST=1 OPENAI_API_KEY='<key>' python integrations/llm_http_transport/examples/quickstart.py  # explicit live opt-in
```

Or run the whole gate, which includes this suite:
`make check`.
