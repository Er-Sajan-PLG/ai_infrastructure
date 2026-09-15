"""The tool type and its registry.

The registry performs **declaration** and **validation**. It does not choose
which tools to advertise to a model, does not speak any provider's wire format,
and does not own telemetry (spec §2). Keeping those separable is the design: a
registry that also selects cannot be tested without a model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .errors import (
    DuplicateToolError,
    FailureKind,
    InvalidSchemaError,
    ToolFailure,
    ToolNotFoundError,
    ToolRegistryError,
)
from .ids import ToolId
from .schema import check_schema, validate_arguments

__all__ = ["Tool", "ToolDescriptor", "ToolRegistry", "ToolResult"]

_EMPTY: Mapping[str, Any] = MappingProxyType({})

# Injected arguments are host-supplied. They are typed loosely on purpose: the
# registry cannot know what a host will inject (a path, a session, a client), and
# guessing a narrower type would reject valid registrations.
_INJECTED_SCHEMA: dict[str, Any] = {
    "description": "Injected by the host. Never model-supplied.",
}


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """A tool's metadata, without the callable.

    ``describe`` returns this rather than the :class:`Tool` itself: descriptors
    cross boundaries that callables should not, and a descriptor is safely
    serialisable.
    """

    id: ToolId
    description: str
    input_schema: Mapping[str, Any]
    injected: frozenset[str]


@dataclass(frozen=True, slots=True)
class Tool:
    """A registered tool.

    Attributes:
        id: Stable structured identity.
        description: What the tool does, for a human or a model.
        input_schema: The **model-facing** view -- injected parameters removed.
        validation_schema: The **full** view, including injected parameters.
        injected: Argument names a model may **never** supply. Values for these
            are taken only from the host-supplied ``trusted`` mapping.
        callable: The implementation. Called with keyword arguments.
    """

    id: ToolId
    description: str
    input_schema: Mapping[str, Any]
    validation_schema: Mapping[str, Any]
    injected: frozenset[str]
    callable: Callable[..., Any] = field(repr=False)

    def descriptor(self) -> ToolDescriptor:
        """Return the callable-free descriptor."""
        return ToolDescriptor(
            id=self.id,
            description=self.description,
            input_schema=self.input_schema,
            injected=self.injected,
        )


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of an invocation: exactly one of a value or a failure."""

    value: Any = None
    failure: ToolFailure | None = None

    @property
    def ok(self) -> bool:
        """Whether the call produced a value."""
        return self.failure is None

    def __post_init__(self) -> None:
        if self.failure is None and self.value is None:
            # A tool legitimately returning None is indistinguishable from a
            # missing value; callers should wrap such tools. Rejected loudly so
            # it cannot silently look like a failure.
            raise ToolRegistryError(
                "ToolResult requires a value or a failure; wrap a None-returning "
                "tool's result in a sentinel rather than returning None"
            )


def _build_tool(
    *,
    tool_id: ToolId,
    description: str,
    input_schema: Mapping[str, Any],
    callable_: Callable[..., Any],
    injected: frozenset[str],
) -> Tool:
    """Validate the schema pair and derive the two views.

    Both schemas are checked against the supported subset, and the injection
    boundary is enforced: an injected name must exist in the validation schema
    and must never appear in the model-facing one (spec §6).
    """
    check_schema(input_schema, where=f"{tool_id}.input_schema")

    unknown = sorted(injected - set(input_schema.get("properties", {})))
    if unknown:
        raise InvalidSchemaError(
            f"{tool_id}: injected argument(s) {', '.join(unknown)} are not declared "
            f"in input_schema.properties"
        )

    model_facing = _without_properties(
        input_schema, injected, where=f"{tool_id}.input_schema"
    )
    check_schema(model_facing, where=f"{tool_id}.input_schema")

    validation_schema = dict(input_schema)
    properties = dict(input_schema.get("properties", {}))
    for name in injected:
        properties[name] = _INJECTED_SCHEMA
    validation_schema["properties"] = properties
    # Injected arguments are required by construction: the host must supply
    # them. Without this, a missing trusted value slides past validation and
    # surfaces later as an opaque TypeError from the callable (found by test).
    validation_schema["required"] = sorted(
        set(validation_schema.get("required", [])) | set(injected)
    )

    return Tool(
        id=tool_id,
        description=description,
        input_schema=MappingProxyType(model_facing),
        validation_schema=MappingProxyType(validation_schema),
        injected=injected,
        callable=callable_,
    )


def _without_properties(
    schema: Mapping[str, Any], remove: frozenset[str], *, where: str
) -> dict[str, Any]:
    """Return a copy of ``schema`` with ``remove`` deleted from properties and required."""
    if not remove:
        return dict(schema)

    result = dict(schema)
    properties = {
        k: v for k, v in schema.get("properties", {}).items() if k not in remove
    }
    result["properties"] = properties

    if "required" in result:
        remaining = [n for n in result["required"] if n not in remove]
        if remaining:
            result["required"] = remaining
        else:
            del result["required"]

    # A required name with no declaration would be an invalid schema.
    unknown = sorted(set(result.get("required", [])) - set(properties))
    if unknown:
        raise InvalidSchemaError(
            f"{where}: removing injected properties left 'required' naming "
            f"undeclared propertie(s) {', '.join(unknown)}"
        )
    return result


class ToolRegistry:
    """A registry of tools, keyed by :class:`ToolId`.

    The registry is pure: no I/O, no network, no imports outside the standard
    library, so its tests need no doubles (spec D-9).
    """

    __slots__ = ("_tools",)

    def __init__(self) -> None:
        self._tools: dict[ToolId, Tool] = {}

    # -- declaration ------------------------------------------------------- #

    def register(
        self,
        *,
        tool_id: ToolId,
        description: str,
        input_schema: Mapping[str, Any],
        callable_: Callable[..., Any],
        injected: frozenset[str] = frozenset(),
    ) -> Tool:
        """Register a tool, returning the built :class:`Tool`.

        Raises:
            InvalidSchemaError: The schema is outside the supported subset, or
                the injection boundary is inconsistent.
            DuplicateToolError: The id is already registered.
        """
        if not description:
            raise ToolRegistryError(f"{tool_id}: description must not be empty")
        if tool_id in self._tools:
            raise DuplicateToolError(
                f"{tool_id} is already registered; ids must be unique (spec D-8)"
            )

        tool = _build_tool(
            tool_id=tool_id,
            description=description,
            input_schema=input_schema,
            callable_=callable_,
            injected=injected,
        )
        self._tools[tool_id] = tool
        return tool

    # -- introspection ----------------------------------------------------- #

    def get(self, tool_id: ToolId) -> Tool | None:
        """Return the tool, or ``None`` when it is not registered."""
        return self._tools.get(tool_id)

    def ids(self) -> tuple[ToolId, ...]:
        """All registered ids, in a deterministic sorted order.

        Stability matters: an unstable enumeration makes tests flaky and diffs
        noisy. MCP later revisions added deterministic ordering for that reason.
        """
        return tuple(sorted(self._tools))

    def describe(self, tool_id: ToolId) -> ToolDescriptor | None:
        """Return the callable-free descriptor, or ``None`` when unregistered."""
        tool = self._tools.get(tool_id)
        return None if tool is None else tool.descriptor()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_id: object) -> bool:
        return tool_id in self._tools

    # -- invocation -------------------------------------------------------- #

    def invoke(
        self,
        tool_id: ToolId,
        arguments: Mapping[str, Any],
        *,
        trusted: Mapping[str, Any] = _EMPTY,
    ) -> ToolResult:
        """Validate arguments and call the tool.

        ``arguments`` is untrusted caller (or model) input. ``trusted`` is
        supplied by the host. They are separate parameters so the boundary is
        visible in the signature (spec §10).

        Raises:
            ToolNotFoundError: No such tool. A caller bug, not a
                :class:`ToolResult`, because a model cannot fix a registry it
                cannot see (spec §7).
        """
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(f"no tool registered as {tool_id}")

        # Non-injected arguments only. Anything a caller supplies for an
        # injected name is discarded and replaced below -- supplying one is not
        # an error, it simply has no effect.
        supplied = {k: v for k, v in arguments.items() if k not in tool.injected}

        problems = validate_arguments(tool.validation_schema, supplied | dict(trusted))
        if problems:
            return ToolResult(
                failure=ToolFailure(
                    kind=FailureKind.INVALID_ARGUMENTS,
                    message="; ".join(str(p) for p in problems),
                    tool_id=str(tool_id),
                )
            )

        # Trusted values win, unconditionally and last.
        final = {**supplied, **trusted}

        try:
            value = tool.callable(**final)
        except Exception as exc:
            # The original exception is retained on the failure so it is never
            # masked (unlike Semantic Kernel's KernelInvokeException, which
            # replaces the cause). The model-visible message carries only the
            # exception *type*, never its text, so internal detail cannot leak
            # into a prompt.
            return ToolResult(
                failure=ToolFailure(
                    kind=FailureKind.EXECUTION_FAILED,
                    message=f"tool raised {type(exc).__name__}",
                    tool_id=str(tool_id),
                    cause=exc,
                )
            )

        return ToolResult(value=value)
