# Cross-Cutting Tests

Tests for repository machinery and cross-component behavior. Capability-specific tests live with their catalog entry (`catalog/<category>/<entry>/tests/`).

| File | Covers |
|---|---|
| [`test_validate_catalog.py`](test_validate_catalog.py) | The catalog entry-contract validator, including its failure paths |

## Running

The suite uses pytest. A local virtual environment is the simplest way to get it:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q
```

Current status: **11 passed** (verified in a local venv on Python 3.14).

## Rules

- A test that cannot fail is not a test. Include the violation case, not just the happy path (charter §18).
- Never weaken or delete a test to obtain a passing result; investigate the failure instead (charter §28).
- Do not add a test dependency without recording why; prefer the standard library.