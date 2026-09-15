# Integration: Agent Loop End to End

> **Status: verified.** Three `TESTED` capabilities composed into one working
> system, with tests. The socket is the only double.

| | |
|---|---|
| **Kind** | Integration (charter §17, §31) |
| **Composes** | [`tool-registry`](../../catalog/tools/tool_registry/) (`TESTED`) · [`model-provider-abstraction`](../../catalog/models/model_provider/) (`TESTED`) · [`react-agent-loop`](../../catalog/agents/react_agent_loop/) (`TESTED`) |
| **Reproduce** | `make check` — or `.venv/bin/pytest integrations/ -q` |
| **Tests** | 25 in [`tests/test_end_to_end.py`](tests/test_end_to_end.py) |

## What this proves

The Phase 1 exit criterion asks for *"at least one end-to-end composition:
model + tools + agent loop, demonstrated in `integrations/`"*. This is that
demonstration, and it is a **test**, not a screenshot.

Every layer is the real implementation:

```
  task
    │
    ▼
┌──────────────────────────────┐
│ react_agent_loop.run         │   the real loop, repetition brake,
│                              │   and observation bounding
│  ┌────────────────────────┐  │
│  │ RegistryDispatcher     │──┼──▶ tool_registry.ToolRegistry
│  │ (real adapter)         │  │    real schema validation, real dispatch
│  └────────────────────────┘  │
│  ┌────────────────────────┐  │
│  │ ProviderCaller         │──┼──▶ model_provider.OpenAIProvider
│  │ (real adapter)         │  │    real encoding, real parsing, real errors
│  └────────────────────────┘  │
└──────────────┬───────────────┘
               │ WireRequest
               ▼
      ┌──────────────────┐
      │ ScriptedTransport│   ← the ONLY double: HTTP becomes a queue
      └──────────────────┘
```

No network, no API key, no model. `ScriptedTransport` implements the public
`Transport` protocol from outside the package — which is itself evidence the
seam is real rather than notional. A runtime `isinstance` check asserts the
conformance, so it does not depend on the type-checker's configuration.

## Why it earns its place

**It found a defect that neither capability's own suite could find.**

`tool_registry` was `TESTED`. `model_provider` was `TESTED`. Composing them
raised:

```
TypeError: Object of type mappingproxy is not JSON serializable
when serializing dict item 'parameters'
```

The registry exposes `input_schema` as a `MappingProxyType` — correct, for
immutability — and the dispatcher passed it straight into a request body that
the provider adapter encodes with `json.dumps`. Neither unit suite crosses that
boundary, so neither could see it. `TESTED` for each did not imply `TESTED` for
the pair.

Fixed at the layer that owns it — the dispatcher adapter, whose documented job
is to return tools *"in the neutral OpenAI-shaped form that every provider
adapter accepts"* — and pinned by 12 regression tests in
[`catalog/agents/react_agent_loop/tests/test_adapter_json_safety.py`](../../catalog/agents/react_agent_loop/tests/test_adapter_json_safety.py).

## What the tests actually check

| Area | Representative assertion |
|---|---|
| Composition works | a run reaches `FINAL_ANSWER` with the real loop, registry and provider |
| **Schemas reach the wire** | the encoded request body is JSON and names all three tools |
| Model-facing schema only | `injected` never appears in an advertised tool (ADR-0006 D-3) |
| Full round trip | a tool call is dispatched; its result appears as a `tool` message correlated by `tool_call_id` |
| Transcript order | `system, user, assistant(with tool_calls), tool` |
| Prompt ownership | the caller's system prompt is forwarded, never built (ADR-0008 D-7) |
| Model-visible failure | a raising tool becomes an observation and the loop continues |
| **Sanitisation across the seam** | the exception's *text* never reaches the model; only its type |
| Invalid arguments | caught by the registry, fed back for the model to correct |
| Non-actionable failure | a hallucinated tool name raises, carrying the trace (D-9) |
| Provider errors | a real 429 becomes a classified `ProviderError` and propagates |
| Retryability | a 429 *with* `retry-after` is retryable; the classification survives the trip |
| Usage | summed across the composition |
| Step limit | `max_steps=1` means one model call and no dispatch |
| Repetition | three identical calls stop the run *before* the third dispatch |
| **Injection** | a tool returning action-shaped text produces no forged call |
| Independence | the provider works with no loop; the registry works with no loop *or* provider |
| Hygiene | no test touches the network |

## Limits — stated, not implied

- **The socket is scripted.** These tests prove the *composition* is correct;
  they say nothing about whether a real provider behaves as documented. That is
  the provider adapter's own suite's job, and ultimately an operator's.
- **Non-streaming only.** `ScriptedTransport.stream` raises rather than
  returning an empty iterator, so a future streaming integration cannot
  silently pass by doing nothing.
- **No injection *persuasion* test.** A tool result cannot *forge* an action —
  that is structurally guaranteed and tested. Whether one can *persuade* a model
  is a model-alignment property, and no test here pretends otherwise.
- **One model.** A single scripted OpenAI-shaped provider. Multi-provider
  behaviour is `model-provider-abstraction`'s concern.
- **Not a framework.** This is a demonstration and a test fixture. It is not
  intended to be imported by production code; it exists to keep the composition
  honest.

## Reproducing

```bash
make setup                                   # once per clone
.venv/bin/pytest integrations/ -q            # 25 tests, no network
```

Or run the whole gate, which includes this suite:
`make check`.
