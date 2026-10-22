"""Quickstart demonstration of the Guardrails capability.

Shows:
- Building a GuardrailPolicy with deterministic validators
- Running it and inspecting the decision and content-free reasons
- Input/output Rails
- PII detection without echoing content

Zero network calls in this example.
"""

from __future__ import annotations

import json

from guardrails.validators import (
    DenylistValidator,
    JsonSchemaValidator,
    OneLineValidator,
    ValidJsonValidator,
)

from guardrails import (
    GuardrailPolicy,
    LengthBoundValidator,
    PIIValidator,
    Rails,
)


def demo_basic() -> None:
    print("=" * 60)
    print("1. Basic output guardrail")
    print("=" * 60)

    policy = GuardrailPolicy(
        name="output",
        validators=(
            LengthBoundValidator(max_chars=200),
            ValidJsonValidator(),
            DenylistValidator(("secret", "password")),
            PIIValidator(),
        ),
    )

    good = json.dumps({"answer": "AI infrastructure is modular."})
    outcome = policy.check(good)
    print(f"  good output: decision={outcome.decision}, allowed={outcome.allowed}")

    bad = "Here is your secret: sk-abcdefghijklmnopqrstuvwxyz123456"
    outcome = policy.check(bad)
    print(f"  bad output: decision={outcome.decision}, allowed={outcome.allowed}")
    print(f"  reasons: {outcome.reasons}")


def demo_schema() -> None:
    print("\n" + "=" * 60)
    print("2. JSON schema guardrail")
    print("=" * 60)

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
        "additionalProperties": False,
    }
    policy = GuardrailPolicy(
        name="schema",
        validators=(JsonSchemaValidator(schema),),
    )
    outcome = policy.check(json.dumps({"name": "Alice", "age": 30}))
    print(f"  valid: decision={outcome.decision}")
    outcome = policy.check(json.dumps({"name": "Bob"}))
    print(f"  invalid: decision={outcome.decision}, reasons={outcome.reasons}")


def demo_rails() -> None:
    print("\n" + "=" * 60)
    print("3. Input/output rails")
    print("=" * 60)

    rails = Rails(
        input_policy=GuardrailPolicy(
            name="input",
            validators=(DenylistValidator(("jailbreak",)),),
        ),
        output_policy=GuardrailPolicy(
            name="output",
            validators=(OneLineValidator(),),
        ),
    )
    print(f"  input (clean): {rails.check_input('hello')}")
    print(f"  input (bad):   {rails.check_input('jailbreak now')}")
    print(f"  output (one line): {rails.check_output('single line')}")
    print(f"  output (multi):   {rails.check_output('line one\\nline two')}")


def demo_content_free() -> None:
    print("\n" + "=" * 60)
    print("4. Content-free reasons (PII not echoed)")
    print("=" * 60)

    policy = GuardrailPolicy(name="pii", validators=(PIIValidator(),))
    sample = "Contact alice@example.com or call 555-123-4567"
    outcome = policy.check(sample)
    print(f"  decision={outcome.decision}")
    for reason in outcome.reasons:
        assert "alice@example.com" not in reason
        assert "555-123-4567" not in reason
        print(f"  reason (content-free): {reason}")


if __name__ == "__main__":
    demo_basic()
    demo_schema()
    demo_rails()
    demo_content_free()
    print("\n" + "=" * 60)
    print("All demos completed successfully!")
    print("=" * 60)
