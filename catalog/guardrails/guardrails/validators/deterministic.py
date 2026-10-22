"""Deterministic output validators.

Every check here is a pure function of its input — no model call, no network,
no hidden state. Each returns a ``ValidationResult`` whose ``reason`` names the
rule and a count or position, never the rejected content.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from tool_registry.schema import check_schema, validate_arguments

from ..protocols import Severity, ValidationResult

__all__ = [
    "AllowlistValidator",
    "DenylistValidator",
    "JsonSchemaValidator",
    "LengthBoundValidator",
    "OneLineValidator",
    "RegexMatchValidator",
    "ValidJsonValidator",
]


@dataclass(frozen=True, slots=True)
class LengthBoundValidator:
    """Check the character length of an output against inclusive bounds.

    Either bound may be ``None`` (unbounded on that side). At least one must
    be set.
    """

    name: str = "length_bound"
    min_chars: int | None = None
    max_chars: int | None = None
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        if self.min_chars is None and self.max_chars is None:
            raise ValueError("LengthBoundValidator needs at least one bound")
        if self.min_chars is not None and self.min_chars < 0:
            raise ValueError("min_chars must be non-negative")
        if self.max_chars is not None and self.max_chars < 0:
            raise ValueError("max_chars must be non-negative")
        if (
            self.min_chars is not None
            and self.max_chars is not None
            and self.min_chars > self.max_chars
        ):
            raise ValueError("min_chars must not exceed max_chars")

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        length = len(text)
        if self.min_chars is not None and length < self.min_chars:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"length {length} below minimum {self.min_chars}",
                metadata={"length": length, "min_chars": self.min_chars},
            )
        if self.max_chars is not None and length > self.max_chars:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"length {length} above maximum {self.max_chars}",
                metadata={"length": length, "max_chars": self.max_chars},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
            metadata={"length": length},
        )


@dataclass(frozen=True, slots=True)
class RegexMatchValidator:
    """Match an output against a regular expression.

    ``mode="deny"`` fails when the pattern matches (use for forbidden
    content). ``mode="allow"`` fails when the pattern does *not* match (use for
    required shapes).

    The pattern is caller-supplied configuration and is trusted as such. It is
    compiled eagerly so a malformed pattern fails at construction rather than at
    validation time. Use fixed, audited patterns for hostile inputs.
    """

    pattern: str
    mode: str = "deny"
    name: str = "regex_match"
    severity: Severity = Severity.ERROR
    _compiled: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in {"deny", "allow"}:
            raise ValueError(f"mode must be 'deny' or 'allow', got {self.mode!r}")
        try:
            compiled = re.compile(self.pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}") from exc
        object.__setattr__(self, "_compiled", compiled)

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        matched = self._compiled.search(text) is not None
        count = len(self._compiled.findall(text))
        if self.mode == "deny":
            if matched:
                return ValidationResult(
                    validator=self.name,
                    passed=False,
                    severity=self.severity,
                    reason=f"pattern matched {count} time(s)",
                    metadata={"mode": self.mode, "match_count": count},
                )
            return ValidationResult(
                validator=self.name,
                passed=True,
                severity=self.severity,
                metadata={"mode": self.mode, "match_count": 0},
            )
        # allow
        if not matched:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason="pattern did not match",
                metadata={"mode": self.mode, "match_count": 0},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
            metadata={"mode": self.mode, "match_count": count},
        )


@dataclass(frozen=True, slots=True)
class AllowlistValidator:
    """Pass only when the output contains at least one allowlisted term.

    ``terms`` is a non-empty list of non-empty strings.
    """

    terms: tuple[str, ...]
    case_sensitive: bool = False
    name: str = "allowlist"
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("terms must be non-empty")
        if any(not isinstance(term, str) or not term for term in self.terms):
            raise ValueError("terms must be non-empty strings")
        object.__setattr__(self, "terms", tuple(self.terms))

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        haystack = text if self.case_sensitive else text.lower()
        needles = (
            self.terms if self.case_sensitive else tuple(t.lower() for t in self.terms)
        )
        found = any(needle in haystack for needle in needles)
        if found:
            return ValidationResult(
                validator=self.name,
                passed=True,
                severity=self.severity,
                metadata={"term_count": len(self.terms)},
            )
        return ValidationResult(
            validator=self.name,
            passed=False,
            severity=self.severity,
            reason=f"no allowlisted term present ({len(self.terms)} configured)",
            metadata={"term_count": len(self.terms)},
        )


@dataclass(frozen=True, slots=True)
class DenylistValidator:
    """Fail when the output contains any denylisted term.

    The matched *configured term* may be named in the reason — it is
    configuration, not model content — but the surrounding text is never echoed.
    """

    terms: tuple[str, ...]
    case_sensitive: bool = False
    name: str = "denylist"
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("terms must be non-empty")
        if any(not isinstance(term, str) or not term for term in self.terms):
            raise ValueError("terms must be non-empty strings")
        object.__setattr__(self, "terms", tuple(self.terms))

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        haystack = text if self.case_sensitive else text.lower()
        needles = (
            self.terms if self.case_sensitive else tuple(t.lower() for t in self.terms)
        )
        hits = [
            term
            for term, needle in zip(self.terms, needles, strict=True)
            if needle in haystack
        ]
        if hits:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"denylisted term present: {hits[0]!r}",
                metadata={"matched_terms": tuple(hits)},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
            metadata={"term_count": len(self.terms)},
        )


@dataclass(frozen=True, slots=True)
class OneLineValidator:
    """Fail when the output spans more than ``max_lines`` lines."""

    max_lines: int = 1
    name: str = "one_line"
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        if self.max_lines < 1:
            raise ValueError("max_lines must be at least 1")

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        if line_count > self.max_lines:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output spans {line_count} lines, maximum is {self.max_lines}",
                metadata={"line_count": line_count, "max_lines": self.max_lines},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
            metadata={"line_count": line_count, "max_lines": self.max_lines},
        )


@dataclass(frozen=True, slots=True)
class ValidJsonValidator:
    """Fail when the output is not parseable JSON.

    The reason reports the parser's static message and position — never the
    offending content.
    """

    name: str = "valid_json"
    severity: Severity = Severity.ERROR

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not valid JSON: {exc.msg} "
                f"at line {exc.lineno} column {exc.colno}",
                metadata={"lineno": exc.lineno, "colno": exc.colno},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
        )


@dataclass(frozen=True, slots=True)
class JsonSchemaValidator:
    """Validate a JSON-encoded output against a supported-subset JSON Schema.

    The schema is checked at construction (``check_schema``) so an unsupported
    keyword fails loudly rather than being silently ignored. The output is
    parsed as JSON first; a non-JSON output is rejected with a content-free
    reason before any schema check runs.
    """

    schema: Mapping[str, Any]
    name: str = "json_schema"
    severity: Severity = Severity.ERROR

    def __post_init__(self) -> None:
        check_schema(self.schema, where=f"{self.name} schema")
        object.__setattr__(self, "schema", dict(self.schema))

    def validate(self, text: Any) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not text (got {type(text).__name__})",
            )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"output is not valid JSON: {exc.msg} "
                f"at line {exc.lineno} column {exc.colno}",
                metadata={"lineno": exc.lineno, "colno": exc.colno},
            )
        problems = validate_arguments(self.schema, parsed)
        if problems:
            return ValidationResult(
                validator=self.name,
                passed=False,
                severity=self.severity,
                reason=f"{len(problems)} schema problem(s): "
                + "; ".join(str(p) for p in problems),
                metadata={"problem_count": len(problems)},
            )
        return ValidationResult(
            validator=self.name,
            passed=True,
            severity=self.severity,
        )
