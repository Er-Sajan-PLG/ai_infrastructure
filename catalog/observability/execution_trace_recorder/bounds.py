"""Bounding, so a record is always writable and never unbounded.

ADR-0010 D-10. Research §3.5: MLflow is the only surveyed system that documents
its truncation limits (250 / 1000 / 10000, suffix ``"..."``). The *numbers* here
are ours; the practice of stating them is theirs.

``max_content_chars`` matches ``react-agent-loop``'s ``max_observation_chars``
rather than inventing a second convention for the same kind of data (ADR-0008
D-6). Truncation is head-only with a suffix naming how many characters were
removed, so a reader can tell a complete value from a cut one without knowing the
limit that applied.

Every truncation is *named*: the caller records which fields were cut, so a
consumer never has to guess whether a value is whole.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["Bounds", "json_safe", "truncate"]

# How much a truncated value says it dropped, e.g. "…[+4120 chars]".
_MARKER_TEMPLATE = "…[+{removed} chars]"


@dataclass(frozen=True, slots=True)
class Bounds:
    """Every limit the recorder applies before writing.

    Attributes:
        max_error_message_chars: An error message is a sanitised line, not a
            stack trace. 500 is generous for the former and far too small for
            the latter, which is the point.
        max_content_chars: Matches ``react-agent-loop``'s
            ``max_observation_chars``.
        max_records: A recorder that grows without bound is a leak. Records past
            the cap are dropped and the count is kept, so a bounded trace of an
            unbounded run is honestly incomplete rather than silently so.
    """

    max_error_message_chars: int = 500
    max_content_chars: int = 8000
    max_records: int = 10000

    def __post_init__(self) -> None:
        for name in (
            "max_error_message_chars",
            "max_content_chars",
            "max_records",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Cut ``text`` to ``limit`` characters, head-first.

    Args:
        text: The value to bound.
        limit: Maximum characters to keep.

    Returns:
        ``(text_or_cut, was_cut)``. The cut form names how many characters were
        removed, so a reader sees the loss without knowing the limit.
    """
    if limit <= 0 or len(text) <= limit:
        # limit <= 0 is a degenerate configuration rather than an error here;
        # Bounds rejects it at construction.
        return text, False
    removed = len(text) - limit
    return text[:limit] + _MARKER_TEMPLATE.format(removed=removed), True


def json_safe(value: object, *, _depth: int = 0) -> object:
    """Convert ``value`` into something ``json.dumps`` accepts, without raising.

    A recorder that raised on an unserialisable payload would kill the run it
    was observing — ADR-0010 D-9. So anything JSON cannot represent is replaced
    by its ``repr``, bounded, rather than dropped or raised on.

    Args:
        value: Any object.
        _depth: Internal recursion guard; not for callers.

    Returns:
        A value built only from ``dict``, ``list``, ``str``, ``int``, ``float``,
        ``bool`` and ``None``.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if _depth > 12:
        # Deep or cyclic structure. A cycle would recurse forever; the depth cap
        # converts that into a bounded string instead of a RecursionError.
        return "<nested too deep>"

    if isinstance(value, Mapping):
        return {str(k): json_safe(v, _depth=_depth + 1) for k, v in value.items()}

    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item, _depth=_depth + 1) for item in value]

    if isinstance(value, (bytes, bytearray)):
        # Bytes are not JSON. Rendering a length is more useful than a repr of
        # the whole payload, which could be megabytes.
        return f"<{type(value).__name__} {len(value)} bytes>"

    if isinstance(value, Sequence) and not isinstance(value, str):
        return [json_safe(item, _depth=_depth + 1) for item in value]

    try:
        rendered = repr(value)
    except Exception:
        return f"<unrepresentable {type(value).__name__}>"
    return rendered


def bound_content(
    content: Mapping[str, Any] | None, limit: int
) -> tuple[Mapping[str, Any] | None, bool]:
    """Make ``content`` JSON-safe and bound its string leaves.

    Args:
        content: The payload, or ``None``.
        limit: Per-string character bound.

    Returns:
        ``(content_or_None, was_truncated)``. The mapping's *shape* is preserved
        and only string leaves are cut, so a consumer still sees every key.
    """
    if content is None:
        return None, False

    safe = json_safe(content)
    if not isinstance(safe, dict):
        # json_safe returns a dict for a Mapping input; this is a type-level
        # statement rather than a possibility.
        return None, False

    cut = _bound_strings(safe, limit)
    return safe, cut


def _bound_strings(value: object, limit: int) -> bool:
    """Cut string leaves of ``value`` in place; return whether anything was cut."""
    if isinstance(value, dict):
        was_cut = False
        for key, item in value.items():
            if isinstance(item, str):
                cut_value, cut = truncate(item, limit)
                if cut:
                    value[key] = cut_value
                    was_cut = True
            else:
                was_cut = _bound_strings(item, limit) or was_cut
        return was_cut

    if isinstance(value, list):
        was_cut = False
        for index, item in enumerate(value):
            if isinstance(item, str):
                cut_value, cut = truncate(item, limit)
                if cut:
                    value[index] = cut_value
                    was_cut = True
            else:
                was_cut = _bound_strings(item, limit) or was_cut
        return was_cut

    return False
