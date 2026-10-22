"""Tests for the policy, outcome and rails."""

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
from guardrails.validators import LengthBoundValidator  # noqa: E402

from guardrails import (  # noqa: E402
    GuardrailDecision,
    GuardrailPolicy,
    Rails,
    Severity,
    ValidationResult,
    Validator,
)


def _policy(
    *validators: Validator,
    on_error: GuardrailDecision = GuardrailDecision.REJECT,
    on_warning: GuardrailDecision = GuardrailDecision.FLAG,
) -> GuardrailPolicy:
    return GuardrailPolicy(
        name="p",
        validators=validators,
        on_error=on_error,
        on_warning=on_warning,
    )


def test_policy_pass() -> None:
    p = _policy(LengthBoundValidator(max_chars=10))
    outcome = p.check("hi")
    assert outcome.decision is GuardrailDecision.PASS
    assert outcome.allowed
    assert outcome.reasons == ()


def test_policy_reject() -> None:
    p = _policy(LengthBoundValidator(max_chars=2))
    outcome = p.check("too long")
    assert outcome.decision is GuardrailDecision.REJECT
    assert not outcome.allowed
    assert len(outcome.reasons) == 1


def test_policy_runs_all_validators() -> None:
    # chain cannot be skipped: both validators run even though first fails
    calls: list[str] = []

    class Counting:
        @property
        def name(self) -> str:
            return "counting"

        def validate(self, text: str) -> ValidationResult:
            calls.append(text)
            return ValidationResult(
                validator="counting", passed=False, reason="always fails"
            )

    p = _policy(Counting(), Counting())
    assert Counting().name == "counting"
    outcome = p.check("x")
    assert len(calls) == 2
    assert len(outcome.failures) == 2


def test_policy_warning_flag() -> None:
    p = _policy(
        LengthBoundValidator(max_chars=2, severity=Severity.WARNING),
        on_warning=GuardrailDecision.FLAG,
    )
    outcome = p.check("too long")
    assert outcome.decision is GuardrailDecision.FLAG
    assert outcome.allowed  # FLAG is not blocking


def test_policy_highest_decision_wins() -> None:
    p = GuardrailPolicy(
        name="p",
        validators=(
            LengthBoundValidator(max_chars=2, severity=Severity.WARNING),
            LengthBoundValidator(max_chars=2, severity=Severity.ERROR),
        ),
    )
    outcome = p.check("too long")
    assert outcome.decision is GuardrailDecision.REJECT


def test_policy_construction_errors() -> None:

    with pytest.raises(ValueError):
        GuardrailPolicy(name="", validators=(LengthBoundValidator(max_chars=1),))
    with pytest.raises(ValueError):
        GuardrailPolicy(name="p", validators=())
    with pytest.raises(ValueError):
        GuardrailPolicy(
            name="p",
            validators=(LengthBoundValidator(max_chars=1),),
            on_error=GuardrailDecision.PASS,
        )
    with pytest.raises(ValueError):
        GuardrailPolicy(
            name="p",
            validators=(LengthBoundValidator(max_chars=1),),
            on_warning=GuardrailDecision.REJECT,
        )


def test_rails() -> None:
    rails = Rails(
        input_policy=_policy(LengthBoundValidator(max_chars=5)),
        output_policy=_policy(LengthBoundValidator(max_chars=5)),
    )
    assert rails.check_input("hi") is not None
    _in = rails.check_input("hi")
    assert _in is not None and _in.allowed
    _in2 = rails.check_input("too long text")
    assert _in2 is not None and _in2.decision is GuardrailDecision.REJECT
    _out = rails.check_output("ok")
    assert _out is not None and _out.allowed


def test_rails_requires_one() -> None:

    with pytest.raises(ValueError):
        Rails()


def test_rails_optional_side() -> None:
    rails = Rails(output_policy=_policy(LengthBoundValidator(max_chars=5)))
    assert rails.check_input("anything") is None
    _out2 = rails.check_output("hi")
    assert _out2 is not None and _out2.allowed


def test_validation_result_invariants() -> None:

    with pytest.raises(ValueError):
        ValidationResult(validator="v", passed=True, reason="nope")
    with pytest.raises(ValueError):
        ValidationResult(validator="v", passed=False)
    with pytest.raises(ValueError):
        ValidationResult(validator="", passed=True)
    # passing without reason is fine
    assert ValidationResult(validator="v", passed=True).passed


def test_outcome_properties() -> None:
    p = _policy(LengthBoundValidator(max_chars=2))
    outcome = p.check("too long")
    assert outcome.failures
    assert outcome.reasons
    assert not outcome.allowed
