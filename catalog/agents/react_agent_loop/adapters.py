"""Optional bindings to the two capabilities this loop composes (ADR-0008 D-1).

These are the only modules in the entry that import tool_registry or
model_provider's behaviour. Everything else runs against the protocols, which is
what lets the test suite drive every failure path with scripted doubles.

Both adapters are small. That is the whole cost of the seam, and it buys a loop
that can be tested without a registry, a model or an API key.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from model_provider import (
    ChatRequest,
    ChatResponse,
    Message,
    Provider,
    ToolCallBlock,
    Transport,
    chat,
)
from tool_registry import ToolId, ToolNotFoundError, ToolRegistry

from .protocols import DispatchOutcome

__all__ = ["ProviderCaller", "RegistryDispatcher"]


class RegistryDispatcher:
    """Adapts a ToolRegistry to the ToolDispatcher protocol.

    Tool names are the registry's own namespace:name rendering. The mapping is
    built by rendering every registered id, never by parsing a name back into a
    ToolId: ToolId.__str__ is documented as display-only, and parsing it would
    reintroduce the ambiguity it exists to avoid.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        allowed: frozenset[str] | None = None,
    ) -> None:
        """Bind a registry, optionally restricting which tools this run may use.

        Args:
            registry: The source of tools.
            allowed: Tool names (the same ``namespace:name`` rendering used on the
                wire) that this dispatcher will advertise and dispatch. ``None``
                means every registered tool -- the pre-existing behaviour.

                A set rather than a predicate so the restriction is inspectable and
                serialisable; a callback would be untestable by inspection and
                impossible to log.

        Raises:
            ValueError: ``allowed`` names a tool the registry does not hold.
                Rejected at construction rather than ignored, for the same reason
                ``run()`` rejects ``max_steps=0``: a typo in a policy should fail
                before a model call is paid for, and a silently-ignored name would
                look like a working restriction while permitting nothing.

        Why this exists: the 2026-09-16 audit found the loop advertised *every*
        registered tool with no way for a caller to narrow the set -- an agent run
        against a fifty-tool registry was offered all fifty, whether or not the
        task needed write access. Least privilege is a caller decision, so it is a
        constructor argument and not a default the adapter picks.
        """
        self._registry = registry
        self._allowed = allowed
        self._by_name: dict[str, ToolId] = {
            str(tool_id): tool_id for tool_id in registry.ids()
        }
        if allowed is not None:
            unknown = sorted(allowed - set(self._by_name))
            if unknown:
                raise ValueError(
                    f"allowed names {', '.join(unknown)} are not registered; "
                    f"this dispatcher can only permit what the registry holds"
                )

    def schemas(self) -> Sequence[Mapping[str, Any]]:
        """Advertise the permitted tools, using their model-facing schema.

        The registry keeps two schema views precisely so injected parameters never
        reach a model (ADR-0006 D-3). Advertising validation_schema here would
        undo that, so this uses input_schema.

        The schema is converted to plain JSON-safe containers. This is not
        defensive padding -- it is a defect this integration found. The registry
        exposes ``input_schema`` as a ``MappingProxyType`` for good reason
        (immutability), and ``MappingProxyType`` is a perfectly valid
        ``Mapping``. But a provider adapter encodes a request with
        ``json.dumps``, and ``json.dumps`` cannot serialise a mappingproxy::

            TypeError: Object of type mappingproxy is not JSON serializable

        Neither capability's own tests caught this, because neither crosses the
        boundary. The dispatcher's documented job is to return tools "in the
        neutral OpenAI-shaped form that every provider adapter accepts", so the
        conversion belongs here.

        When ``allowed`` was given at construction, only those tools are
        advertised. This is the half of least privilege that a model can see: a
        tool it is never offered is a tool it is far less likely to call, so the
        filter is the primary control and :meth:`dispatch` is the backstop for a
        model that calls one anyway.
        """
        schemas: list[Mapping[str, Any]] = []
        for name, tool_id in sorted(self._by_name.items()):
            if self._allowed is not None and name not in self._allowed:
                continue
            descriptor = self._registry.describe(tool_id)
            if descriptor is None:  # pragma: no cover - ids() and describe() agree
                continue
            schemas.append(
                {
                    "name": name,
                    "description": descriptor.description,
                    "parameters": _json_safe(descriptor.input_schema),
                }
            )
        return tuple(schemas)

    def dispatch(self, call: ToolCallBlock) -> DispatchOutcome:
        """Invoke a call, translating the registry's taxonomy into an outcome.

        The registry already classifies failures by whether a model can act on
        them (ADR-0006 D-4). This adapter obeys that classification rather than
        re-litigating it: duplicating the judgement here would let the two drift,
        and the loop would then enforce a rule the registry no longer holds.

        A call for a tool outside ``allowed`` is refused here, not merely hidden
        from :meth:`schemas`. Hiding it is the primary control -- a model cannot
        ask for what it was never offered -- but a model can still emit a name it
        remembers from a system prompt or a previous run, and a filter that only
        applied to advertising would be a suggestion rather than a restriction.

        The refusal is reported with ``model_visible=False`` and ``kind="not_found"``
        for the same reason the registry does so: the model cannot be told "that
        tool exists but you may not use it" without also being told the tool
        exists. Being denied a capability it was never offered is indistinguishable,
        from the model's side, from the tool not being there -- and that
        indistinguishability is the point.
        """
        tool_id = self._by_name.get(call.name)
        if tool_id is None or (
            self._allowed is not None and call.name not in self._allowed
        ):
            return DispatchOutcome(
                ok=False,
                text=None,
                model_visible=False,
                kind="not_found",
                tool_id=call.name,
            )

        try:
            result = self._registry.invoke(tool_id, call.arguments)
        except ToolNotFoundError:
            # The name resolved a moment ago, so the registry changed under us.
            # Treated exactly like a miss: not model-visible.
            return DispatchOutcome(
                ok=False,
                text=None,
                model_visible=False,
                kind="not_found",
                tool_id=str(tool_id),
            )

        if result.ok:
            return DispatchOutcome(
                ok=True,
                text=_as_observation(result.value),
                model_visible=True,
                kind="ok",
                tool_id=str(tool_id),
            )

        failure = result.failure
        if failure is None:  # pragma: no cover - ToolResult guarantees one
            raise AssertionError("ToolResult reported failure with no ToolFailure")

        kind = str(failure.kind)
        if not failure.model_visible:
            return DispatchOutcome(
                ok=False,
                text=None,
                model_visible=False,
                kind=kind,
                tool_id=str(tool_id),
            )
        return DispatchOutcome(
            ok=False,
            text=f"tool error [{kind}]: {failure.message}",
            model_visible=True,
            kind=kind,
            tool_id=str(tool_id),
        )


def _json_safe(value: Any) -> Any:
    """Recursively convert a value into containers ``json.dumps`` can encode.

    A deep conversion, not ``dict(value)``: a shallow copy of a mapping leaves
    its *nested* values untouched, so a mappingproxy one level down still
    reaches ``json.dumps`` and still raises. That is exactly the bug this
    function fixes -- see :meth:`RegistryDispatcher.schemas`.

    Unknown leaf types are returned unchanged rather than stringified. Coercing
    them here would hide a genuinely unserialisable value until it failed
    somewhere less obvious; leaving them lets the encoder raise at the boundary
    that actually owns the problem.
    """
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _as_observation(value: Any) -> str:
    """Render a tool's value as observation text.

    A tool contract says it returns a string; anything else is repr'd so an
    integer result is not silently indistinguishable from the string "42". The
    distinction matters when the model is reasoning about types.
    """
    if isinstance(value, str):
        return value
    return repr(value)


class ProviderCaller:
    """Adapts a provider plus transport to the ModelCaller protocol.

    Holds the model settings because the protocol's call receives the
    conversation, not a whole request: the loop is not a place to configure a
    provider, and putting temperature on Agent means the loop never has to know
    which provider ignores it.
    """

    def __init__(
        self,
        *,
        provider: Provider,
        transport: Transport,
        api_key: str,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self._provider = provider
        self._transport = transport
        self._api_key = api_key
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature

    def call(
        self,
        messages: Sequence[Message],
        *,
        system: str | None,
        tools: Sequence[Mapping[str, Any]],
    ) -> ChatResponse:
        """Encode and send one non-streaming chat request."""
        request = ChatRequest(
            model=self._model,
            messages=messages,
            system=system,
            max_output_tokens=self._max_output_tokens,
            temperature=self._temperature,
            tools=tools,
        )
        return chat(
            request,
            provider=self._provider,
            transport=self._transport,
            api_key=self._api_key,
        )
