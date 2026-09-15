"""Validation against a documented subset of JSON Schema 2020-12.

Why a subset, and why hand-written
----------------------------------
JSON Schema is large enough that its full implementation is itself an attack
surface: external ``$ref`` invites SSRF, and pathological composition invites CPU
exhaustion. This repository's foundational component carries zero runtime
dependencies (ADR-0003, ADR-0006), so we implement a deliberately small subset --
and, critically, **reject everything else loudly**.

The rejection rule is the security property. A validator that ignores keywords it
does not understand returns ``valid`` for input it never checked. That converts
an unverified boundary into an apparently-verified one, which is worse than
failing outright.

Supported (spec §5)::

    type, properties, required, additionalProperties, items, enum, description

Everything else is rejected at registration, by name.

Bounds
------
Adversarial input is the threat model, not an edge case. Depth is checked
*before* recursing, so ``RecursionError`` is impossible rather than merely
unlikely (spec §8.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import InvalidSchemaError

__all__ = [
    "MAX_ENUM_VALUES",
    "MAX_ERRORS",
    "MAX_PROPERTIES",
    "MAX_SCHEMA_DEPTH",
    "SUPPORTED_KEYWORDS",
    "ValidationProblem",
    "check_schema",
    "validate_arguments",
]

MAX_SCHEMA_DEPTH = 32
"""Maximum nesting depth for schemas and arguments. Deep nesting is a stack-exhaustion vector."""

MAX_PROPERTIES = 256
"""Maximum declared properties on a single object schema."""

MAX_ENUM_VALUES = 1024
"""Maximum permitted ``enum`` size."""

MAX_ERRORS = 50
"""Maximum validation problems returned, so output stays bounded."""

SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "description",
    }
)
"""The complete set of JSON Schema keywords this subset understands."""

_TYPE_NAMES = frozenset(
    {"object", "string", "integer", "number", "boolean", "array", "null"}
)


class ValidationProblem:
    """One reason arguments did not satisfy a schema.

    ``message`` is deliberately safe to show a model: it names a field and an
    expectation, and never echoes internal state (spec §7).
    """

    __slots__ = ("message", "path")

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationProblem(path={self.path!r}, message={self.message!r})"

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


# --------------------------------------------------------------------------- #
# Schema checking (registration time)
# --------------------------------------------------------------------------- #


def check_schema(schema: Any, *, where: str = "schema") -> None:
    """Verify a schema is within the supported subset.

    Args:
        schema: The candidate schema, typically a mapping.
        where: A label used in error messages to locate the problem.

    Raises:
        InvalidSchemaError: If the schema is malformed, uses an unsupported
            keyword, or exceeds a bound. The message always names the offending
            keyword.
    """
    _check_schema(schema, where=where, depth=0)


def _check_schema(schema: Any, *, where: str, depth: int) -> None:
    # Depth is checked before recursing, so RecursionError cannot occur.
    if depth > MAX_SCHEMA_DEPTH:
        raise InvalidSchemaError(
            f"{where}: schema nests deeper than the supported maximum of {MAX_SCHEMA_DEPTH}"
        )

    if not isinstance(schema, dict):
        raise InvalidSchemaError(
            f"{where}: schema must be an object, got {type(schema).__name__}"
        )

    unsupported = sorted(set(schema) - SUPPORTED_KEYWORDS)
    if unsupported:
        # Named loudly, never ignored -- this is the security property.
        raise InvalidSchemaError(
            f"{where}: unsupported keyword(s) {', '.join(unsupported)}. "
            f"Supported: {', '.join(sorted(SUPPORTED_KEYWORDS))}"
        )

    declared_type = schema.get("type")
    if declared_type is not None and (
        not isinstance(declared_type, str) or declared_type not in _TYPE_NAMES
    ):
        raise InvalidSchemaError(
            f"{where}: 'type' must be one of {', '.join(sorted(_TYPE_NAMES))}"
        )

    if "description" in schema and not isinstance(schema["description"], str):
        raise InvalidSchemaError(f"{where}: 'description' must be a string")

    if "enum" in schema:
        _check_enum(schema["enum"], where=where)

    if "properties" in schema:
        _check_properties(schema, where=where, depth=depth)

    if "required" in schema:
        _check_required(schema, where=where)

    if "additionalProperties" in schema and not isinstance(
        schema["additionalProperties"], bool
    ):
        # A schema-valued additionalProperties would require full JSON Schema.
        raise InvalidSchemaError(
            f"{where}: 'additionalProperties' must be true or false in this subset, "
            f"not a schema"
        )

    if "items" in schema:
        _check_schema(schema["items"], where=f"{where}.items", depth=depth + 1)


def _check_enum(values: Any, *, where: str) -> None:
    if not isinstance(values, list):
        raise InvalidSchemaError(f"{where}: 'enum' must be a list")
    if not values:
        raise InvalidSchemaError(f"{where}: 'enum' must not be empty")
    if len(values) > MAX_ENUM_VALUES:
        raise InvalidSchemaError(
            f"{where}: 'enum' has {len(values)} values, exceeding the maximum of {MAX_ENUM_VALUES}"
        )


def _check_properties(schema: dict[str, Any], *, where: str, depth: int) -> None:
    properties = schema["properties"]
    if not isinstance(properties, dict):
        raise InvalidSchemaError(f"{where}: 'properties' must be an object")
    if len(properties) > MAX_PROPERTIES:
        raise InvalidSchemaError(
            f"{where}: {len(properties)} properties exceed the maximum of {MAX_PROPERTIES}"
        )
    for name, subschema in properties.items():
        if not isinstance(name, str):
            raise InvalidSchemaError(f"{where}: property names must be strings")
        _check_schema(subschema, where=f"{where}.properties.{name}", depth=depth + 1)


def _check_required(schema: dict[str, Any], *, where: str) -> None:
    required = schema["required"]
    if not isinstance(required, list) or not all(isinstance(n, str) for n in required):
        raise InvalidSchemaError(f"{where}: 'required' must be a list of strings")
    declared = schema.get("properties", {})
    if not isinstance(declared, dict):
        return
    unknown = sorted(set(required) - set(declared))
    if unknown:
        raise InvalidSchemaError(
            f"{where}: 'required' names undeclared propertie(s) {', '.join(unknown)}"
        )


# --------------------------------------------------------------------------- #
# Argument validation (call time)
# --------------------------------------------------------------------------- #


def validate_arguments(
    schema: Mapping[str, Any], arguments: Any, *, where: str = "arguments"
) -> list[ValidationProblem]:
    """Validate arguments against a schema already accepted by :func:`check_schema`.

    Returns:
        A list of problems, empty when the arguments are acceptable. At most
        :data:`MAX_ERRORS` are returned.
    """
    problems: list[ValidationProblem] = []
    _validate(schema, arguments, path=where, depth=0, problems=problems)
    return problems[:MAX_ERRORS]


def _validate(
    schema: Mapping[str, Any],
    value: Any,
    *,
    path: str,
    depth: int,
    problems: list[ValidationProblem],
) -> None:
    if len(problems) >= MAX_ERRORS:
        return
    # Depth checked before recursing: RecursionError is impossible, not unlikely.
    if depth > MAX_SCHEMA_DEPTH:
        problems.append(
            ValidationProblem(path, f"nests deeper than {MAX_SCHEMA_DEPTH}")
        )
        return

    if "enum" in schema:
        _validate_enum(schema["enum"], value, path=path, problems=problems)

    expected = schema.get("type")
    if expected is not None and not _matches_type(value, expected):
        problems.append(
            ValidationProblem(path, f"expected {expected}, got {_type_name(value)}")
        )
        return

    if expected == "object" or ("properties" in schema and isinstance(value, dict)):
        _validate_object(schema, value, path=path, depth=depth, problems=problems)

    if expected == "array" and isinstance(value, list):
        items = schema.get("items")
        if items is not None:
            for index, item in enumerate(value):
                if len(problems) >= MAX_ERRORS:
                    return
                _validate(
                    items,
                    item,
                    path=f"{path}[{index}]",
                    depth=depth + 1,
                    problems=problems,
                )


def _validate_enum(
    allowed: list[Any], value: Any, *, path: str, problems: list[ValidationProblem]
) -> None:
    if not any(_same_json_value(value, candidate) for candidate in allowed):
        rendered = ", ".join(repr(c) for c in allowed[:8])
        suffix = ", ..." if len(allowed) > 8 else ""
        problems.append(
            ValidationProblem(path, f"expected one of [{rendered}{suffix}]")
        )


def _validate_object(
    schema: Mapping[str, Any],
    value: Any,
    *,
    path: str,
    depth: int,
    problems: list[ValidationProblem],
) -> None:
    if not isinstance(value, dict):
        # Already reported by the type check when 'type' was declared.
        if "type" not in schema:
            problems.append(
                ValidationProblem(path, f"expected object, got {_type_name(value)}")
            )
        return

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return

    required = schema.get("required", [])
    for name in required:
        if name not in value:
            problems.append(
                ValidationProblem(path, f"missing required property '{name}'")
            )

    for name, subschema in properties.items():
        if name in value:
            _validate(
                subschema,
                value[name],
                path=f"{path}.{name}",
                depth=depth + 1,
                problems=problems,
            )

    # Strict by default: models routinely emit undeclared fields, and passing
    # them through to a callable is how a hallucinated parameter becomes a bug.
    if schema.get("additionalProperties") is False:
        unexpected = sorted(set(value) - set(properties))
        for name in unexpected:
            if len(problems) >= MAX_ERRORS:
                return
            problems.append(ValidationProblem(path, f"unexpected property '{name}'"))


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        # bool is an int subclass in Python; JSON treats them as distinct.
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _same_json_value(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool-is-int coercion."""
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(left == right)
    return type(left) is type(right) and left == right
