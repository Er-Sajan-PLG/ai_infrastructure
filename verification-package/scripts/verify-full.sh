#!/usr/bin/env bash
#
# Full verification suite — the canonical entry point.
#
# Runs all core properties: format, lint, type, unit, integration, build,
# security, coverage. This is what CI runs. Developers run this before
# pushing to catch anything pre-push missed.
#
# Usage: ./scripts/verify-full.sh [property]
#   With no args: runs all properties.
#   With a property name: runs only that property (e.g., ./scripts/verify-full.sh lint)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PROPERTY="${1:-all}"

fail() {
    echo "" >&2
    echo "verify-full FAILED: $1" >&2
    exit 1
}

# --- Format ----------------------------------------------------------------
verify_format() {
    echo "verify-full: format"
    if [ -x ".venv/bin/black" ]; then
        .venv/bin/black --check . 2>/dev/null || fail "black would reformat"
    elif command -v black >/dev/null 2>&1; then
        black --check . 2>/dev/null || fail "black would reformat"
    fi
}

# --- Lint ------------------------------------------------------------------
verify_lint() {
    echo "verify-full: lint"
    if [ -x ".venv/bin/ruff" ]; then
        .venv/bin/ruff check . 2>/dev/null || fail "ruff found lint errors"
    elif command -v ruff >/dev/null 2>&1; then
        ruff check . 2>/dev/null || fail "ruff found lint errors"
    fi
}

# --- Typecheck -------------------------------------------------------------
verify_type() {
    echo "verify-full: typecheck"
    if [ -x ".venv/bin/mypy" ]; then
        .venv/bin/mypy . 2>/dev/null || fail "type errors"
    elif command -v mypy >/dev/null 2>&1; then
        mypy . 2>/dev/null || fail "type errors"
    fi
}

# --- Unit tests ------------------------------------------------------------
verify_unit() {
    echo "verify-full: unit tests"
    if [ -x ".venv/bin/pytest" ]; then
        .venv/bin/pytest -x -q --ignore=tests/integration --ignore=tests/e2e 2>/dev/null \
            || fail "unit tests failed"
    elif command -v pytest >/dev/null 2>&1; then
        pytest -x -q --ignore=tests/integration --ignore=tests/e2e 2>/dev/null \
            || fail "unit tests failed"
    fi
}

# --- Integration tests -----------------------------------------------------
verify_integration() {
    echo "verify-full: integration tests"
    if [ -x ".venv/bin/pytest" ]; then
        .venv/bin/pytest -x -q tests/integration 2>/dev/null || fail "integration tests failed"
    elif command -v pytest >/dev/null 2>&1; then
        pytest -x -q tests/integration 2>/dev/null || fail "integration tests failed"
    fi
}

# --- Build -----------------------------------------------------------------
verify_build() {
    echo "verify-full: build"
    if [ -f "pyproject.toml" ] && [ -x ".venv/bin/python" ]; then
        .venv/bin/python -m compileall -q . 2>/dev/null || fail "build failed"
    elif [ -f "package.json" ] && command -v npm >/dev/null 2>&1; then
        npm run build 2>/dev/null || fail "build failed"
    fi
}

# --- Security --------------------------------------------------------------
verify_security() {
    echo "verify-full: security"
    if command -v gitleaks >/dev/null 2>&1; then
        gitleaks git . --no-banner --redact --exit-code 1 2>/dev/null \
            || fail "gitleaks found secrets"
    fi
    if [ -x ".venv/bin/bandit" ]; then
        .venv/bin/bandit -r . -ll 2>/dev/null || fail "bandit found issues"
    elif command -v bandit >/dev/null 2>&1; then
        bandit -r . -ll 2>/dev/null || fail "bandit found issues"
    fi
}

# --- Coverage --------------------------------------------------------------
verify_coverage() {
    echo "verify-full: coverage"
    if [ -x ".venv/bin/pytest" ]; then
        .venv/bin/pytest --cov --cov-report=term-missing --cov-fail-under=80 -q 2>/dev/null \
            || fail "coverage below floor"
    elif command -v pytest >/dev/null 2>&1; then
        pytest --cov --cov-report=term-missing --cov-fail-under=80 -q 2>/dev/null \
            || fail "coverage below floor"
    fi
}

# --- Dispatch ---------------------------------------------------------------
case "$PROPERTY" in
    all)
        verify_format
        verify_lint
        verify_type
        verify_unit
        verify_integration
        verify_build
        verify_security
        verify_coverage
        ;;
    format)     verify_format ;;
    lint)       verify_lint ;;
    type)       verify_type ;;
    unit)       verify_unit ;;
    integration) verify_integration ;;
    build)      verify_build ;;
    security)   verify_security ;;
    coverage)   verify_coverage ;;
    *)
        echo "Unknown property: $PROPERTY" >&2
        echo "Available: all format lint type unit integration build security coverage" >&2
        exit 2
        ;;
esac

echo "verify-full: all checks passed."
exit 0
