# Research: Model Provider Abstraction

- **Capability:** `model-provider-abstraction` (category: models)
- **Status:** `RESEARCHED` → `UNDERSTOOD`
- **Session:** 9
- **Date:** 2026-09-15
- **Decision:** [ADR-0007](../../docs/decisions/0007-model-provider-abstraction.md)

Claims are labelled per charter §6:
**FACT** (verified against a primary source, cited) · **OBSERVATION** (read from
docs/source) · **INFERENCE** (our reasoning) · **DESIGN OPINION** (a choice).

---

## 1. The problem, stated without reference to any implementation

> Components must not hard-code one provider's SDK, error shapes, or streaming model.

Stated that way the problem decomposes into a **shape** concern and a
**transport** concern. Conflating them is what makes this abstraction heavy.

| Concern | Question | Belongs to |
|---|---|---|
| **Message shape** | How is a conversation represented neutrally? | the abstraction |
| **Response shape** | Three providers return three structures — how is one flattened? | the abstraction |
| **Usage shape** | `prompt_tokens` vs `input_tokens` vs `promptTokenCount` | the abstraction |
| **Finish reasons** | `stop`/`length` vs `end_turn`/`max_tokens` vs `STOP`/`MAX_TOKENS` | the abstraction |
| **Error taxonomy** | Which failures are retryable, rate-limited, or fatal? | the abstraction |
| **Wire encoding** | What JSON goes on the socket for provider X? | a provider adapter |
| **HTTP** | Connections, timeouts, TLS, proxies, retries | **the caller** |

**INFERENCE — the load-bearing insight:** the abstraction owns the *shape*, not
the *socket*. Every heavy abstraction in this space took on the socket too, and
that is precisely why consuming them means consuming 14 packages.

**Verified evidence for that claim.** LiteLLM's `pyproject.toml` on `main`
declares 14 base `dependencies`, including `openai`, `httpx`, `tiktoken`,
`tokenizers`, `pydantic`, `jsonschema`, `aiohttp` and **`boto3`** — fetched and
confirmed this session. The root cause is visible in its error classes:
`class RateLimitError(openai.RateLimitError)`. To recognise an OpenAI-shaped
error you must depend on the OpenAI SDK, permanently.

---

## 2. Constraints

| Constraint | Source | Consequence |
|---|---|---|
| **Zero runtime dependencies** | ADR-0003 | No provider SDK. Normalisation hand-written; transport injected. |
| **Model-agnostic** | charter §31 | No vendor SDK type in any public signature. |
| **Component independence** | charter §31 | No agent loop, no registry, no network required. |
| **Python + mypy strict** | charter §13 | Fully annotated; no `extra='allow'` smuggled fields. |
| **Verifiable without network** | charter §18 | Provider quirks testable against canned payloads. |
| **Streaming in scope** | taxonomy | Named explicitly; cannot be deferred silently. |

**DESIGN OPINION — the seam.** Define the abstraction over an injected
transport: the abstraction owns normalisation, the caller supplies I/O. A test
supplies a fake transport with canned bytes, so normalisation is exhaustively
testable with no network, no model and no dependencies. This is also the *only*
way to test three providers' edge cases systematically.

---

## 3. Survey findings

### 3.1 The three providers barely agree on anything

Full table in the survey record; the decisive divergences:

| Dimension | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| System prompt | a `system` **role message** | top-level `system` param — **no system role exists** | top-level `systemInstruction` |
| Text location | `choices[0].message.content` | `content[]` typed blocks | `candidates[0].content.parts[]` |
| Stream end | `data: [DONE]` sentinel | `message_stop` event | **none** — stream just ends |
| Tool args | **JSON string** | parsed object | parsed object |
| Overload signal | 503 | **529 `overloaded_error`** | 503 |
| Total tokens | `total_tokens` | **absent** — must sum | `totalTokenCount` |

**FACT (verified against OpenAI's published OpenAPI spec this session):** tool
call arguments are `type: string`, described as *"A JSON string of the arguments
to pass to the function."* The other two return parsed objects. A neutral layer
must therefore always parse — and on streaming, OpenAI **fragments that JSON
string across chunks**, so it must reassemble before parsing.

### 3.2 Usage in streaming is the sharpest trap

**FACT (verified against OpenAI's OpenAPI spec this session):** usage is absent
from streamed responses unless the caller sets
`stream_options: {"include_usage": true}`, and then it "shows the token usage
statistics" on "an additional chunk ... before the `data: [DONE]` message" —
whose `choices` array is **empty**.

**FACT (verified against the Anthropic SDK source this session):** usage is split
across two event types — `message_start` carries `input_tokens`, and
`message_delta.usage.output_tokens` is **cumulative**. There is no
`total_tokens` field at all. The SDK source also warns the counts are
billing-oriented and "will not match one-to-one" with response content, and
exposes cache dimensions (`cache_creation_input_tokens`,
`cache_read_input_tokens`) that OpenAI models differently.

So the same fact — "how many tokens did that cost?" — requires **three different
access strategies**, and on OpenAI it may simply be unavailable.

**INFERENCE:** a neutral streaming API that promises usage in every chunk would
be lying. Usage must be optional, and the absence must be expressible.

### 3.3 Interface burden predicts integration pain

The survey's clearest signal: LangChain requires **one** method (`_generate`) and
*derives* the rest — including async, FACT-verified as
`run_in_executor(None, self._generate, ...)`. LlamaIndex declares **all eight**
abstract, and its async methods are a façade:
`async def achat(...): return self.chat(...)` — which *looks* asynchronous and
blocks the event loop.

**DESIGN OPINION:** derive what can be derived; never present a fake async
surface. A sync-only core with documented `asyncio.to_thread` guidance is
honest and sufficient for a foundational primitive.

### 3.4 Retries live at two different layers

The survey distinguishes **transport** retries (a 429/503 that may succeed later)
from **validation** retries (a model returned malformed structured output;
re-ask with the error). Conflating them is a design error: each layer should own
the failure it can actually fix. This primitive owns neither — it names the
failure and lets the caller decide.

---

## 4. Synthesis

1. **A shape-owning, transport-injected abstraction is viable with zero
   dependencies.** All three providers are HTTPS+JSON; normalisation is data
   manipulation; SSE framing can be parsed by standard library code over an
   injected line iterator.
2. **Model the union, not the intersection.** A message with an optional system
   slot and a list of typed content blocks round-trips all three. The
   lowest-common-denominator schema is what forces silent lossiness.
3. **Lossy translation must be declared, never silent.** LiteLLM strips
   JSON-Schema keywords a provider rejects; our `tool-registry` already
   established the opposite principle — reject loudly, by name.
4. **Normalise finish reasons to a small closed enum and keep the raw value.**
   Gemini exposes 18+; they cannot be merged losslessly, and the raw value is
   needed for debugging.
5. **Errors: one root carrying provider, model, and status; a few
   caller-actionable subclasses.** Not a 2,753-line substring matcher.
6. **Streams are fallible iterators.** OpenAI raises mid-iteration on an error
   frame; a stream must be able to fail after yielding tokens.

---

## 5. Open questions carried to the decision

1. Should the abstraction perform HTTP at all, or require an injected transport?
2. Sync-only, or derived async as well?
3. How much of the request surface is in scope — chat only, or completions too?
4. How are provider-specific features (thinking blocks, cache tokens) represented
   without leaking vendor concepts into the neutral type?
5. Where does retry policy live?
6. Does this depend on `tool-registry` for tool schemas, or stay independent?

All six are resolved in [ADR-0007](../../docs/decisions/0007-model-provider-abstraction.md).

---

## 6. Survey method and limitations

Three parallel surveys against primary sources: provider documentation and
published OpenAPI specs; and raw source at a pinned version/commit for LiteLLM
(1.102.0), langchain-core (1.6.3), LlamaIndex (0.14.24) and the OpenAI Python SDK
(`main`).

**Corrections and caveats recorded rather than smoothed over:**

- A survey characterised LiteLLM's provider detection as an "if/elif cascade".
  **Corrected on verification:** it is 894 lines, but structured as per-provider
  `_get_*_provider` helpers plus `provider_list` table lookups — not a naive
  cascade. The original criticism (hard to follow, string-driven) stands; the
  mechanism description did not.
- A survey initially assumed provider SDKs were eager dependencies.
  **Corrected:** provider SDKs are lazily imported; the *base* dependency list of
  14 packages is confirmed by direct fetch.
- OpenAI's full `finish_reason` enum was **not** re-verified against a primary
  page (search capacity errors), so it is OBSERVATION, not FACT.
- Google's documentation is mid-migration: `ai.google.dev` now points to a newer
  "Interactions API" as the recommended surface. The Gemini column describes the
  `v1beta` GenerateContent path actually targeted. **INFERENCE:** if Google
  deprecates that path, the Gemini adapter is the one most likely to need rework
  — consistent with the finding that a provider adapter, not the neutral core,
  is where churn lands.
- OpenAI now steers integrators to the **Responses API**, whose event model
  differs again. Targeting Chat Completions is a deliberate, reversible choice;
  it is a *provider adapter* decision, which is the point of the seam.