"""Regression tests for the registry-to-provider schema seam.

Found by the end-to-end integration, not by review and not by either
capability's own suite
------------------------------------------------------------
``ToolRegistry`` exposes ``input_schema`` as a ``MappingProxyType`` (immutable,
correct) and ``RegistryDispatcher`` passed it straight through into a request
body. The OpenAI adapter encodes that body with ``json.dumps``, which cannot
serialise a mappingproxy::

    TypeError: Object of type mappingproxy is not JSON serializable
    when serializing dict item 'parameters'

Both capabilities were marked ``TESTED`` and both were -- separately. The defect
lived exactly on the seam between them, which is what the integration exists to
exercise and what neither unit suite crosses.

These tests pin the fix at the layer that owns it: the dispatcher adapter, whose
documented contract is to return tools "in the neutral OpenAI-shaped form that
every provider adapter accepts".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("models", "tools", "agents"):
    sys.path.insert(0, str(_CATALOG / _sub))

from react_agent_loop import RegistryDispatcher  # noqa: E402
from react_agent_loop.adapters import _json_safe  # noqa: E402
from tool_registry import ToolId, ToolRegistry  # noqa: E402


def _registry_with(schema: dict[str, Any]) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        tool_id=ToolId("t", "tool"),
        description="A tool.",
        input_schema=schema,
        callable_=lambda **_: "ok",
    )
    return registry


# --------------------------------------------------------------------------- #
# The reported defect, at the level it was observed
# --------------------------------------------------------------------------- #


def test_advertised_schemas_survive_json_dumps() -> None:
    """The exact failure the integration hit.

    ``json.dumps`` is what a provider adapter does to build a request body, so
    if this raises, no real model call can ever be made.
    """
    registry = _registry_with(
        {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
            "additionalProperties": False,
        }
    )
    schemas = RegistryDispatcher(registry).schemas()

    # Must not raise. This is the regression.
    encoded = json.dumps([dict(s) for s in schemas])

    assert "parameters" in encoded
    assert json.loads(encoded)[0]["name"] == "t:tool"


def test_nested_mappings_are_also_converted() -> None:
    """A shallow ``dict()`` would not have fixed this.

    The mappingproxy the registry exposes is the *outer* schema; its nested
    ``properties`` mapping is where the shallow copy would have left a
    mappingproxy behind, and ``json.dumps`` would still have raised. The fix is
    a deep conversion for exactly this reason.
    """
    registry = _registry_with(
        {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {"deep": {"type": "string"}},
                }
            },
            "required": ["nested"],
        }
    )
    schemas = RegistryDispatcher(registry).schemas()
    json.dumps([dict(s) for s in schemas])  # must not raise

    parameters = schemas[0]["parameters"]
    assert isinstance(parameters, dict)
    assert isinstance(parameters["properties"], dict)
    assert isinstance(parameters["properties"]["nested"], dict)


def test_the_conversion_is_not_destructive() -> None:
    """Converting to plain containers must not change the schema's meaning."""
    schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}},
        "required": ["a"],
        "additionalProperties": False,
    }
    registry = _registry_with(schema)
    advertised = RegistryDispatcher(registry).schemas()[0]["parameters"]

    assert advertised["required"] == ["a"]
    assert advertised["additionalProperties"] is False
    assert advertised["properties"]["a"] == {"type": "integer"}


def test_arrays_of_objects_are_converted() -> None:
    """Schemas are JSON; arrays of mappings occur inside them."""
    registry = _registry_with(
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"x": {"type": "integer"}},
                    },
                }
            },
            "required": ["items"],
        }
    )
    schemas = RegistryDispatcher(registry).schemas()
    json.dumps([dict(s) for s in schemas])  # must not raise


# --------------------------------------------------------------------------- #
# _json_safe itself
# --------------------------------------------------------------------------- #


def test_json_safe_converts_a_mapping_proxy() -> None:
    from types import MappingProxyType

    result = _json_safe(MappingProxyType({"a": 1}))
    assert result == {"a": 1}
    assert type(result) is dict


def test_json_safe_handles_nested_proxies() -> None:
    from types import MappingProxyType

    inner = MappingProxyType({"b": MappingProxyType({"c": 2})})
    result = _json_safe(MappingProxyType({"a": inner}))
    assert result == {"a": {"b": {"c": 2}}}
    json.dumps(result)  # must not raise


def test_json_safe_handles_lists_and_tuples() -> None:
    assert _json_safe([1, 2]) == [1, 2]
    assert _json_safe((1, 2)) == [1, 2]


def test_json_safe_leaves_scalars_alone() -> None:
    """A leaf is returned unchanged, not stringified.

    Coercing an unserialisable leaf here would move the failure somewhere less
    obvious. Leaving it lets the encoder raise at the boundary that owns the
    problem.
    """
    sentinel = object()
    assert _json_safe(sentinel) is sentinel
    assert _json_safe(None) is None
    assert _json_safe(True) is True
    assert _json_safe(3) == 3
    assert _json_safe("s") == "s"


def test_json_safe_coerces_non_string_keys() -> None:
    """JSON object keys must be strings; json.dumps does this itself for
    str/int/float/bool/None, but doing it here keeps the output predictable."""
    assert _json_safe({1: "a"}) == {"1": "a"}


@pytest.mark.parametrize(
    "value",
    [
        {"type": "object", "properties": {}},
        {"a": [{"b": 1}]},
        {},
    ],
)
def test_json_safe_output_is_always_encodable(value: object) -> None:
    json.dumps(_json_safe(value))
