# Tool Registry & Function Calling Primitive

> **Status: `TESTED`.** Register, describe, validate, and invoke tools with typed schemas. Zero runtime dependencies — standard library only.

| | |
|---|---|
| **Capability** | [`tool-registry`](../../../TAXONOMY.md) (category: tools) |
| **Specification** | [`specifications/tool-registry.md`](../../../specifications/tool-registry.md) |
| **Decision** | [ADR-0006](../../../docs/decisions/0006-tool-registry.md) — `IMPLEMENT` |
| **Research** | [`research/tools/tool-registry.md`](../../../research/tools/tool-registry.md) |
| **Provenance** | [`PROVENANCE.md`](PROVENANCE.md) — inspired-by, **not** derived-from |

## What it is

A uniform, inspectable, validated boundary between **model intent** and
**executable behaviour**. It performs two things:

1. **Declaration** — what tools exist, and what is each one's typed input contract?
2. **Validation** — are the arguments acceptable *before* any side effect occurs?

## Why it exists

Every capability above it — agent loops, MCP clients, provider adapters — needs to
turn a model's "call this tool with these arguments" into a real call, safely and
inspectably.

Research found that **no surveyed project ships a genuine registry** (ADR-0006):
OpenAI has none, LangChain's is a name-keyed dict rebuilt per node, MCP's tool
identity dies with the connection, and Semantic Kernel's is a god object with a
fail-open allowlist default. This fills that gap rather than re-implementing
something that exists.

## How it works

```python
from tool_registry import ToolId, ToolRegistry

registry = ToolRegistry()
registry.register(
    tool_id=ToolId("core", "add"),
    description="Add two integers.",
    input_schema={
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
    callable_=lambda *, a, b: a + b,
)

result = registry.invoke(ToolId("core", "add"), {"a": 2, "b": 3})
assert result.ok and result.value == 5
```

Run the full tour: `python catalog/tools/tool_registry/examples/quickstart.py`

### The five concerns, and which are ours

| Concern | Owner |
|---|---|
| Declaration | **this** |
| Validation | **this** |
| Binding (model call → callable) | a thin adapter over this |
| Selection (which tools to advertise) | the caller / agent loop |
| Telemetry | `execution-trace-recorder` |

Keeping these separate is the design: a registry that also selects cannot be
tested without a model.

## Variants & types

### The failure taxonomy — divided by model-actionability

This is the capability's central rule, and the one thing OpenAI, LangChain, and
MCP independently converged on.

| Failure | `model_visible` | Why |
|---|---|---|
| `NOT_FOUND` | **False** | A hallucinated name cannot be fixed by the model that hallucinated it. Raises `ToolNotFoundError`. |
| `INVALID_ARGUMENTS` | **True** | The model produced the arguments and can correct them. |
| `EXECUTION_FAILED` | **True** | The model should not assume the action succeeded. |

MCP states the rationale normatively: tool errors belong *in* the result
"otherwise the LLM would not be able to see that an error occurred and
self-correct."

Unexpected exceptions from this package's *own* code are **not** converted to
failures — they propagate, so a real defect is never reported to a model as "the
tool failed".

### The injection boundary

Arguments a model may supply and arguments a tool receives are **different sets**,
and the difference is a security boundary:

```python
registry.register(
    tool_id=ToolId("core", "read_file"),
    input_schema={..., "properties": {"path": {...}, "root": {...}}},
    callable_=read_file,
    injected=frozenset({"root"}),   # model can never supply this
)

registry.invoke(read_id, {"path": "x", "root": "/tmp/evil"},  # forged → discarded
                trusted={"root": "/srv/sandbox"})             # trusted → wins
```

LangGraph's source describes the same defence: *"prevents an LLM from forging
hidden InjectedToolArg fields."* Supplying an injected name is **not an error** —
rejecting it would reveal the parameter's existence.

### The supported JSON Schema subset

`type`, `properties`, `required`, `additionalProperties`, `items`, `enum`,
`description`.

**Everything else is rejected at registration, loudly and by name** — including
`$ref`, `oneOf`, `anyOf`, `allOf`, `not`, `patternProperties`, `if`/`then`/`else`,
`pattern`, and `format`.

This is a security property, not a style preference. A validator that ignores
keywords it does not understand reports `valid` for input it never checked,
converting an unverified boundary into an apparently-verified one.

## Landscape

Registered reference projects (all `code_reused: false`, all concepts only):
OpenAI function calling · LangChain/LangGraph · Model Context Protocol ·
Microsoft Semantic Kernel. See [`docs/registry/`](../../../docs/registry/RESEARCH_REGISTRY.md).

## Our implementations

This is the only implementation in this category. See
[`TAXONOMY.md`](../../../TAXONOMY.md) §4.

## When to use / When not to use

**Use it when** you need to expose callables to something untrusted (a model, a
plugin, a config file) and want validation before side effects, a stable
identifier, and a typed outcome.

**Do not use it when** you already control both sides completely and validation
adds nothing — a direct function call is clearer.

**This is not a sandbox.** A registered callable runs with full process privilege.
The registry validates argument *shape*, never *semantics*: a schema can require
`path: string`, not that the path is safe. See §8 of the specification for the
complete list of what it does *not* protect against.

## References

- [`specifications/tool-registry.md`](../../../specifications/tool-registry.md) — the design
- [`docs/decisions/0006-tool-registry.md`](../../../docs/decisions/0006-tool-registry.md) — the decision and rejected alternatives
- [`research/tools/tool-registry.md`](../../../research/tools/tool-registry.md) — the survey