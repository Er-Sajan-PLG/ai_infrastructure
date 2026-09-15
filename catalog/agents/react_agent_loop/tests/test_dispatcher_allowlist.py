"""Tests for the per-run tool allowlist on RegistryDispatcher.

Why this file exists
--------------------
The 2026-09-16 audit found the agent loop advertised **every** registered tool
and offered no way for a caller to narrow the set. An agent run against a
fifty-tool registry was offered all fifty whether or not the task needed write
access. That is `AI-003` (least privilege) in the audit's own words: "the
tool/permission allowlist: what an agent can call, with which credentials, and
what is blocked by default."

The fix is a set, not a predicate, so the restriction is inspectable and
serialisable. These tests pin both halves: what a model is *offered*, and what
happens when it asks for something it was not offered.

The second half matters more than it looks. A filter that only applied to
advertising would be a suggestion: a model can emit a name it remembers from a
system prompt or a previous run, and `dispatch` is where that gets refused.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

_CATALOG = Path(__file__).resolve().parents[3]
for _sub in ("models", "tools", "agents"):
    sys.path.insert(0, str(_CATALOG / _sub))

from model_provider import ToolCallBlock  # noqa: E402
from react_agent_loop import RegistryDispatcher  # noqa: E402
from tool_registry import ToolId, ToolRegistry  # noqa: E402


def _registry(*names: str) -> ToolRegistry:
    """A registry holding one trivial tool per name."""
    registry = ToolRegistry()
    for name in names:
        registry.register(
            tool_id=ToolId("demo", name),
            description=f"The {name} tool.",
            input_schema={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
                "additionalProperties": False,
            },
            callable_=lambda *, x, _name=name: f"{_name}:{x}",
        )
    return registry


def _call(name: str, args: dict[str, str] | None = None) -> ToolCallBlock:
    return ToolCallBlock(id="c1", name=name, arguments=args or {"x": "v"})


def _names(schemas: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(s["name"]) for s in schemas]


# --------------------------------------------------------------------------- #
# Default behaviour is unchanged
# --------------------------------------------------------------------------- #


def test_no_allowlist_advertises_every_registered_tool() -> None:
    """The pre-existing behaviour must survive: `allowed=None` means everything."""
    dispatcher = RegistryDispatcher(_registry("a", "b", "c"))
    assert _names(dispatcher.schemas()) == ["demo:a", "demo:b", "demo:c"]


def test_no_allowlist_dispatches_a_registered_tool() -> None:
    dispatcher = RegistryDispatcher(_registry("a"))
    outcome = dispatcher.dispatch(_call("demo:a"))
    assert outcome.ok
    assert outcome.text == "a:v"


# --------------------------------------------------------------------------- #
# Advertising: the visible half
# --------------------------------------------------------------------------- #


def test_allowlist_narrows_what_is_advertised() -> None:
    dispatcher = RegistryDispatcher(
        _registry("read", "write", "delete"), allowed=frozenset({"demo:read"})
    )
    assert _names(dispatcher.schemas()) == ["demo:read"]


def test_allowlist_order_is_still_sorted() -> None:
    """Restricting must not make the enumeration order unstable."""
    dispatcher = RegistryDispatcher(
        _registry("a", "b", "c"), allowed=frozenset({"demo:c", "demo:a"})
    )
    assert _names(dispatcher.schemas()) == ["demo:a", "demo:c"]


def test_an_empty_allowlist_advertises_nothing() -> None:
    """An empty set is a valid policy: this run gets no tools at all.

    Distinct from None. `None` means "unrestricted"; `frozenset()` means
    "none", and conflating them would make a deliberately tool-less run
    impossible to express.
    """
    dispatcher = RegistryDispatcher(_registry("a", "b"), allowed=frozenset())
    assert dispatcher.schemas() == ()


def test_the_model_facing_schema_is_still_used() -> None:
    """The allowlist must not change *which* schema view is advertised."""
    dispatcher = RegistryDispatcher(_registry("a"), allowed=frozenset({"demo:a"}))
    parameters = dispatcher.schemas()[0]["parameters"]
    assert parameters["properties"] == {"x": {"type": "string"}}


# --------------------------------------------------------------------------- #
# Dispatch: the enforcing half, and the reason it is not redundant
# --------------------------------------------------------------------------- #


def test_a_tool_outside_the_allowlist_is_refused_even_though_it_exists() -> None:
    """The whole point: hiding a tool is a suggestion, refusing it is a rule.

    `_by_name` still maps every registered tool, so without this check a model
    that emitted a name it remembered would have been served.
    """
    dispatcher = RegistryDispatcher(
        _registry("read", "delete"), allowed=frozenset({"demo:read"})
    )
    outcome = dispatcher.dispatch(_call("demo:delete"))
    assert outcome.ok is False
    assert outcome.model_visible is False
    assert outcome.kind == "not_found"


def test_a_refused_tool_is_indistinguishable_from_a_missing_one() -> None:
    """Both report the same kind, deliberately.

    Telling the model "that tool exists but you may not use it" would also tell
    it the tool exists. Being denied a capability it was never offered should
    look, from the model's side, exactly like the capability not being there.
    """
    dispatcher = RegistryDispatcher(
        _registry("read", "delete"), allowed=frozenset({"demo:read"})
    )

    denied = dispatcher.dispatch(_call("demo:delete"))
    missing = dispatcher.dispatch(_call("demo:absent"))

    assert denied.kind == missing.kind == "not_found"
    assert denied.model_visible == missing.model_visible is False
    assert denied.text == missing.text is None


def test_an_allowed_tool_still_dispatches() -> None:
    dispatcher = RegistryDispatcher(
        _registry("read", "delete"), allowed=frozenset({"demo:read"})
    )
    assert dispatcher.dispatch(_call("demo:read")).ok


def test_an_empty_allowlist_refuses_everything() -> None:
    dispatcher = RegistryDispatcher(_registry("a"), allowed=frozenset())
    outcome = dispatcher.dispatch(_call("demo:a"))
    assert outcome.ok is False
    assert outcome.kind == "not_found"


# --------------------------------------------------------------------------- #
# Construction-time rejection
# --------------------------------------------------------------------------- #


def test_an_unknown_name_in_the_allowlist_is_rejected_at_construction() -> None:
    """A typo in a policy must fail before a model call is paid for.

    Ignoring it would produce a restriction that looks like it works while
    permitting nothing the caller intended.
    """
    with pytest.raises(ValueError, match="not registered"):
        RegistryDispatcher(_registry("read"), allowed=frozenset({"demo:reed"}))


def test_the_rejection_names_the_offending_tool() -> None:
    with pytest.raises(ValueError, match="demo:typo"):
        RegistryDispatcher(_registry("read"), allowed=frozenset({"demo:typo"}))


def test_a_partially_valid_allowlist_is_still_rejected() -> None:
    """One good name does not excuse one bad one."""
    with pytest.raises(ValueError, match="demo:bad"):
        RegistryDispatcher(
            _registry("read", "write"), allowed=frozenset({"demo:read", "demo:bad"})
        )


def test_the_full_allowlist_is_accepted() -> None:
    """Naming everything explicitly is legal, if redundant."""
    dispatcher = RegistryDispatcher(
        _registry("a", "b"), allowed=frozenset({"demo:a", "demo:b"})
    )
    assert _names(dispatcher.schemas()) == ["demo:a", "demo:b"]


# --------------------------------------------------------------------------- #
# The registry cannot change under a restriction
# --------------------------------------------------------------------------- #


def test_a_tool_registered_after_construction_is_still_governed() -> None:
    """The allowlist is a name set, not a snapshot of ToolId objects.

    A tool added to the registry later is not in `allowed`, so it is neither
    advertised nor dispatchable. Rebuilding from `ids()` at construction would
    have made this depend on timing; comparing names does not.
    """
    registry = _registry("read")
    dispatcher = RegistryDispatcher(registry, allowed=frozenset({"demo:read"}))

    registry.register(
        tool_id=ToolId("demo", "late"),
        description="Registered after the dispatcher was built.",
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
            "additionalProperties": False,
        },
        callable_=lambda *, x: f"late:{x}",
    )

    assert _names(dispatcher.schemas()) == ["demo:read"]
    assert dispatcher.dispatch(_call("demo:late")).kind == "not_found"
