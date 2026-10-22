"""PII detection as a deterministic validator.

Patterns only — no model, no external service. Matched content is reported
by count and position only; the matched text is never echoed (leak-channel
invariant).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..protocols import Severity, ValidationResult

__all__ = ["PIIValidator", "PiiKind"]

# Patterns deliberately conservative: they prefer false negatives to false
# positives, and they never capture content into named groups that could be
# echoed. Every match is located by span, not by value.
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){7,}\d(?!\d)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "api_key": re.compile(
        r"\b(?:sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36})\b"
    ),
}


class PiiKind(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    API_KEY = "api_key"


@dataclass(frozen=True, slots=True)
class PIIValidator:
    """Detect personally identifiable information using fixed patterns.

    ``kinds`` selects which patterns run; defaults to all. ``credit_card``
    matches are additionally Luhn-checked so arbitrary digit runs do not trip.
    """

    kinds: tuple[PiiKind, ...] = field(default_factory=lambda: tuple(PiiKind))
    name: str = "pii"
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        if not self.kinds:
            raise ValueError("kinds must be non-empty")
        if any(not isinstance(k, PiiKind) for k in self.kinds):
            # allow string values for ergonomics
            try:
                normalised = tuple(PiiKind(k) for k in self.kinds)
            except ValueError as exc:
                raise ValueError(f"unknown pii kind: {exc}") from exc
            object.__setattr__(self, "kinds", normalised)
        else:
            object.__setattr__(self, "kinds", tuple(self.kinds))

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        findings: list[tuple[str, int, int]] = []
        for kind in self.kinds:
            pattern = _PII_PATTERNS[kind.value]
            for match in pattern.finditer(text):
                if kind is PiiKind.CREDIT_CARD and not _luhn(match.group(0)):
                    continue
                findings.append((kind.value, match.start(), match.end()))
        if not findings:
            return ValidationResult(
                validator=self.name,
                passed=True,
                severity=self.severity,
                metadata={"finding_count": 0},
            )
        by_kind: dict[str, int] = {}
        for kind_name, _, _ in findings:
            by_kind[kind_name] = by_kind.get(kind_name, 0) + 1
        summary = ", ".join(
            f"{kind}={count}" for kind, count in sorted(by_kind.items())
        )
        return ValidationResult(
            validator=self.name,
            passed=False,
            severity=self.severity,
            reason=f"pii detected: {summary}",
            metadata={
                "finding_count": len(findings),
                "by_kind": by_kind,
                "spans": tuple((start, end) for _, start, end in findings),
            },
        )


def _luhn(digits: str) -> bool:
    """Return True when ``digits`` (with separators) passes the Luhn check."""
    nums = [int(c) for c in digits if c.isdigit()]
    if len(nums) < 13:
        return False
    total = 0
    parity = len(nums) % 2
    for index, digit in enumerate(nums):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
