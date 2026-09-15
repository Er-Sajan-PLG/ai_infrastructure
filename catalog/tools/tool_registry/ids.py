"""Stable tool identity.

A tool's identity must outlive any process, connection, or session. Research
found that no surveyed project achieves this (ADR-0006):

- **Model Context Protocol** scopes tool identity to a live connection; it dies
  on restart.
- **Semantic Kernel** flattens a namespace into a model-visible ``"Plugin-function"``
  string that is re-parsed on the way back -- a silent mismatch source.
- **LangChain** keys a dict by bare name, with no namespace and no collision policy.

``ToolId`` is therefore a structured, frozen value. ``str()`` renders it for
humans and error messages; reconstructing an id by splitting that string is not
part of the API (spec §4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ToolRegistryError

__all__ = ["ToolId"]

_PART_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True, slots=True, order=True)
class ToolId:
    """A stable, structured tool identifier.

    Attributes:
        namespace: The owning scope, e.g. ``"core"`` or ``"mcp.github"``.
        name: The tool's name within that namespace, e.g. ``"get_weather"``.
    """

    namespace: str
    name: str

    def __post_init__(self) -> None:
        _check_part("namespace", self.namespace)
        _check_part("name", self.name)

    def __str__(self) -> str:
        """Render for display only -- never parse this back into a ToolId."""
        return f"{self.namespace}:{self.name}"


def _check_part(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ToolRegistryError(f"ToolId {label} must be a non-empty string")
    if not _PART_RE.match(value):
        raise ToolRegistryError(
            f"ToolId {label} {value!r} must match {_PART_RE.pattern} "
            f"(lowercase alphanumerics, '.', '_', '-'; must start alphanumeric)"
        )
