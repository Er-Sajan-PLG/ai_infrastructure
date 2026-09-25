# ADR-0028 — `llm_http_transport`: a stdlib socket for `model-provider-abstraction`, placed in `integrations/`

- **Status:** Accepted
- **Date:** 2026-09-24
- **Capability:** [`model-provider-abstraction`](../../TAXONOMY.md) (category: models) — consumer-side; no catalog entry created
- **Supersedes:** —
- **Superseded by:** —

## Context

ADR-0007 D-1 split shape from socket: the abstraction never performs I/O, and the caller supplies a `Transport`. It left two debts, both named explicitly:

1. *"Own HTTP with `urllib`" — REJECT for now … Requires an ADR.* Making retry/timeout/proxy policy the primitive's problem contradicted D-4 (the caller owns retry policy).
2. *"A caller must supply a transport … Mitigated by a documented stdlib example"* (Consequences) — that example was never written. The only `Transport` implementations in the repository were test doubles (`RecordingTransport`, `ScriptedTransport`). There was no path from `chat()` to a real provider, which blocked every downstream phase that needs a live model.

The decision to evolve (2026-09-24) keeps ADR-0007, ADR-0008 (sync-only), dataclasses-over-Pydantic, and stdlib-only core. Phase 1 therefore provides the missing stdlib transport implementation and basic live-call path **without** adding a runtime dependency, adding an async surface, or putting I/O into the catalog. Remaining transport concerns (retry, pooling, proxy policy, live vendor verification) are deferred to future work.

Two facts found during design shaped the outcome:

- The transport does **not** attach auth headers. `chat()` calls `provider.build_request(request, api_key=...)`, and the adapter already encodes credentials into `WireRequest.headers` (e.g. `providers/openai.py:158`). The transport's only auth duty is forwarding headers as-is without logging them. Environment-variable key resolution is a separate small helper, not transport behavior.
- One transport serves all three providers. It sends to `WireRequest.url`, which each adapter already built from its `DEFAULT_BASE_URL`. No per-endpoint code exists.

## Decision

**ADAPT + IMPLEMENT:** `integrations/llm_http_transport/` — a real, stdlib-only (`urllib.request`) `Transport` implementation plus env-var key resolution — as an **integration**, not a catalog entry, not a dependency.

### Why an integration, not a catalog entry

This is the whole decision. ADR-0007 rejected owning HTTP *as the primitive* because the primitive cannot own retry/timeout/proxy policy. An integration **is the caller** — the exact layer D-4 assigns retry policy to — so the contradiction that forced the rejection does not apply here. Placement consequences:

- `catalog/` keeps zero runtime dependencies and `import-linter` contract 3 (entries never depend on integrations) holds: the edge goes integration → catalog, the allowed direction. The contract's `forbidden_modules` list is extended with the new integration name so the one-way rule stays machine-checked rather than intentional.
- The transport implements every protocol duty from `transport.py:21-54` verbatim: forward `WireRequest.method/url/headers/body` as-is; never raise on non-2xx in `send()` (status is data); `stream()` yields raw response lines with no SSE/`[DONE]` interpretation; no retry; no JSON parsing; stdlib failures map to `TransportError` (`URLError`, connection failures) / `ProviderTimeoutError` (`TimeoutError`, including `URLError` wrapping one) and no raw stdlib exception escapes — `chat()`/`stream()` callers only catch `ProviderError`.
- Sync-only (`urllib.request` blocks), consistent with ADR-0008. Async callers use the documented `asyncio.to_thread` path. No `async def` surface added.
- Env-var names: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. `resolve_api_key()` treats a missing or blank variable as missing and raises `MissingApiKeyError` naming the variable and the export remedy — it never prints a key.

### Scope (built)

| File | Contents |
|---|---|
| `integrations/llm_http_transport/__init__.py` | Package docstring + `__all__`, mirroring `agent_loop_end_to_end/__init__.py` |
| `transport.py` | `UrllibTransport`: `__init__(timeout=…)`; `send()`; `stream()`; structural conformance asserted via the `TYPE_CHECKING _CONFORMS_TO_TRANSPORT` pattern from `scripted_transport.py:90-95` |
| `keys.py` | `PROVIDER_ENV_VARS`, `MissingApiKeyError`, `resolve_api_key(provider) -> str` |
| `README.md` | Integration-pattern README: composes-what, reproduce command, limits table |
| `tests/test_llm_http_transport.py` | Offline mapping and failure tests only, via monkeypatched `urlopen` (no sockets): exact bytes forwarded, non-2xx returned not raised, `URLError`→`TransportError`, timeout→`ProviderTimeoutError`, mid-stream failure surfaces, no credential leakage into messages. These establish local request/response mapping, not live vendor compatibility or endpoint behavior. |
| `examples/quickstart.py` | Offline by default; live call requires `AI_INFRASTRUCTURE_LIVE_TEST=1` and a valid `OPENAI_API_KEY`; otherwise prints the explicit opt-in instruction and exits 0 |

### Explicitly NOT built

- No retry/backoff (caller owns it per D-4; classification via `retryable`/`retry_after` already exists).
- No proxy/TLS policy beyond stdlib defaults and an explicit timeout parameter.
- No new catalog entry, no taxonomy capability, no `PROVENANCE.md` (those belong to catalog entries, not integrations).
- No dependency added: `dependencies=[]` untouched, so no §22 dependency gate was triggered.

## Consequences

**Positive.** The missing stdlib transport implementation and basic live-call path are now provided. Remaining transport concerns (retry, pooling, proxy policy, live vendor verification) are deferred to future work. This does not validate live vendor compatibility: the tests use monkeypatched `urlopen` and verify local mapping and composition only. There are zero new dependencies, zero async surface, and zero catalog changes. pytest `testpaths` already includes `integrations`, so the suite is collected by `make check` with no config change.

**Negative / accepted.**

- A second `Transport` implementation to maintain alongside the test doubles (mitigated: conformance is structurally asserted, and the protocol surface is two methods).
- `urllib.request` ergonomics: no connection pooling, verbose streaming reads. Accepted — pooling is a performance concern for a later phase, and `httpx`/`requests` would detonate the zero-dependency property for one convenience.
- `stream()` on a non-2xx open raises `TransportError` carrying the status code rather than a classified provider error: the streaming return type is lines, so there is no channel for status-as-data, and feeding an error JSON body into the SSE parser would fail silently downstream. Callers needing classification on the streaming path should open via `send()` first. Recorded as a stated limit in the integration README, not a hidden behavior.

**Neutral.**

- Registration follows the existing pattern only: a row in `integrations/README.md`. No `TAXONOMY.md` convention was invented — `agent_loop_end_to_end` is itself absent from `TAXONOMY.md`, and inventing an `integrations/` registry section is deferred until a phase needs `make status` to check it.
- `docs/decisions/README.md` index row for this ADR is a one-line follow-up, deliberately left for the maintainer (new-files-only constraint on this change).

## Alternatives considered

| Alternative | Verdict | Reason |
|---|---|---|
| `httpx` / `requests` as a new dependency | REJECT | Adds a runtime dependency for pooling ergonomics; triggers §22 human-review gate; contradicts the confirmed stdlib-only constraint. Revisit if/when pooling is measured as the bottleneck. |
| `aiohttp` + async transport | REJECT | Adds a dependency AND an async surface, contradicting ADR-0008 D-3. The documented `asyncio.to_thread` path covers async callers. |
| Vendor SDKs (`openai`, `anthropic`, `google-generativeai`) | REJECT | ADR-0007 already rejected this: error classes subclass SDK types, making coupling permanent; loses zero-dependency property at import time. |
| Place the transport in `catalog/` as a 6th entry | REJECT | Catalog entries must stay I/O-free and relocatable; a socket-owning entry breaks the independence contracts and the "no env reads in the abstraction" rule (D-1: *"never reads an environment variable for an API key"*). The env-reading helper cannot live in catalog at all. |
| Place it in `study_pipeline/` | REJECT | Study pipeline is static-only by ADR-0021 (never opens sockets to studied code; its network surface is `git clone` of allow-listed hosts). A live-LLM socket is a different trust domain. |
| `curl` subprocess transport | REJECT | Shell-out for HTTPS adds a process-spawn failure mode, breaks in-process timeout semantics, and complicates the stdlib-only story for zero benefit. |

## Charter references

§8 (decision vocabulary: ADAPT the deferred urllib item, IMPLEMENT the integration); §12 (recorded as ADR before building); §17 + §31 (integration rules — consume via public interfaces only, one-way dependency); §18 (tests run offline — monkeypatched `urlopen`, no sockets, no markers needed); §22 (no runtime dependency added, so no dependency gate; trust-boundary note: this is the repository's first code that contacts vendor APIs with credentials — keys flow env → memory → headers, never to disk/logs).

## Taxonomy impact

None on categories or capabilities (per "Explicitly NOT built"). No `TAXONOMY.md` edits in this change.
