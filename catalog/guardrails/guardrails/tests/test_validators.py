"""Tests for the deterministic validators."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pathlib import Path as _Path

_catalog_root = _Path(__file__).resolve().parents[3]
for _cat in (
    "tools",
    "models",
    "agents",
    "observability",
    "protocols",
    "deployment",
    "memory",
    "retrieval",
    "evaluation",
    "guardrails",
):
    _p = str(_catalog_root / _cat)
    sys.path.insert(0, _p)

from guardrails.validators import (  # noqa: E402
    AllowlistValidator,
    DenylistValidator,
    JsonSchemaValidator,
    OneLineValidator,
    PIIValidator,
    RegexMatchValidator,
    ValidJsonValidator,
)
from tool_registry.errors import InvalidSchemaError  # noqa: E402

from guardrails import LengthBoundValidator, Severity  # noqa: E402


def test_length_pass_and_fail() -> None:
    v = LengthBoundValidator(min_chars=3, max_chars=5)
    assert v.validate("abc").passed
    assert not v.validate("ab").passed
    assert not v.validate("abcdef").passed
    assert "below minimum" in (v.validate("ab").reason or "")
    assert "above maximum" in (v.validate("abcdef").reason or "")


def test_length_requires_bound() -> None:
    import pytest

    with pytest.raises(ValueError):
        LengthBoundValidator()


def test_length_non_text() -> None:
    v = LengthBoundValidator(max_chars=5)
    r = v.validate(123)
    assert not r.passed
    assert "not text" in (r.reason or "")


def test_regex_deny() -> None:
    v = RegexMatchValidator(r"\d{3}-\d{2}-\d{4}", mode="deny")
    r = v.validate("ssn 123-45-6789 here")
    assert not r.passed
    assert r.metadata["match_count"] == 1
    clean = v.validate("no ssn here")
    assert clean.passed
    assert clean.metadata["match_count"] == 0


def test_regex_allow() -> None:
    v = RegexMatchValidator(r"^\d+$", mode="allow")
    assert v.validate("42").passed
    r = v.validate("not a number")
    assert not r.passed
    assert "did not match" in (r.reason or "")


def test_regex_invalid_mode_and_pattern() -> None:
    import pytest

    with pytest.raises(ValueError):
        RegexMatchValidator("x", mode="maybe")
    with pytest.raises(ValueError):
        RegexMatchValidator("[unclosed")


def test_regex_reason_does_not_echo_match() -> None:
    v = RegexMatchValidator(r"secret-\d+", mode="deny")
    r = v.validate("the value is secret-42")
    assert r.reason is not None
    assert "secret-42" not in (r.reason or "")


def test_allowlist() -> None:
    v = AllowlistValidator(("apple", "banana"))
    assert v.validate("I like apple pie").passed
    r = v.validate("I like cherry")
    assert not r.passed
    assert "no allowlisted term" in (r.reason or "")


def test_allowlist_case_insensitive() -> None:
    v = AllowlistValidator(("Apple",), case_sensitive=False)
    assert v.validate("APPLE pie").passed
    v2 = AllowlistValidator(("Apple",), case_sensitive=True)
    assert not v2.validate("APPLE pie").passed


def test_allowlist_construction() -> None:
    import pytest

    with pytest.raises(ValueError):
        AllowlistValidator(())
    with pytest.raises(ValueError):
        AllowlistValidator(("",))


def test_denylist() -> None:
    v = DenylistValidator(("secret", "password"))
    r = v.validate("my secret value")
    assert not r.passed
    assert "secret" in (r.reason or "")  # configured term may be named
    assert v.validate("nothing here").passed


def test_denylist_case_insensitive() -> None:
    v = DenylistValidator(("Secret",), case_sensitive=False)
    r = v.validate("MY SECRET")
    assert not r.passed


def test_one_line() -> None:
    v = OneLineValidator()
    assert v.validate("single line").passed
    assert v.validate("").passed
    r = v.validate("line one\nline two")
    assert not r.passed
    assert "spans 2 lines" in (r.reason or "")
    v2 = OneLineValidator(max_lines=2)
    assert v2.validate("a\nb").passed


def test_valid_json() -> None:
    v = ValidJsonValidator()
    assert v.validate('{"a": 1}').passed
    r = v.validate("{not json}")
    assert not r.passed
    assert "not valid JSON" in (r.reason or "")
    # position only, no content
    assert "not json" not in (r.reason or "")


def test_json_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
        "additionalProperties": False,
    }
    v = JsonSchemaValidator(schema)
    assert v.validate(json.dumps({"name": "Alice", "age": 30})).passed
    r = v.validate(json.dumps({"name": "Bob"}))
    assert not r.passed
    assert "schema problem" in (r.reason or "")
    r2 = v.validate("not json")
    assert not r2.passed
    assert "not valid JSON" in (r2.reason or "")


def test_json_schema_rejects_unsupported_keyword() -> None:
    import pytest

    with pytest.raises(InvalidSchemaError):
        JsonSchemaValidator({"type": "string", "minLength": 1})


def test_pii_email_phone_ssn() -> None:
    v = PIIValidator()
    r = v.validate("email me at alice@example.com")
    assert not r.passed
    assert "email=1" in (r.reason or "")
    assert "alice@example.com" not in (r.reason or "")
    r2 = v.validate("no pii here")
    assert r2.passed


def test_pii_credit_card_luhn() -> None:
    v = PIIValidator(kinds=(__import__("guardrails").PiiKind.CREDIT_CARD,))
    # valid Luhn number
    r = v.validate("card 4111111111111111")
    assert not r.passed
    # invalid Luhn run should not trip
    r2 = v.validate("number 1234567890123456")
    assert r2.passed


def test_pii_api_key() -> None:
    v = PIIValidator()
    r = v.validate("key sk-abcdefghijklmnopqrstuvwxyz0123456789")
    assert not r.passed
    assert "api_key=1" in (r.reason or "")


def test_pii_spans_metadata() -> None:
    v = PIIValidator()
    r = v.validate("a@b.com and c@d.com")
    assert r.metadata["finding_count"] == 2
    assert len(r.metadata["spans"]) == 2


def test_pii_kinds_validation() -> None:
    import pytest

    with pytest.raises(ValueError):
        PIIValidator(kinds=())
    # string coercion
    v = PIIValidator(kinds=("email",))  # type: ignore[arg-type]
    assert not v.validate("x@y.com").passed


def test_severity_override() -> None:
    v = LengthBoundValidator(max_chars=3, severity=Severity.WARNING)
    r = v.validate("too long here")
    assert not r.passed
    assert r.severity is Severity.WARNING
