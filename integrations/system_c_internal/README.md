# Integration: System C — Entirely Internal

> **Status: verified.** Three `TESTED` capabilities composed into one working
> system, with tests. The socket is the only double.

| | |
|---|---|
| **Kind** | Integration (charter §17, §31) |
| **Composes** | [`tool-registry`](../../catalog/tools/tool_registry/) (`TESTED`) · [`model-provider-abstraction`](../../catalog/models/model_provider/) (`TESTED`) · [`react-agent-loop`](../../catalog/agents/react_agent_loop/) (`TESTED`) |
| **Reproduce** | `make check` — or `.venv/bin/pytest integrations/system_c_internal/ -q` |
| **Tests** | 12 in [`tests/test_system_c.py`](tests/test_system_c.py) |

## What this proves

System C is the Phase 4 exit criterion: *"entirely composed from
`ai_infrastructure`."* Every component is a real `TESTED` capability, consumed
through its public interface only. No component is modified, subclassed, or
monkey-patched.

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

## What the tests actually check

| Area | Representative assertion |
|---|---|
| Composition works | a run reaches `FINAL_ANSWER` with the real loop, registry and provider |
| Tool dispatch | a tool call is dispatched; its result appears as a `tool` message |
| Repetition brake | three identical calls stop the run before the third dispatch |
| Provider errors | a real 429 becomes a classified `ProviderError` and propagates |
| Step limit | `max_steps=1` means one model call and no dispatch |
| Direct chat | the provider works with no loop and no registry |
| No network | `ScriptedTransport` never opens a socket |

## Limits — stated, not implied

- **The socket is scripted.** These tests prove the *composition* is correct;
  they say nothing about whether a real provider behaves as documented.
- **Non-streaming only.** `ScriptedTransport.stream` raises rather than
  returning an empty iterator.
- **One model.** A single scripted OpenAI-shaped provider.
- **Not a framework.** This is a demonstration and a test fixture.

## Reproducing

```bash
make setup                                   # once per clone
.venv/bin/pytest integrations/system_c_internal/ -q  # 12 tests, no network
```
