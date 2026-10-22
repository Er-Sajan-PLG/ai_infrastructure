"""Guardrails — deterministic output validation.

Provides the ``Validator`` protocol, ``ValidationResult`` and the
``PASS`` / ``FLAG`` / ``REJECT`` decision vocabulary, a ``GuardrailPolicy``
that runs every validator it holds, caller-invoked ``Rails`` for input/output
placement, and deterministic validators (length, JSON schema, regex, allowlist,
denylist, PII, one-line, valid-JSON).

Zero runtime dependencies — standard library only. Model-backed classifiers are
deliberately out of scope (DW-015).

See specifications/guardrails.md for the design and
docs/decisions/0038-guardrails-deterministic.md for the decision.
"""

from __future__ import annotations

from .policy import GuardrailPolicy, Rails
from .protocols import (
    GuardrailDecision,
    GuardrailOutcome,
    Severity,
    ValidationResult,
    Validator,
)
from .validators import (
    AllowlistValidator,
    DenylistValidator,
    JsonSchemaValidator,
    LengthBoundValidator,
    OneLineValidator,
    PiiKind,
    PIIValidator,
    RegexMatchValidator,
    ValidJsonValidator,
)

__all__ = [
    "AllowlistValidator",
    "DenylistValidator",
    "GuardrailDecision",
    "GuardrailOutcome",
    "GuardrailPolicy",
    "JsonSchemaValidator",
    "LengthBoundValidator",
    "OneLineValidator",
    "PIIValidator",
    "PiiKind",
    "Rails",
    "RegexMatchValidator",
    "Severity",
    "ValidJsonValidator",
    "ValidationResult",
    "Validator",
]
