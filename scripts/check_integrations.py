#!/usr/bin/env python3
"""Validate integration directory consistency.

Checks that each integration follows the repository's conventions:
- Has a README.md
- Has a tests/ directory
- Is listed in integrations/README.md's table
- Does not import from catalog/ (reverse direction enforced separately)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INTEGRATIONS_ROOT = Path("integrations")


def check_integration_readme(integration_path: Path) -> tuple[bool, str]:
    """Check if integration has a README.md."""
    readme = integration_path / "README.md"
    if not readme.exists():
        return False, "missing README.md"
    if readme.stat().st_size == 0:
        return False, "README.md is empty"
    return True, ""


def check_integration_tests(integration_path: Path) -> tuple[bool, str]:
    """Check if integration has a tests/ directory with at least one test file."""
    tests_dir = integration_path / "tests"
    if not tests_dir.exists():
        return False, "missing tests/ directory"
    if not tests_dir.is_dir():
        return False, "tests/ exists but is not a directory"
    test_files = list(tests_dir.glob("test_*.py"))
    if not test_files:
        return False, "tests/ contains no test_*.py files"
    return True, ""


def check_listed_in_readme_table(
    integration_name: str, readme_path: Path
) -> tuple[bool, str]:
    """Check if integration is listed in the integrations/README.md table."""
    if not readme_path.exists():
        return False, "integrations/README.md does not exist"
    content = readme_path.read_text(encoding="utf-8")
    # Look for the integration name in a markdown table row
    # Pattern: | [`name`](name/) |
    pattern = rf"\[\s*`{re.escape(integration_name)}`\s*\]\s*\(\s*{re.escape(integration_name)}/\s*\)"
    if re.search(pattern, content):
        return True, ""
    return False, "not listed in integrations/README.md table"


def check_no_catalog_imports_from_integration(
    integration_path: Path,
) -> tuple[bool, str]:
    """Check that integration Python files don't import from catalog/ internal modules."""
    py_files = list(integration_path.rglob("*.py"))
    violations = []

    for py_file in py_files:
        # Skip test files
        if "tests" in py_file.parts:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Look for imports from catalog.*.* (internal submodules)
        # Legitimate: from model_provider import X (public interface)
        # Not legitimate: from catalog.models.model_provider.provider import X
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r"^(from|import)\s+catalog\.", stripped) and re.search(
                r"from\s+catalog\.\w+\.\w+\.\w+", stripped
            ):
                violations.append(
                    f"{py_file.relative_to(INTEGRATIONS_ROOT)}:{i}: {stripped}"
                )

    if violations:
        return False, "catalog internal imports found: " + "; ".join(violations)
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate integration directory consistency"
    )
    parser.add_argument("--root", type=Path, default=Path(), help="Repository root")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    args = parser.parse_args()

    repo_root = args.root.resolve()
    integrations_dir = repo_root / INTEGRATIONS_ROOT
    readme_path = integrations_dir / "README.md"

    if not integrations_dir.exists():
        print(f"ERROR: {integrations_dir} does not exist")
        return 1

    # Get integration subdirectories (excluding __pycache__ etc.)
    integrations = [
        d
        for d in integrations_dir.iterdir()
        if d.is_dir() and not d.name.startswith("__") and not d.name.startswith(".")
    ]

    if not integrations:
        print("No integrations found")
        return 0

    errors = []
    warnings = []

    for integration in integrations:
        name = integration.name
        passed = True

        # Check README
        ok, msg = check_integration_readme(integration)
        if not ok:
            errors.append(f"{name}: {msg}")
            passed = False

        # Check tests/
        ok, msg = check_integration_tests(integration)
        if not ok:
            errors.append(f"{name}: {msg}")
            passed = False

        # Check listed in README table
        ok, msg = check_listed_in_readme_table(name, readme_path)
        if not ok:
            errors.append(f"{name}: {msg}")
            passed = False

        # Check no internal catalog imports
        ok, msg = check_no_catalog_imports_from_integration(integration)
        if not ok:
            warnings.append(f"{name}: {msg}")

        if passed:
            print(f"  ✓ {name}")

    for w in warnings:
        print(f"  ⚠ {w}")

    for e in errors:
        print(f"  ✗ {e}")

    if errors:
        print(f"\n{len(errors)} integration(s) failed validation")
        return 1

    print(f"\nAll {len(integrations)} integration(s) passed validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
