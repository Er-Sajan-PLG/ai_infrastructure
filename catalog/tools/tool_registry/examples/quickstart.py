#!/usr/bin/env python3
"""A runnable tour of the tool registry.

Demonstrates registration, introspection, strict validation, the two failure
channels, and -- most importantly -- the injection boundary that stops a model
from forging a privileged argument.

Run::

    python catalog/tools/tool_registry/examples/quickstart.py

No model, no network, no dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tool_registry import (
    FailureKind,
    InvalidSchemaError,
    ToolId,
    ToolNotFoundError,
    ToolRegistry,
)

SANDBOX_ROOT = "/srv/sandbox"


def read_file(*, path: str, root: str) -> str:
    """Read a file inside the sandbox root."""
    return f"<contents of {root}/{path}>"


def main() -> None:
    registry = ToolRegistry()

    # --- 1. Register a tool with an injected argument ---------------------- #
    #
    # `root` is declared so the host can supply it, but it is in `injected`,
    # so it is removed from the schema the model would ever see.
    read_id = ToolId("core", "read_file")
    registry.register(
        tool_id=read_id,
        description="Read a file within a sandbox root.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the root."},
                "root": {"type": "string"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        callable_=read_file,
        injected=frozenset({"root"}),
    )

    add_id = ToolId("core", "add")
    registry.register(
        tool_id=add_id,
        description="Add two integers.",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        callable_=lambda *, a, b: a + b,
    )

    print("1. REGISTERED")
    for tool_id in registry.ids():
        print(f"   {tool_id}")

    # --- 2. Introspect without invoking ------------------------------------ #
    descriptor = registry.describe(read_id)
    assert descriptor is not None
    visible = sorted(descriptor.input_schema["properties"])
    print("\n2. INTROSPECTION")
    print(f"   model sees properties: {visible}")
    print(f"   host-only injected:    {sorted(descriptor.injected)}")
    print(f"   'root' hidden from model: {'root' not in visible}")

    # --- 3. Success -------------------------------------------------------- #
    result = registry.invoke(add_id, {"a": 2, "b": 40})
    print("\n3. SUCCESS")
    print(f"   add(2, 40) = {result.value}")

    # --- 4. The two failure channels --------------------------------------- #
    print("\n4. FAILURE TAXONOMY (divided by whether a model can act on it)")

    bad_args = registry.invoke(add_id, {"a": 1, "b": "two"})
    assert bad_args.failure is not None
    print(f"   invalid arguments -> {bad_args.failure.kind.value}")
    print(f"      model_visible={bad_args.failure.model_visible}")
    print(f"      message: {bad_args.failure.message}")

    try:
        registry.invoke(ToolId("core", "ghost"), {})
    except ToolNotFoundError:
        print("   unknown tool      -> raises ToolNotFoundError (never a prompt)")

    print(f"      NOT_FOUND.model_visible={FailureKind.NOT_FOUND.model_visible}")

    # --- 5. The injection boundary ----------------------------------------- #
    #
    # An attacker (or a confused model) supplies a value for `root`. It is
    # discarded; only the host-supplied value is used.
    print("\n5. INJECTION BOUNDARY")
    forged = registry.invoke(
        read_id,
        {"path": "etc/passwd", "root": "/tmp/attacker"},  # <- forged
        trusted={"root": SANDBOX_ROOT},  # <- trusted wins
    )
    print("   caller supplied root: /tmp/attacker")
    print(f"   host supplied root:   {SANDBOX_ROOT}")
    print(f"   actual call used:     {forged.value}")
    # The tool's *output* embeds the root it was called with. The forged root
    # must not appear anywhere in it.
    assert SANDBOX_ROOT in forged.value
    assert "/tmp/attacker" not in forged.value
    print("   forged value had no effect ✓")

    # --- 6. Rejection is loud, not silent ---------------------------------- #
    print("\n6. UNSUPPORTED SCHEMAS ARE REJECTED BY NAME")
    try:
        registry.register(
            tool_id=ToolId("core", "bad"),
            description="Uses an unsupported keyword.",
            input_schema={
                "type": "object",
                "properties": {"x": {"type": "string", "$ref": "#/defs/x"}},
            },
            callable_=lambda **_: None,
        )
    except InvalidSchemaError as exc:
        print(f"   rejected: {exc}")
    print("   (silently ignoring $ref would report 'valid' for unchecked input)")

    print("\nDone.")


if __name__ == "__main__":
    main()
