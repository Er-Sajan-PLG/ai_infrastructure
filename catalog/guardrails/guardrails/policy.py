"""Policy objects: turn a set of validators into one decision.

The policy is the composition point. It runs **every** validator it holds —
never short-circuiting on the first failure — so a caller sees all the reasons
at once and cannot accidentally skip part of the chain (specification
§Testing strategy, "a request through the composed path cannot skip the
validator chain").
"""

from __future__ import annotations

from dataclasses import dataclass

from .protocols import (
    GuardrailDecision,
    GuardrailOutcome,
    Severity,
    ValidationResult,
    Validator,
)

_DECISION_RANK: dict[GuardrailDecision, int] = {
    GuardrailDecision.PASS: 0,
    GuardrailDecision.FLAG: 1,
    GuardrailDecision.REJECT: 2,
}

_ERROR_DECISIONS: frozenset[GuardrailDecision] = frozenset(
    {GuardrailDecision.FLAG, GuardrailDecision.REJECT}
)
_WARNING_DECISIONS: frozenset[GuardrailDecision] = frozenset(
    {GuardrailDecision.PASS, GuardrailDecision.FLAG}
)


@dataclass(frozen=True, slots=True)
class GuardrailPolicy:
    """A named set of validators plus the decisions their failures imply.

    Attributes:
        name: Policy identifier, reported in the outcome.
        validators: The rules to run, in order. All of them run on every check.
        on_error: Decision for a failed ``ERROR`` validator. Must be ``FLAG``
            or ``REJECT`` — an error cannot silently pass.
        on_warning: Decision for a failed ``WARNING`` validator. Must be
            ``PASS`` or ``FLAG`` — a warning never blocks.
    """

    name: str
    validators: tuple[Validator, ...]
    on_error: GuardrailDecision = GuardrailDecision.REJECT
    on_warning: GuardrailDecision = GuardrailDecision.FLAG

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("policy name must be non-empty")
        if not self.validators:
            raise ValueError("a policy must hold at least one validator")
        if self.on_error not in _ERROR_DECISIONS:
            raise ValueError(
                f"on_error must be one of {sorted(_ERROR_DECISIONS)}, "
                f"got {self.on_error}"
            )
        if self.on_warning not in _WARNING_DECISIONS:
            raise ValueError(
                f"on_warning must be one of {sorted(_WARNING_DECISIONS)}, "
                f"got {self.on_warning}"
            )

    def check(self, text: str) -> GuardrailOutcome:
        """Run every validator and aggregate into one decision."""
        results = tuple(validator.validate(text) for validator in self.validators)
        return GuardrailOutcome(
            policy=self.name,
            decision=self._decide(results),
            results=results,
        )

    def _decide(self, results: tuple[ValidationResult, ...]) -> GuardrailDecision:
        decision = GuardrailDecision.PASS
        for result in results:
            if result.passed:
                continue
            implied = (
                self.on_error if result.severity is Severity.ERROR else self.on_warning
            )
            if _DECISION_RANK[implied] > _DECISION_RANK[decision]:
                decision = implied
        return decision


@dataclass(frozen=True, slots=True)
class Rails:
    """Input and output rails for one boundary.

    A rail is a policy applied on one side of the model: the input rail checks
    what goes *to* the model, the output rail checks what comes *back*. Either
    may be absent; at least one must be present, because a ``Rails`` with
    neither validates nothing.
    """

    input_policy: GuardrailPolicy | None = None
    output_policy: GuardrailPolicy | None = None

    def __post_init__(self) -> None:
        if self.input_policy is None and self.output_policy is None:
            raise ValueError("Rails needs at least one of input_policy/output_policy")

    def check_input(self, text: str) -> GuardrailOutcome | None:
        """Run the input rail, or ``None`` when no input rail is configured."""
        if self.input_policy is None:
            return None
        return self.input_policy.check(text)

    def check_output(self, text: str) -> GuardrailOutcome | None:
        """Run the output rail, or ``None`` when no output rail is configured."""
        if self.output_policy is None:
            return None
        return self.output_policy.check(text)
