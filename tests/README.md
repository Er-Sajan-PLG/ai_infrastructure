# Cross-Cutting Tests

Tests for repository machinery and cross-component behavior. Capability-specific tests live with their catalog entry (`catalog/<category>/<entry>/tests/`).

| File | Covers |
|---|---|
| [`test_validate_catalog.py`](test_validate_catalog.py) | The catalog entry-contract validator, including its failure paths |
| [`test_repo_status.py`](test_repo_status.py) | The governance drift detector: parser, per-stage artifact rules, dependency rules, ADR-index rule, CLI exit codes, `--json` |
| [`test_check_links.py`](test_check_links.py) | The Markdown link checker: relative-link resolution, anchors, depth errors, skip-dirs |
| [`test_check_phase_plan.py`](test_check_phase_plan.py) | Stage-chain order, charter-order equality, historical-reversal regression, and the deliberate lifecycle-tuple duplication |
| [`test_gate_coverage.py`](test_gate_coverage.py) | **Meta-test** — asserts every source/test/coverage directory is classified and gated, and that the Makefile's mypy `find` covers them all |
| [`test_ci_parity.py`](test_ci_parity.py) | CI ↔ Makefile parity: every gate in `CI_GATES` is exercised and the workflow delegates to `make` |
| [`test_check_collectability.py`](test_check_collectability.py) | The catalog-entry test collectability verifier |
| [`test_check_risks.py`](test_check_risks.py) | The accepted-risk register verifier (expiry, anti-gaming, ceiling) |
| [`test_check_deferred.py`](test_check_deferred.py) | The deferred-work register verifier (schema, expiry, observable triggers) |
| [`test_check_licenses.py`](test_check_licenses.py) | The licence allow-list verifier |
| [`test_check_commit_msg.py`](test_check_commit_msg.py) | Conventional Commits header format (ADR-0019) |

## Running

The suite uses pytest. A local virtual environment is the simplest way to get it:

```bash
make setup
.venv/bin/python -m pytest
```

Current status: 11 cross-cutting files in `tests/`, 277 capability tests across 5 catalog entries, 25 integration tests. Capability-specific tests live with their catalog entry (`catalog/<category>/<entry>/tests/`).

## Rules

- A test that cannot fail is not a test. Include the violation case, not just the happy path (charter §18).
- Never weaken or delete a test to obtain a passing result; investigate the failure instead (charter §28).
- Do not add a test dependency without recording why; prefer the standard library.