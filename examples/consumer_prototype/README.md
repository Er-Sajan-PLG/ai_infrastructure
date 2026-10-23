# Consumer Prototype (Phase 4 proof)

Demonstrates consuming `ai_infrastructure` capabilities from an **installed**
package, with no `sys.path` manipulation and no imports from `catalog/`
internals. This is the evidence for "a capability can leave the laboratory."

## How to run

```bash
# 1. Build + install the package into a clean environment
python -m build --wheel
pip install --no-deps dist/ai_infrastructure-*.whl

# 2. Run the demo
python examples/consumer_prototype/consumer_demo.py
```

## What it proves

- `import ai_infrastructure` exposes `__version__` and 176 public symbols.
- `tool_registry`, `model_provider`, `react_agent_loop`, `rate_limiting`,
  `execution_trace_recorder` are importable after install.
- No `sys.path` manipulation by the consumer.
- No imports from `catalog/` internals.

## Current limitation (recorded, not hidden)

The installed package relies on `ai_infrastructure/__init__.py` inserting the
`catalog/<category>/` directories into `sys.path` as a side effect of
`import ai_infrastructure`. The consumer must therefore `import ai_infrastructure`
before importing any capability module. This is the gap tracked by ADR-0042
(Public API Namespace Policy): the canonical namespaced API
(`from ai_infrastructure.tools import ToolRegistry`) is the intended end state
and is not implemented yet. Until it is, per-capability imports depend on the
shim.

See `docs/decisions/0042-public-api-namespace-policy.md`.
