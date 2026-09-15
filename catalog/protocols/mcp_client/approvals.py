"""The approval seam — this capability's answer to `AI-010`.

The 2026-09-16 audit adjudicated "consequential actions require human
confirmation" a legitimate **DEFER** for `react-agent-loop`, because that loop
dispatches *in-process, to code the caller wrote*, and its README declares
approval gates a non-goal. That reasoning does not carry here: this client
dispatches to **processes we did not write**, and the protocol's own tools page
carries a ``<Warning>`` that there *"SHOULD always be a human in the loop with
the ability to deny tool invocations."*

So the seam is mandatory and the default **denies**.

The two shipped policies are deliberately spelled out rather than implied:
:class:`DenyAllApprovals` is the default, and a caller who wants autonomy writes
:class:`AllowAllApprovals` — a name that reads as the decision it is. A library
that permitted by default would have made the consequential decision on the
caller's behalf, and the caller would never see it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable

__all__ = [
    "AllowAllApprovals",
    "ApprovalPolicy",
    "ApprovalRequest",
    "CallableApprovals",
    "DenyAllApprovals",
]


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Everything a policy needs to decide, and nothing more.

    Attributes:
        tool_name: The remote tool name, as the server reported it — not the
            registry's ``namespace:name`` rendering, because a policy reasons
            about what the *server* offers.
        arguments: The arguments about to be sent, frozen into a read-only
            mapping so a policy cannot mutate the call it just approved.
        namespace: The client-minted namespace the tool was projected under.
    """

    tool_name: str
    arguments: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    namespace: str = ""


@runtime_checkable
class ApprovalPolicy(Protocol):
    """Decides whether one ``tools/call`` may proceed."""

    def decide(self, request: ApprovalRequest) -> bool:
        """Return ``True`` to permit the call, ``False`` to refuse it."""
        ...


class DenyAllApprovals:
    """Refuses every call. The default when no policy is supplied."""

    __slots__ = ()

    # The parameter is required by the ApprovalPolicy protocol, not by this
    # implementation -- refusing does not depend on what is being refused.
    # Keeping the name means a caller can still invoke it as
    # `decide(request=...)`, which a rename to `_request` would break.
    def decide(self, request: ApprovalRequest) -> bool:  # noqa: ARG002
        return False

    def __repr__(self) -> str:
        return "DenyAllApprovals()"


class AllowAllApprovals:
    """Permits every call.

    Supported, and named so that a reader of the code sees the decision. It is
    not the default, and it should not be reached for casually: a policy that
    always returns ``True`` is indistinguishable from having no policy at all.
    """

    __slots__ = ()

    # Same as DenyAllApprovals: the signature is the protocol's, and permitting
    # unconditionally is exactly the decision this class exists to name.
    def decide(self, request: ApprovalRequest) -> bool:  # noqa: ARG002
        return True

    def __repr__(self) -> str:
        return "AllowAllApprovals()"


class CallableApprovals:
    """Adapts a plain ``Callable[[ApprovalRequest], bool]`` to the protocol.

    For tests and for callers who already have a function. The object is
    ``__repr__``'d with the callable's own name so a denial message can name the
    policy that refused, which is the difference between a useful diagnostic and
    "denied by policy" with no way to find the policy.
    """

    __slots__ = ("_decide", "_name")

    def __init__(self, decide: Callable[[ApprovalRequest], bool]) -> None:
        if not callable(decide):
            raise TypeError("CallableApprovals needs a callable")
        self._decide = decide
        self._name = getattr(decide, "__name__", type(decide).__name__)

    def decide(self, request: ApprovalRequest) -> bool:
        return bool(self._decide(request))

    def __repr__(self) -> str:
        return f"CallableApprovals({self._name})"
