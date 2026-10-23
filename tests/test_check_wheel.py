"""Unit tests for scripts/check_wheel.py."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import subprocess  # noqa: E402

import pytest  # noqa: E402

import check_wheel  # noqa: E402
from check_wheel import check_names, main, validate_wheel  # noqa: E402


def test_check_names_clean() -> None:
    names = [
        "catalog/tools/tool_registry/__init__.py",
        "ai_infrastructure/__init__.py",
        "foo.dist-info/METADATA",
    ]
    assert check_names(names) == []


def test_check_names_pyc() -> None:
    v = check_names(["foo/__pycache__/bar.pyc"])
    assert any("pycache" in x or "forbidden suffix" in x for x in v)


def test_check_names_test_artifact() -> None:
    v = check_names(["catalog/tools/tool_registry/tests/test_tool_registry.py"])
    assert any("test artifact" in x for x in v)


def test_check_names_conftest() -> None:
    v = check_names(["conftest.py"])
    assert any("dev file" in x for x in v)


def test_validate_wheel_clean() -> None:
    names = ["a.py", "foo.dist-info/METADATA"]
    assert validate_wheel(names) == 0


def test_validate_wheel_forbidden() -> None:
    names = ["foo.pyc"]
    assert validate_wheel(names) == 1


def test_validate_wheel_no_sources() -> None:
    names = ["foo.dist-info/METADATA"]
    assert validate_wheel(names) == 1


def test_validate_wheel_no_metadata() -> None:
    names = ["a.py"]
    assert validate_wheel(names) == 1


def test_main_builds_clean_wheel() -> None:
    assert main() == 0


def test_build_failure_surfaces_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    from typing import ClassVar

    class _R:
        returncode: ClassVar[int] = 1
        stdout: ClassVar[str] = "out"
        stderr: ClassVar[str] = "err"
        args: ClassVar[list[str]] = ["x"]

    def _runner(*a: object, **k: object) -> _R:
        return _R()

    with pytest.raises(subprocess.CalledProcessError):
        check_wheel._build(Path("/tmp"), runner=_runner)


def test_main_no_wheel_produced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_wheel, "_build", lambda outdir: [])
    assert check_wheel.main() == 1
