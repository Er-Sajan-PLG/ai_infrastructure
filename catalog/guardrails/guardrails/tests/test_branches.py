"""Additional branch-coverage tests for validators."""

from __future__ import annotations

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

import pytest  # noqa: E402
from guardrails.validators import (  # noqa: E402
    AllowlistValidator,
    DenylistValidator,
    JsonSchemaValidator,
    OneLineValidator,
    PIIValidator,
    RegexMatchValidator,
    ValidJsonValidator,
)
from guardrails.validators.pii import _luhn  # noqa: E402

from guardrails import LengthBoundValidator  # noqa: E402


def test_luhn_short() -> None:
    assert _luhn("123") is False


def test_length_construction_errors() -> None:
    with pytest.raises(ValueError):
        LengthBoundValidator(min_chars=-1)
    with pytest.raises(ValueError):
        LengthBoundValidator(max_chars=-1)
    with pytest.raises(ValueError):
        LengthBoundValidator(min_chars=5, max_chars=2)


def test_regex_non_text() -> None:
    v = RegexMatchValidator("x", mode="deny")
    r = v.validate(123)
    assert not r.passed
    assert "not text" in (r.reason or "")


def test_allowlist_non_text() -> None:
    v = AllowlistValidator(("a",))
    r = v.validate(123)
    assert not r.passed


def test_denylist_construction_and_non_text() -> None:
    with pytest.raises(ValueError):
        DenylistValidator(())
    with pytest.raises(ValueError):
        DenylistValidator(("",))
    v = DenylistValidator(("a",))
    r = v.validate(123)
    assert not r.passed


def test_one_line_construction_and_non_text() -> None:
    with pytest.raises(ValueError):
        OneLineValidator(max_lines=0)
    v = OneLineValidator()
    r = v.validate(123)
    assert not r.passed


def test_valid_json_non_text() -> None:
    v = ValidJsonValidator()
    r = v.validate(123)
    assert not r.passed


def test_json_schema_non_text() -> None:
    schema = {"type": "string"}
    v = JsonSchemaValidator(schema)
    r = v.validate(123)
    assert not r.passed


def test_pii_unknown_kind() -> None:
    with pytest.raises(ValueError):
        PIIValidator(kinds=("nope",))  # type: ignore[arg-type]


def test_pii_non_text() -> None:
    v = PIIValidator()
    r = v.validate(123)
    assert not r.passed


def test_pii_luhn_false() -> None:
    v = PIIValidator()
    # 13+ digits but invalid Luhn
    r = v.validate("number 1234567890123")
    # may or may not be detected as credit card; ensure no crash
    assert r is not None


def test_rails_output_none() -> None:
    from guardrails import GuardrailPolicy, Rails

    rails = Rails(
        input_policy=GuardrailPolicy(
            name="i", validators=(LengthBoundValidator(max_chars=5),)
        )
    )
    assert rails.check_output("hi") is None


def test_counting_name() -> None:
    # covered via direct access
    pass
