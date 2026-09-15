"""The content-capture policy — off by default, and that is the finding.

ADR-0010 D-8. The evidence is uncomfortable and worth restating here, because a
reader of this file is the person most likely to "helpfully" flip the default:
**only one of the six surveyed systems states a default-off policy** — OTel — and
it is the only one that has been through a privacy review. The other five either
capture by default and redact afterwards, or take no position at all.

The majority practice is not the safe default, which is exactly why following the
crowd would be the wrong move. OTel's own text:

    Instrumentations SHOULD NOT capture this attribute by default.

with ``gen_ai.output.messages`` flagged *"likely to contain sensitive information
including user/PII data."*

So :class:`CaptureNothing` is the default, and enabling capture requires naming
:class:`CaptureEverything` — a name a reviewer sees in a diff.

**A redacted field is not the same as an absent one.** With capture off,
``content`` is ``None``. It is never a ``"__REDACTED__"`` sentinel: that would put
a value where the honest answer is "we did not look".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["CaptureEverything", "CaptureNothing", "CapturePolicy"]


@runtime_checkable
class CapturePolicy(Protocol):
    """Decides whether model content and tool payloads are written."""

    def capture_model_content(self) -> bool:
        """True when prompt and completion text may be recorded."""
        ...

    def capture_tool_payloads(self) -> bool:
        """True when tool arguments and results may be recorded."""
        ...


class CaptureNothing:
    """Writes no content. The default.

    A trace produced under this policy is safe to commit as a test fixture,
    because it contains no model text and no tool payloads.
    """

    __slots__ = ()

    def capture_model_content(self) -> bool:
        return False

    def capture_tool_payloads(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "CaptureNothing()"


class CaptureEverything:
    """Writes model content and tool payloads.

    Supported, and named so that a reviewer sees the decision. **A caller using
    this is capturing PII** when the model or the tools handle any, and that is
    the caller's decision to make explicitly rather than a default they inherit.
    """

    __slots__ = ()

    def capture_model_content(self) -> bool:
        return True

    def capture_tool_payloads(self) -> bool:
        return True

    def __repr__(self) -> str:
        return "CaptureEverything()"
