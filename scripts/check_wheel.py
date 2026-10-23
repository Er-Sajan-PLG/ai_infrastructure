#!/usr/bin/env python3
"""Verify the built wheel contains only shippable artifacts.

Builds the wheel (via `python -m build --wheel`) into a temporary directory and
asserts:

  * the wheel exists
  * no ``__pycache__`` / ``*.pyc`` / ``*.pyo`` entries (packaging hygiene)
  * no test files or development-only artifacts
  * source modules and package metadata are present

Exit non-zero on any violation. Intended as a CI/release gate, not a
per-commit check (building is slow).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_SUFFIXES = (".pyc", ".pyo", ".pyd")
FORBIDDEN_NAMES = {"conftest.py"}


def check_names(names: list[str]) -> list[str]:
    """Return a list of violation descriptions for the given wheel entry names."""
    violations: list[str] = []
    for n in names:
        if any(n.endswith(s) for s in FORBIDDEN_SUFFIXES):
            violations.append(f"forbidden suffix: {n}")
        if "__pycache__" in n.split("/"):
            violations.append(f"pycache dir: {n}")
        if "/tests/" in n or "/test_" in n:
            violations.append(f"test artifact: {n}")
        if n.rsplit("/", 1)[-1] in FORBIDDEN_NAMES:
            violations.append(f"dev file: {n}")
    return violations


def validate_wheel(names: list[str]) -> int:
    """Validate a list of wheel entry names. Return 0 on success, 1 on failure."""
    violations = check_names(names)
    if violations:
        print("FAIL: wheel contains forbidden entries:")
        for v in violations:
            print(f"  - {v}")
        return 1

    py_sources = [n for n in names if n.endswith(".py")]
    metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
    if not py_sources:
        print("FAIL: wheel contains no Python sources")
        return 1
    if not metadata:
        print("FAIL: wheel contains no METADATA")
        return 1

    print(
        f"OK: {len(names)} entries, {len(py_sources)} .py sources, "
        f"{len(metadata)} metadata file(s); no pycache/pyc/test artifacts."
    )
    return 0


def _build(outdir: Path, runner: Any = subprocess.run) -> list[Path]:
    result = runner(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(outdir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return list(outdir.glob("*.whl"))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        outdir = Path(td)
        wheels = _build(outdir)
        if not wheels:
            print("FAIL: no wheel produced")
            return 1
        wheel = wheels[0]
        print(f"wheel: {wheel.name}")

        with zipfile.ZipFile(wheel) as z:
            names = z.namelist()

        return validate_wheel(names)


if __name__ == "__main__":
    sys.exit(main())
