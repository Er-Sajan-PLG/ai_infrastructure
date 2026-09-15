"""Tests for the tool registry.

Failure paths are the majority, by design (spec §11). Validation is a security
boundary, so adversarial input is a first-class case class rather than an edge
case.

No model, no network, no filesystem, no doubles -- a direct benefit of the
boundary the capability chose.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The entry lives at catalog/tools/tool_registry/, so the importable parent is
# catalog/tools/ -- tests/ -> tool_registry/ -> tools/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tool_registry import (
    DuplicateToolError,
    FailureKind,
    InvalidSchemaError,
    ToolId,
    ToolNotFoundError,
    ToolRegistry,
    ToolRegistryError,
)
from tool_registry.schema import (
    MAX_ENUM_VALUES,
    MAX_ERRORS,
    MAX_PROPERTIES,
    MAX_SCHEMA_DEPTH,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _schema(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    }
    base.update(overrides)
    return base


def _registry_with_add() -> tuple[ToolRegistry, ToolId]:
    registry = ToolRegistry()
    tool_id = ToolId("core", "add")
    registry.register(
        tool_id=tool_id,
        description="Add two integers.",
        input_schema=_schema(),
        callable_=lambda *, a, b: a + b,
    )
    return registry, tool_id


# --------------------------------------------------------------------------- #
# Identity (spec §4)
# --------------------------------------------------------------------------- #


def test_tool_id_is_hashable_and_usable_as_key() -> None:
    assert {ToolId("core", "x"): 1}[ToolId("core", "x")] == 1


def test_namespaces_disambiguate_same_name() -> None:
    """The whole point of namespacing: same name, different owners."""
    assert ToolId("core", "get") != ToolId("mcp.github", "get")


def test_tool_id_order_is_deterministic() -> None:
    ids = [ToolId("b", "x"), ToolId("a", "y")]
    assert sorted(ids) == [ToolId("a", "y"), ToolId("b", "x")]


def test_str_form_is_display_only_but_stable() -> None:
    assert str(ToolId("core", "get_weather")) == "core:get_weather"


@pytest.mark.parametrize("bad", ["", "Upper", "has space", "-leading", ".dot"])
def test_invalid_name_characters_are_rejected(bad: str) -> None:
    with pytest.raises(ToolRegistryError):
        ToolId("core", bad)


def test_empty_namespace_is_rejected() -> None:
    with pytest.raises(ToolRegistryError):
        ToolId("", "name")


# --------------------------------------------------------------------------- #
# Registration failures (spec §5)
# --------------------------------------------------------------------------- #


def test_duplicate_id_is_rejected_not_overwritten() -> None:
    """Last-write-wins would hide a bug behind a plausible result (D-8)."""
    registry, tool_id = _registry_with_add()
    with pytest.raises(DuplicateToolError):
        registry.register(
            tool_id=tool_id,
            description="A different add.",
            input_schema=_schema(),
            callable_=lambda *, a, b: a - b,
        )


def test_unknown_keyword_is_rejected_by_name() -> None:
    """Silent permissiveness is the bug; the message must name the keyword."""
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError) as excinfo:
        registry.register(
            tool_id=ToolId("core", "x"),
            description="Uses an unsupported keyword.",
            input_schema={"type": "object", "wat": True},
            callable_=lambda **_: 1,
        )
    assert "wat" in str(excinfo.value)


@pytest.mark.parametrize(
    "keyword",
    [
        "$ref",
        "oneOf",
        "anyOf",
        "allOf",
        "not",
        "patternProperties",
        "if",
        "pattern",
        "format",
    ],
)
def test_each_unsupported_keyword_is_rejected(keyword: str) -> None:
    """Every keyword outside the subset must fail loudly, naming itself."""
    registry = ToolRegistry()
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"x": {"type": "string", keyword: "anything"}},
    }
    with pytest.raises(InvalidSchemaError) as excinfo:
        registry.register(
            tool_id=ToolId("core", "x"),
            description="Unsupported.",
            input_schema=schema,
            callable_=lambda **_: 1,
        )
    assert keyword in str(excinfo.value)


def test_non_object_schema_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema=["not", "a", "mapping"],  # type: ignore[arg-type]
            callable_=lambda **_: 1,
        )


def test_invalid_type_name_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema={"type": "object", "properties": {"a": {"type": "integerr"}}},
            callable_=lambda **_: 1,
        )


def test_empty_enum_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema={"type": "object", "properties": {"a": {"enum": []}}},
            callable_=lambda **_: 1,
        )


def test_required_naming_undeclared_property_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema={"type": "object", "properties": {}, "required": ["ghost"]},
            callable_=lambda **_: 1,
        )


def test_schema_valued_additional_properties_is_rejected() -> None:
    """A schema-valued additionalProperties would need full JSON Schema."""
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema={"type": "object", "additionalProperties": {"type": "string"}},
            callable_=lambda **_: 1,
        )


def test_empty_description_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolRegistryError):
        registry.register(
            tool_id=ToolId("core", "x"),
            description="",
            input_schema={"type": "object"},
            callable_=lambda **_: 1,
        )


# --------------------------------------------------------------------------- #
# Bounds: adversarial input (spec §8.1)
# --------------------------------------------------------------------------- #


def test_deeply_nested_schema_is_rejected_without_recursion_error() -> None:
    """Depth is checked before recursing, so RecursionError is impossible."""
    depth = MAX_SCHEMA_DEPTH + 5
    schema: dict[str, object] = {"type": "integer"}
    for _ in range(depth):
        schema = {"type": "object", "properties": {"n": schema}}

    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError) as excinfo:
        registry.register(
            tool_id=ToolId("core", "deep"),
            description="Too deep.",
            input_schema=schema,
            callable_=lambda **_: 1,
        )
    assert "deeper" in str(excinfo.value)


def test_extremely_deep_schema_does_not_crash() -> None:
    """A pathological schema fails cleanly rather than exhausting the stack."""
    schema: dict[str, object] = {"type": "integer"}
    for _ in range(2000):
        schema = {"type": "object", "properties": {"n": schema}}

    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "pathological"),
            description="Hostile.",
            input_schema=schema,
            callable_=lambda **_: 1,
        )


def test_too_many_properties_is_rejected() -> None:
    props = {f"p{i}": {"type": "integer"} for i in range(MAX_PROPERTIES + 1)}
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "wide"),
            description="Too wide.",
            input_schema={"type": "object", "properties": props},
            callable_=lambda **_: 1,
        )


def test_oversized_enum_is_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError):
        registry.register(
            tool_id=ToolId("core", "enumy"),
            description="Too many values.",
            input_schema={
                "type": "object",
                "properties": {"a": {"enum": list(range(MAX_ENUM_VALUES + 1))}},
            },
            callable_=lambda **_: 1,
        )


# --------------------------------------------------------------------------- #
# Argument validation (spec §7)
# --------------------------------------------------------------------------- #


def test_valid_arguments_are_invoked() -> None:
    registry, tool_id = _registry_with_add()
    result = registry.invoke(tool_id, {"a": 2, "b": 3})
    assert result.ok
    assert result.value == 5


@pytest.mark.parametrize(
    ("arguments", "expect_fragment"),
    [
        ({"a": 1}, "missing required property 'b'"),
        ({"a": 1, "b": "two"}, "expected integer"),
        ({"a": 1, "b": 2, "c": 3}, "unexpected property 'c'"),
        ({"a": True, "b": 2}, "expected integer"),
    ],
)
def test_invalid_arguments_produce_a_model_visible_failure(
    arguments: dict[str, object], expect_fragment: str
) -> None:
    registry, tool_id = _registry_with_add()
    result = registry.invoke(tool_id, arguments)
    assert not result.ok
    assert result.failure is not None
    assert result.failure.kind is FailureKind.INVALID_ARGUMENTS
    assert result.failure.model_visible
    assert expect_fragment in result.failure.message


def test_bool_is_not_accepted_as_integer() -> None:
    """Python's bool-is-int coercion must not leak into JSON typing."""
    registry, tool_id = _registry_with_add()
    result = registry.invoke(tool_id, {"a": True, "b": 1})
    assert not result.ok
    assert result.failure is not None
    assert "expected integer" in result.failure.message


def test_enum_mismatch_is_reported() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("core", "pick")
    registry.register(
        tool_id=tool_id,
        description="Pick a colour.",
        input_schema={
            "type": "object",
            "properties": {"c": {"type": "string", "enum": ["red", "green"]}},
            "required": ["c"],
        },
        callable_=lambda *, c: c,
    )
    result = registry.invoke(tool_id, {"c": "blue"})
    assert not result.ok
    assert result.failure is not None
    assert "red" in result.failure.message


def test_enum_accepts_a_declared_value() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("core", "pick")
    registry.register(
        tool_id=tool_id,
        description="Pick a colour.",
        input_schema={
            "type": "object",
            "properties": {"c": {"type": "string", "enum": ["red", "green"]}},
            "required": ["c"],
        },
        callable_=lambda *, c: c,
    )
    result = registry.invoke(tool_id, {"c": "red"})
    assert result.ok
    assert result.value == "red"


def test_nested_object_and_array_validation() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("core", "nested")
    registry.register(
        tool_id=tool_id,
        description="Nested.",
        input_schema={
            "type": "object",
            "properties": {
                "inner": {
                    "type": "object",
                    "properties": {"n": {"type": "integer"}},
                    "required": ["n"],
                    "additionalProperties": False,
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["inner"],
        },
        callable_=lambda **_: "ok",
    )
    assert registry.invoke(tool_id, {"inner": {"n": 1}}).ok

    bad = registry.invoke(tool_id, {"inner": {"n": "x"}})
    assert not bad.ok
    assert bad.failure is not None
    assert "inner.n" in bad.failure.message

    bad2 = registry.invoke(tool_id, {"inner": {"n": 1}, "tags": [1, 2]})
    assert not bad2.ok
    assert bad2.failure is not None
    assert "tags" in bad2.failure.message


def test_additional_properties_defaults_to_permissive_only_when_absent() -> None:
    """Explicit false rejects; absence does not (strictness is opt-in per schema)."""
    registry = ToolRegistry()
    loose = ToolId("core", "loose")
    registry.register(
        tool_id=loose,
        description="No additionalProperties declared.",
        input_schema={"type": "object", "properties": {"a": {"type": "integer"}}},
        callable_=lambda **kwargs: len(kwargs),
    )
    result = registry.invoke(loose, {"a": 1, "extra": 2})
    assert result.ok
    assert result.value == 2


def test_deeply_nested_arguments_do_not_recurse_infinitely() -> None:
    """Hostile *arguments* are bounded the same way hostile schemas are."""
    registry = ToolRegistry()
    tool_id = ToolId("core", "echo")
    registry.register(
        tool_id=tool_id,
        description="Echo.",
        input_schema={"type": "object", "properties": {"a": {"type": "object"}}},
        callable_=lambda **_: 1,
    )
    payload: dict[str, object] = {"a": 1}
    for _ in range(3000):
        payload = {"a": payload}
    result = registry.invoke(tool_id, {"a": payload})
    # Either accepted or rejected, but it must return rather than crash.
    assert result.ok or result.failure is not None


def test_error_output_is_bounded() -> None:
    """Validation output is capped so a hostile payload cannot flood a prompt."""
    props = {f"p{i}": {"type": "integer"} for i in range(MAX_ERRORS + 20)}
    registry = ToolRegistry()
    tool_id = ToolId("core", "wide")
    registry.register(
        tool_id=tool_id,
        description="Many fields.",
        input_schema={
            "type": "object",
            "properties": props,
            "required": list(props),
            "additionalProperties": False,
        },
        callable_=lambda **_: 1,
    )
    result = registry.invoke(tool_id, {})
    assert not result.ok
    assert result.failure is not None
    assert result.failure.message.count(";") < MAX_ERRORS


# --------------------------------------------------------------------------- #
# The injection boundary (spec §6) -- the security-critical section
# --------------------------------------------------------------------------- #


def _registry_with_injected() -> tuple[ToolRegistry, ToolId]:
    registry = ToolRegistry()
    tool_id = ToolId("core", "read_file")
    registry.register(
        tool_id=tool_id,
        description="Read a file within the sandbox root.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}, "root": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        callable_=lambda *, path, root: f"{root}/{path}",
        injected=frozenset({"root"}),
    )
    return registry, tool_id


def test_injected_argument_is_absent_from_the_model_facing_schema() -> None:
    """A model must never see a privileged parameter."""
    registry, tool_id = _registry_with_injected()
    tool = registry.get(tool_id)
    assert tool is not None
    assert "root" not in tool.input_schema["properties"]
    assert "root" in tool.validation_schema["properties"]


def test_required_list_drops_injected_names_in_the_model_view() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("core", "x")
    registry.register(
        tool_id=tool_id,
        description="d",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "string"}, "secret": {"type": "string"}},
            "required": ["a", "secret"],
        },
        callable_=lambda **_: 1,
        injected=frozenset({"secret"}),
    )
    tool = registry.get(tool_id)
    assert tool is not None
    assert "secret" not in tool.input_schema.get("required", [])


def test_caller_supplied_injected_value_is_discarded_and_replaced() -> None:
    """The forging defence, verified end to end.

    LangGraph's source strips caller-supplied values for injected keys before
    adding trusted ones, with the comment: "This prevents an LLM from forging
    hidden InjectedToolArg fields via ToolCall.args."
    """
    registry, tool_id = _registry_with_injected()
    tool = registry.get(tool_id)
    assert tool is not None

    # An attacker supplies a value for the injected 'root'.
    result = registry.invoke(
        tool_id,
        {"path": "etc/passwd", "root": "/tmp/attacker"},
        trusted={"root": "/srv/sandbox"},
    )

    assert result.ok
    # The forged value must have had no effect whatsoever.
    assert result.value == "/srv/sandbox/etc/passwd"
    assert result.value != "/tmp/attacker/etc/passwd"


def test_forged_injected_value_is_not_an_error_merely_ineffective() -> None:
    """Supplying an injected name is ignored, not rejected.

    Rejecting it would leak the existence of a privileged parameter to whatever
    produced the call.
    """
    registry, tool_id = _registry_with_injected()
    result = registry.invoke(
        tool_id, {"path": "a", "root": "forged"}, trusted={"root": "/ok"}
    )
    assert result.ok
    assert result.value == "/ok/a"


def test_injected_argument_must_be_declared_in_input_schema() -> None:
    registry = ToolRegistry()
    with pytest.raises(InvalidSchemaError) as excinfo:
        registry.register(
            tool_id=ToolId("core", "x"),
            description="d",
            input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
            callable_=lambda **_: 1,
            injected=frozenset({"undeclared"}),
        )
    assert "undeclared" in str(excinfo.value)


def test_missing_trusted_value_is_an_invalid_arguments_failure() -> None:
    """A host that forgets to supply a trusted value must fail, not silently default."""
    registry, tool_id = _registry_with_injected()
    result = registry.invoke(tool_id, {"path": "a"})
    assert not result.ok
    assert result.failure is not None
    assert result.failure.kind is FailureKind.INVALID_ARGUMENTS


# --------------------------------------------------------------------------- #
# Failure taxonomy (spec §7)
# --------------------------------------------------------------------------- #


def test_unknown_tool_id_raises_and_is_not_model_visible() -> None:
    """A hallucinated name cannot be fixed by the model that hallucinated it."""
    registry, _ = _registry_with_add()
    with pytest.raises(ToolNotFoundError):
        registry.invoke(ToolId("core", "nope"), {})


def test_failure_kind_model_visibility_is_correct() -> None:
    assert FailureKind.NOT_FOUND.model_visible is False
    assert FailureKind.INVALID_ARGUMENTS.model_visible is True
    assert FailureKind.EXECUTION_FAILED.model_visible is True


def test_tool_exception_becomes_an_execution_failure_preserving_the_cause() -> None:
    registry = ToolRegistry()
    tool_id = ToolId("core", "boom")

    def explode(*, a: int) -> int:
        raise ValueError("internal detail that must not leak")

    registry.register(
        tool_id=tool_id,
        description="Explodes.",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        },
        callable_=explode,
    )

    result = registry.invoke(tool_id, {"a": 1})
    assert not result.ok
    assert result.failure is not None
    assert result.failure.kind is FailureKind.EXECUTION_FAILED
    assert result.failure.model_visible
    # The original is preserved, never masked (unlike KernelInvokeException).
    assert isinstance(result.failure.cause, ValueError)
    # ...and its message does not leak into the model-visible text.
    assert "internal detail" not in result.failure.message


def test_internal_exceptions_are_not_converted_to_tool_failures() -> None:
    """A bug in our own code must propagate, not masquerade as a tool failure.

    Only an exception raised by the *tool body* becomes an ExecutionFailed
    result. Anything raised while reading the caller's arguments is a bug in
    this package or its caller, and must surface as itself -- otherwise a real
    defect would be reported to a model as "the tool failed", which is both
    false and unfixable by the model.
    """

    class Hostile:
        """A mapping that raises when the registry reads its contents."""

        def items(self) -> object:
            raise RuntimeError("a bug in our own argument handling")

    registry, tool_id = _registry_with_add()
    # Not a ToolResult with EXECUTION_FAILED -- it must surface as itself.
    with pytest.raises(RuntimeError):
        registry.invoke(tool_id, Hostile())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Introspection (spec §10)
# --------------------------------------------------------------------------- #


def test_ids_are_sorted_and_stable() -> None:
    registry = ToolRegistry()
    for ns, name in [("b", "z"), ("a", "y"), ("a", "x")]:
        registry.register(
            tool_id=ToolId(ns, name),
            description="d",
            input_schema={"type": "object"},
            callable_=lambda **_: 1,
        )
    assert registry.ids() == (ToolId("a", "x"), ToolId("a", "y"), ToolId("b", "z"))


def test_describe_excludes_the_callable() -> None:
    """Descriptors cross boundaries that callables should not."""
    registry, tool_id = _registry_with_add()
    descriptor = registry.describe(tool_id)
    assert descriptor is not None
    assert not hasattr(descriptor, "callable")


def test_describe_returns_none_for_unknown_tool() -> None:
    registry, _ = _registry_with_add()
    assert registry.describe(ToolId("core", "ghost")) is None


def test_contains_and_len() -> None:
    registry, tool_id = _registry_with_add()
    assert tool_id in registry
    assert ToolId("core", "ghost") not in registry
    assert len(registry) == 1


# --------------------------------------------------------------------------- #
# Purity (spec D-9)
# --------------------------------------------------------------------------- #


def test_no_third_party_imports() -> None:
    """Zero runtime dependencies is a requirement, not an aspiration."""
    import tool_registry
    import tool_registry.errors
    import tool_registry.ids
    import tool_registry.registry
    import tool_registry.schema

    allowed_prefixes = (
        "tool_registry",
        "__future__",
        "collections",
        "dataclasses",
        "enum",
        "re",
        "types",
        "typing",
    )
    for module in (
        tool_registry,
        tool_registry.errors,
        tool_registry.ids,
        tool_registry.registry,
        tool_registry.schema,
    ):
        for name in vars(module):
            obj = getattr(module, name)
            if isinstance(obj, type(sys)):
                assert (
                    obj.__name__.split(".")[0] in allowed_prefixes
                ), f"{module.__name__} imports third-party module {obj.__name__}"
