"""Tool Registry & Function Calling Primitive.

A uniform, inspectable, validated boundary between model intent and executable
behaviour. Performs **declaration** and **validation**; it does not select tools
for a model, speak any provider's wire format, or own telemetry.

Zero runtime dependencies -- standard library only.

    >>> from tool_registry import ToolId, ToolRegistry
    >>> registry = ToolRegistry()
    >>> _ = registry.register(
    ...     tool_id=ToolId("core", "add"),
    ...     description="Add two integers.",
    ...     input_schema={
    ...         "type": "object",
    ...         "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    ...         "required": ["a", "b"],
    ...         "additionalProperties": False,
    ...     },
    ...     callable_=lambda *, a, b: a + b,
    ... )
    >>> registry.invoke(ToolId("core", "add"), {"a": 2, "b": 3}).value
    5

See ``specifications/tool-registry.md`` for the design and
``docs/decisions/0006-tool-registry.md`` for the decision.
"""

from __future__ import annotations

from .errors import (
    DuplicateToolError,
    FailureKind,
    InvalidSchemaError,
    ToolFailure,
    ToolNotFoundError,
    ToolRegistryError,
)
from .ids import ToolId
from .registry import Tool, ToolDescriptor, ToolRegistry, ToolResult

__all__ = [
    "DuplicateToolError",
    "FailureKind",
    "InvalidSchemaError",
    "Tool",
    "ToolDescriptor",
    "ToolFailure",
    "ToolId",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolResult",
]
