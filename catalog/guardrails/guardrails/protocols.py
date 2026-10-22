"""Core protocols for the Guardrails capability.

Defines the ``Validator`` protocol, ``ValidationResult`` and the decision
vocabulary. All validators compose these protocols — no inheritance required.

The invariant this module exists to make checkable: a rejection is a *decision
with a reason*, not an exception, and the reason never carries the rejected
content (see ``ValidationResult.__post_init__`` and each validator's docs).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class Severity(StrEnum):
    """How seriously a failed check should be treated.

    ``WARNING`` is advisory: the caller may forward the output while recording
    the finding. ``ERROR`` is blocking unless the policy says otherwise.
    """

    WARNING = "warning"
    ERROR = "error"


class GuardrailDecision(StrEnum):
    """The outcome of running a policy over one piece of output.

    ``PASS`` — every check passed, forward the output.
    ``FLAG`` — a check failed but the output is allowed; the caller decides.
    ``REJECT`` — the output must not be forwarded.

    There is deliberately no ``REGENERATE`` decision: re-generation is a caller
    choice, not a guardrail action (specification §Invariants). A guardrail
    validates; it never rewrites.
    """

    PASS = "pass"  # noqa: S105
    FLAG = "flag"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The result of one validator against one output.

    Attributes:
        validator: The validator's name (the rule that ran).
        passed: Whether the output satisfied the rule.
        severity: How seriously a failure should be treated.
        reason: Why the output failed. Required on failure, forbidden on pass,
            and **never** the rejected content — a rule name, a count, or a
            position only. This is the leak-channel invariant.
        metadata: Structured, content-free detail (counts, offsets, sizes).
    """

    validator: str
    passed: bool
    severity: Severity = Severity.ERROR
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validator:
            raise ValueError("validator must be a non-empty name")
        if self.passed and self.reason is not None:
            raise ValueError("a passing result must not carry a reason")
        if not self.passed and not self.reason:
            raise ValueError("a failing result must carry a reason")


@runtime_checkable
class Validator(Protocol):
    """One deterministic output check.

    Implementations must be pure functions of their input — no hidden state, no
    network calls, no model calls. A validator that needs a model is a later
    stage, not this protocol (specification §Out of scope).
    """

    @property
    def name(self) -> str:
        """Unique validator identifier (the rule that ran)."""
        ...

    def validate(self, text: str) -> ValidationResult:
        """Check one piece of output against this rule."""
        ...


@dataclass(frozen=True, slots=True)
class GuardrailOutcome:
    """The aggregated result of a policy over one piece of output."""

    policy: str
    decision: GuardrailDecision
    results: tuple[ValidationResult, ...]

    @property
    def allowed(self) -> bool:
        """Whether the output may be forwarded (anything but ``REJECT``)."""
        return self.decision is not GuardrailDecision.REJECT

    @property
    def failures(self) -> tuple[ValidationResult, ...]:
        """Only the results that failed, in validator order."""
        return tuple(result for result in self.results if not result.passed)

    @property
    def reasons(self) -> tuple[str, ...]:
        """The content-free reasons for every failure, in validator order."""
        return tuple(
            result.reason for result in self.failures if result.reason is not None
        )
