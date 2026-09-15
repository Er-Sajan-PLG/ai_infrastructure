"""Project remote MCP tools into the local :class:`~tool_registry.ToolRegistry`.

This is where an **external** boundary is met, and it is the only module in the
package that imports ``tool_registry``. Two rules govern it.

**The namespace is client-minted.** ``ToolId(namespace, remote_name)``, with
``namespace`` supplied by the caller. The specification requires the client to
disambiguate collisions and warns that ``serverInfo.name`` is neither unique nor
trustworthy; the security section says ``clientInfo``/``serverInfo`` are
self-reported and **SHOULD NOT** be relied on for security decisions
(ADR-0009 D-4). So the server's name never becomes an identifier.

**A tool the registry cannot represent is excluded — by name, with a reason —
never adapted.** MCP permits any JSON Schema 2020-12 keyword; the registry
implements a documented subset and rejects unknown keywords loudly (ADR-0006
D-2). Loosening the subset is the wrong fix, and ADR-0006 says so: the correct
response to a too-small subset is an ADR adding a dependency, not a quiet
widening. Two concrete cases arise in practice:

* a remote name containing uppercase (MCP allows it; ``ToolId`` does not), and
* an ``inputSchema`` using ``oneOf``/``$ref``/``if`` or any other keyword outside
  the subset.

The specification's own robustness rule — *"one malformed tool must not prevent
other valid tools from being used"* — is adopted here even though its stated
scope is Streamable HTTP, because the failure mode is the same for stdio.

The registry is the **authority** for what it accepts: this module does not
duplicate the subset check, it attempts registration and lets
:class:`~tool_registry.InvalidSchemaError` decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tool_registry import (
    DuplicateToolError,
    InvalidSchemaError,
    ToolId,
    ToolRegistry,
    ToolRegistryError,
)

from .client import MCPClient, ToolDescriptorView

__all__ = ["ExcludedTool", "ProjectionReport", "is_legal_tool_name", "project_tools"]


@dataclass(frozen=True, slots=True)
class ExcludedTool:
    """A remote tool that was not projected, and why.

    Attributes:
        name: The remote name, as the server reported it.
        reason: A short, human-readable explanation.
    """

    name: str
    reason: str


@dataclass(slots=True)
class ProjectionReport:
    """What a projection did.

    Attributes:
        registered: The ids that were successfully added to the registry.
        excluded: The tools that were not, each with its reason.
    """

    registered: list[ToolId] = field(default_factory=list)
    excluded: list[ExcludedTool] = field(default_factory=list)

    @property
    def registered_count(self) -> int:
        """How many tools were added."""
        return len(self.registered)

    @property
    def excluded_count(self) -> int:
        """How many tools were refused."""
        return len(self.excluded)

    def why(self, name: str) -> str | None:
        """Return the exclusion reason for ``name``, or ``None`` if it was kept."""
        for entry in self.excluded:
            if entry.name == name:
                return entry.reason
        return None


# ToolId's own character class: lowercase alphanumerics, '.', '_', '-', and it
# must start alphanumeric. MCP additionally allows uppercase, which is the whole
# point of the check below.
_LEGAL_FIRST = set("abcdefghijklmnopqrstuvwxyz0123456789")
_LEGAL_REST = _LEGAL_FIRST | {".", "_", "-"}


def is_legal_tool_name(name: str) -> bool:
    """True when ``name`` is representable as a ``ToolId.name``.

    This is a *predictive* check for a better error message, not the authority:
    the registry still validates on registration. It exists because
    ``InvalidSchemaError`` would report the failure as a schema problem, and the
    actual problem is the name.
    """
    if not name:
        return False
    if name[0] not in _LEGAL_FIRST:
        return False
    return all(ch in _LEGAL_REST for ch in name[1:])


def project_tools(
    client: MCPClient,
    registry: ToolRegistry,
    *,
    namespace: str | None = None,
) -> ProjectionReport:
    """Project every tool ``client`` advertises into ``registry``.

    Args:
        client: A client whose handshake has already run.
        registry: The destination registry.
        namespace: Overrides the client's namespace. Defaults to the client's,
            which is itself client-minted.

    Returns:
        A :class:`ProjectionReport` naming what was registered and what was
        excluded. The caller can inspect the exclusions rather than assuming the
        projection was total.

    Notes:
        A tool is skipped when the registry would raise on its schema. That is
        deliberate: attempting registration and catching
        :class:`~tool_registry.InvalidSchemaError` makes the registry the single
        authority for what it accepts, instead of a second, drifting copy of the
        subset rule living here.
    """
    effective_namespace = namespace if namespace is not None else client.namespace
    report = ProjectionReport()

    for descriptor in client.list_tools():
        _project_one(client, registry, descriptor, effective_namespace, report)

    return report


def _project_one(
    client: MCPClient,
    registry: ToolRegistry,
    descriptor: ToolDescriptorView,
    namespace: str,
    report: ProjectionReport,
) -> None:
    """Attempt to project one tool, recording either success or the reason."""
    if not is_legal_tool_name(descriptor.name):
        report.excluded.append(
            ExcludedTool(
                name=descriptor.name,
                reason=(
                    "the remote name is not representable as a ToolId name "
                    "(ToolId accepts lowercase alphanumerics, '.', '_' and '-'); "
                    "downcasing it would let two distinct remote tools collide, "
                    "so it is excluded instead (ADR-0009 D-4)"
                ),
            )
        )
        return

    schema = descriptor.input_schema
    if not schema:
        report.excluded.append(
            ExcludedTool(
                name=descriptor.name,
                reason="the server advertised no inputSchema",
            )
        )
        return

    if schema.get("type") != "object":
        report.excluded.append(
            ExcludedTool(
                name=descriptor.name,
                reason=(
                    "inputSchema root type must be 'object' — MCP tool arguments "
                    f"are always objects, got {schema.get('type')!r}"
                ),
            )
        )
        return

    tool_id = ToolId(namespace, descriptor.name)
    try:
        registry.register(
            tool_id=tool_id,
            description=descriptor.description or f"Remote MCP tool {descriptor.name}.",
            input_schema=schema,
            callable_=_make_forwarder(client, descriptor.name),
        )
    except InvalidSchemaError as exc:
        report.excluded.append(
            ExcludedTool(
                name=descriptor.name,
                reason=(
                    f"inputSchema is outside the registry's documented subset: {exc}. "
                    f"Widening the subset requires an ADR (ADR-0006); the tool is "
                    f"excluded rather than validated loosely"
                ),
            )
        )
    except DuplicateToolError as exc:
        report.excluded.append(
            ExcludedTool(
                name=descriptor.name,
                reason=f"already registered under {namespace}: {exc}",
            )
        )
    except ToolRegistryError:  # pragma: no cover - defensive, see below
        # Anything else the registry raises is a programming error in this
        # module, not a property of the remote tool. Re-raised rather than
        # recorded, so it cannot be mistaken for a server problem.
        raise
    else:
        # Success, and `else` rather than a trailing statement after the `try`
        # body: it runs only when no exception was raised, so a future `except`
        # clause cannot accidentally swallow the bookkeeping.
        #
        # This branch is the whole point of the report. A projection that names
        # its exclusions but never its inclusions is a one-sided account: a
        # caller cannot tell a total projection from an empty one, and five
        # tests failed on exactly that before this line existed.
        report.registered.append(tool_id)


def _make_forwarder(client: MCPClient, remote_name: str) -> Any:
    """Build the local callable that forwards to the remote tool.

    The returned callable takes keyword arguments and returns a string. It maps
    the remote outcome onto the registry's own result shape by **raising** on a
    model-visible failure, because that is how a tool body reports a failure: the
    registry catches the exception and converts it into a ``ToolFailure`` with
    ``EXECUTION_FAILED``. Returning a string that merely *looks* like an error
    would report success and let a loop continue on a false premise.
    """

    def _forward(**arguments: object) -> str:
        outcome = client.call_tool(remote_name, arguments)
        if outcome.failure is not None:
            raise _RemoteToolError(outcome.failure.message)
        return outcome.text

    _forward.__name__ = f"mcp_{remote_name}"
    return _forward


class _RemoteToolError(RuntimeError):
    """Raised inside a projected tool body when the remote call failed.

    Private on purpose: the registry converts it to ``EXECUTION_FAILED`` and the
    message it carries is the one the *client* already sanitised, so nothing
    internal escapes into a prompt.
    """
