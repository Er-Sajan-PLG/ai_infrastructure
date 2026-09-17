"""Unit tests for study_pipeline.inventory — the structural map.

Every test builds a fixture repository on disk under `tmp_path` rather than
cloning. That is deliberate and load-bearing: unit tests must pass with the
network down, or `make check` becomes flaky for a reason unrelated to the code
under test. The one test that needs a real clone is marked `network` and
excluded from the default run.

The fixtures are SYNTHETIC repositories, so each test states exactly which
structural feature it is exercising. Several bugs in this module were found by
running it against a real repository after the synthetic tests passed — those
cases are kept as regression tests with the real shape that exposed them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from study_pipeline.inventory import (
    COUNTED_EXTENSIONS,
    MAX_FILES_WALKED,
    SKIP_DIRS,
    Inventory,
    Manifest,
    build_inventory,
)


def _write(root: Path, relative: str, content: str = "") -> Path:
    """Write a file, creating parent directories."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    """A small but conventionally-shaped Python project."""
    repo = tmp_path / "target"
    _write(repo, "pyproject.toml", '[project]\nname = "demo"\nversion = "1.0"\n')
    _write(repo, "src/demo/__init__.py")
    _write(repo, "src/demo/core.py", "x = 1\n")
    _write(repo, "src/demo/util.py", "y = 2\n")
    _write(repo, "tests/__init__.py")
    _write(repo, "tests/test_core.py", "def test_a(): pass\n")
    _write(repo, "tests/test_util.py", "def test_b(): pass\n")
    _write(repo, "README.md", "# demo\n")
    _write(repo, "LICENSE", "Apache-2.0\n")
    _write(repo, ".github/workflows/ci.yml", "name: ci\n")
    return repo


# ---------------------------------------------------------------------------
# Shape: counts, layout, language
# ---------------------------------------------------------------------------


def test_counts_files_and_bytes(python_repo: Path) -> None:
    inventory = build_inventory(python_repo)
    on_disk = [p for p in python_repo.rglob("*") if p.is_file()]
    assert inventory.total_files == len(on_disk)
    assert inventory.total_bytes == sum(p.stat().st_size for p in on_disk)


def test_counts_only_known_extensions(python_repo: Path) -> None:
    _write(python_repo, "notes.xyzzy", "ignored")
    inventory = build_inventory(python_repo)
    assert ".xyzzy" not in inventory.extension_counts
    assert all(ext in COUNTED_EXTENSIONS for ext in inventory.extension_counts)


def test_extension_counts_are_ordered_by_frequency(python_repo: Path) -> None:
    inventory = build_inventory(python_repo)
    counts = list(inventory.extension_counts.values())
    assert counts == sorted(counts, reverse=True)


def test_detects_primary_language(python_repo: Path) -> None:
    assert build_inventory(python_repo).primary_language == "Python"


def test_primary_language_ignores_documentation(tmp_path: Path) -> None:
    # A heavily documented Go project must not report as "Markdown".
    repo = tmp_path / "target"
    _write(repo, "main.go", "package main\n")
    for index in range(20):
        _write(repo, f"doc-{index}.md", "# docs\n")
    assert build_inventory(repo).primary_language == "Go"


def test_primary_language_is_unknown_without_code(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "README.md", "# docs only\n")
    assert build_inventory(repo).primary_language == "unknown"


def test_top_level_entries_are_listed(python_repo: Path) -> None:
    entries = build_inventory(python_repo).top_level_entries
    assert "pyproject.toml" in entries
    assert "src" in entries
    assert "tests" in entries


def test_a_non_directory_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "a-file"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        build_inventory(target)


# ---------------------------------------------------------------------------
# Skipping: the bug found by studying a real repository
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skipped", sorted(SKIP_DIRS))
def test_skip_dirs_are_excluded(tmp_path: Path, skipped: str) -> None:
    repo = tmp_path / "target"
    _write(repo, "keep.py", "x = 1\n")
    _write(repo, f"{skipped}/dep.py", "x = 2\n")
    inventory = build_inventory(repo)
    assert inventory.total_files == 1
    assert not any(skipped in d.split("/") for d in inventory.packages)


def test_dependency_cache_is_not_reported_as_packages(tmp_path: Path) -> None:
    """Regression: a real repository reported 4602 files instead of 214.

    This repository sets `UV_CACHE_DIR=.uv-cache/`, an extracted package cache
    with an `__init__.py` in every package. Studying itself before `.uv-cache`
    was in SKIP_DIRS listed 60+ third-party packages as if they were its own.
    """
    repo = tmp_path / "target"
    _write(repo, "src/mine/__init__.py")
    _write(repo, ".uv-cache/archive/requests/requests/__init__.py")
    _write(repo, ".uv-cache/archive/flask/flask/__init__.py")

    inventory = build_inventory(repo)
    assert inventory.packages == ("src/mine",)


def test_symlinks_are_never_followed(tmp_path: Path) -> None:
    # A studied repository can contain a symlink to `/` or to a large tree.
    # Following it would make the walk unbounded and misreport the size.
    repo = tmp_path / "target"
    _write(repo, "real.py", "x = 1\n")
    (repo / "loop").symlink_to(tmp_path)
    inventory = build_inventory(repo)
    assert inventory.total_files == 1


def test_unreadable_directory_does_not_abort_the_study(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "ok.py", "x = 1\n")
    locked = repo / "locked"
    locked.mkdir()
    _write(repo, "locked/hidden.py", "x = 2\n")
    locked.chmod(0o000)
    try:
        inventory = build_inventory(repo)
        # Either the file was counted (running as root) or skipped; both are
        # correct. What must not happen is an exception.
        assert inventory.total_files >= 1
    finally:
        locked.chmod(0o755)


# ---------------------------------------------------------------------------
# Packages and test layout
# ---------------------------------------------------------------------------


def test_detects_src_layout_package(python_repo: Path) -> None:
    assert "src/demo" in build_inventory(python_repo).packages


def test_detects_flat_layout_package(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "flatpkg/__init__.py")
    _write(repo, "flatpkg/mod.py", "x = 1\n")
    assert "flatpkg" in build_inventory(repo).packages


def test_test_directories_are_not_reported_as_packages(python_repo: Path) -> None:
    """Regression: from studying psf/requests.

    Its `tests/` carries an `__init__.py`, which made it importable — but it is
    not a package the project ships, and listing it misrepresents the surface.
    """
    inventory = build_inventory(python_repo)
    assert "tests" not in inventory.packages
    assert all("tests" not in pkg for pkg in inventory.packages)


def test_counts_test_files_and_directories(python_repo: Path) -> None:
    # Counts every file under a test directory, including its `__init__.py`:
    # this is a count of files in the test tree, not of test FUNCTIONS, which
    # would require parsing or running them (ADR-0021 forbids the latter).
    # The fixture has tests/__init__.py plus two test modules.
    inventory = build_inventory(python_repo)
    assert inventory.test_file_count == 3
    assert "tests" in inventory.test_dirs


def test_test_file_count_is_not_a_test_count(python_repo: Path) -> None:
    """The number is files in a test tree, never a claim about how many tests.

    Pinned as a test because the distinction is exactly the kind of thing a
    report writer would collapse: "212 test files" is defensible, "1,504 tests"
    is not, and only the second requires executing the project.
    """
    inventory = build_inventory(python_repo)
    # The fixture holds two test FUNCTIONS across three files in tests/.
    assert inventory.test_file_count == 3


@pytest.mark.parametrize("name", ["tests", "test", "testing", "spec"])
def test_recognises_each_conventional_test_directory(tmp_path: Path, name: str) -> None:
    repo = tmp_path / "target"
    _write(repo, f"{name}/test_x.py", "def test_x(): pass\n")
    assert build_inventory(repo).test_file_count == 1


def test_a_file_named_test_is_not_a_test_directory(tmp_path: Path) -> None:
    # `test_helpers.py` at the root is a source file, not evidence of a suite.
    repo = tmp_path / "target"
    _write(repo, "test_helpers.py", "x = 1\n")
    assert build_inventory(repo).test_file_count == 0


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------


def test_detects_marker_groups(python_repo: Path) -> None:
    markers = build_inventory(python_repo).markers
    assert "python-packaging" in markers
    assert "governance" in markers
    assert "ci-github" in markers
    assert "tests" in markers


def test_reports_which_marker_members_were_found(tmp_path: Path) -> None:
    # "has governance files" is much weaker evidence than naming them.
    repo = tmp_path / "target"
    _write(repo, "LICENSE")
    _write(repo, "SECURITY.md")
    found = build_inventory(repo).markers["governance"]
    assert "LICENSE" in found
    assert "SECURITY.md" in found
    assert "CONTRIBUTING.md" not in found


def test_absent_marker_groups_are_omitted(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "main.py", "x = 1\n")
    assert "containers" not in build_inventory(repo).markers


def test_detects_dockerfile_and_compose(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "Dockerfile")
    _write(repo, "compose.yaml")
    assert set(build_inventory(repo).markers["containers"]) == {
        "Dockerfile",
        "compose.yaml",
    }


# ---------------------------------------------------------------------------
# Manifests — parsed, never resolved
# ---------------------------------------------------------------------------


def test_parses_pyproject_project_dependencies(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname = "d"\nversion = "1"\ndependencies = ["requests>=2.31", "click"]\n',
    )
    inventory = build_inventory(repo)
    assert "requests>=2.31" in inventory.declared_dependencies
    assert "click" in inventory.declared_dependencies


def test_pyproject_extras_are_labelled(tmp_path: Path) -> None:
    # The distinction between shipping and development dependencies has to
    # survive into the report, or a reader assumes pytest ships.
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname = "d"\nversion = "1"\ndependencies = []\n'
        '[project.optional-dependencies]\ndev = ["pytest"]\n',
    )
    deps = build_inventory(repo).declared_dependencies
    assert "[extras] pytest" in deps


def test_parses_poetry_dependencies(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[tool.poetry]\nname = "d"\n'
        '[tool.poetry.dependencies]\npython = "^3.12"\nhttpx = "^0.27"\n',
    )
    deps = build_inventory(repo).declared_dependencies
    assert "httpx" in deps
    # The interpreter is not a dependency of the project in the sense a reader
    # assessing its surface cares about.
    assert "python" not in deps


def test_invalid_pyproject_is_reported_not_fatal(tmp_path: Path) -> None:
    # A malformed manifest is a finding about the project, not a crash.
    repo = tmp_path / "target"
    _write(repo, "pyproject.toml", "this is not [ valid toml")
    inventory = build_inventory(repo)
    manifest = inventory.manifests[0]
    assert manifest.error
    assert "invalid TOML" in manifest.error


def test_parses_requirements_txt(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "requirements.txt",
        "# a comment\n\nrequests>=2.31\nclick  # inline\n-r other.txt\n--index-url https://x\n",
    )
    deps = build_inventory(repo).declared_dependencies
    assert "requests>=2.31" in deps
    assert "click" in deps
    # Options and nested includes are not requirements and are not followed.
    assert not any(d.startswith("-") for d in deps)


def test_dev_requirements_are_labelled(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "requirements-dev.txt", "pytest\nruff\n")
    assert "[extras] pytest" in build_inventory(repo).declared_dependencies


def test_parses_package_json(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18"},
                "devDependencies": {"typescript": "^5"},
                "peerDependencies": {"react-dom": "^18"},
            }
        ),
    )
    deps = build_inventory(repo).declared_dependencies
    assert "react" in deps
    assert "[extras] typescript" in deps
    assert "[peer] react-dom" in deps


def test_invalid_package_json_is_reported_not_fatal(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "package.json", "{not json")
    manifest = build_inventory(repo).manifests[0]
    assert "invalid JSON" in manifest.error


def test_parses_cargo_toml(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "Cargo.toml",
        '[package]\nname = "d"\n[dependencies]\nserde = "1"\n[dev-dependencies]\ncriterion = "0.5"\n',
    )
    deps = build_inventory(repo).declared_dependencies
    assert "serde" in deps
    assert "[extras] criterion" in deps


def test_declared_dependencies_are_deduplicated(tmp_path: Path) -> None:
    # Reporting one package twice overstates the surface being assessed.
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname = "d"\nversion="1"\ndependencies = ["click"]\n',
    )
    _write(repo, "requirements.txt", "click\n")
    deps = build_inventory(repo).declared_dependencies
    assert deps.count("click") == 1


def test_nested_manifests_are_ignored(tmp_path: Path) -> None:
    # A manifest in examples/ describes the examples, not the project.
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname = "d"\nversion="1"\ndependencies = ["core"]\n',
    )
    _write(
        repo,
        "examples/pyproject.toml",
        '[project]\nname="e"\ndependencies=["example-only"]\n',
    )
    deps = build_inventory(repo).declared_dependencies
    assert "core" in deps
    assert "example-only" not in deps


# ---------------------------------------------------------------------------
# Determinism and dataclass contracts
# ---------------------------------------------------------------------------


def test_two_runs_agree(python_repo: Path) -> None:
    # A study report that changes between runs on the same commit is not
    # reproducible, and reproducibility is the point of pinning the commit.
    first = build_inventory(python_repo)
    second = build_inventory(python_repo)
    assert first == second


def test_inventory_is_frozen(python_repo: Path) -> None:
    import dataclasses

    inventory = build_inventory(python_repo)
    with pytest.raises(dataclasses.FrozenInstanceError):
        inventory.total_files = 0  # type: ignore[misc]


def test_truncation_is_reported_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import study_pipeline.inventory as inventory_module

    repo = tmp_path / "target"
    for index in range(10):
        _write(repo, f"f{index}.py", "x = 1\n")

    # A silently-truncated walk would produce numbers that look complete.
    monkeypatch.setattr(inventory_module, "MAX_FILES_WALKED", 3)
    inventory = inventory_module.build_inventory(repo)
    assert inventory.truncated
    assert inventory.notes
    assert "lower bound" in inventory.notes[0]


def test_max_files_walked_is_generous() -> None:
    assert MAX_FILES_WALKED >= 100_000


def test_inventory_declared_dependencies_is_a_property(python_repo: Path) -> None:
    inventory: Inventory = build_inventory(python_repo)
    assert isinstance(inventory.declared_dependencies, tuple)


def test_manifest_dataclass_holds_requirement_strings() -> None:
    manifest = Manifest(
        path="requirements.txt", kind="requirements", requirements=("a>=1",)
    )
    # Declared strings, never resolved versions (ADR-0021).
    assert manifest.requirements == ("a>=1",)
    assert manifest.error == ""


# ---------------------------------------------------------------------------
# Real clone (opt-in; never run in the default suite)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_studies_a_real_repository() -> None:
    """End-to-end against GitHub. Excluded by default so `make check` is offline.

    Run explicitly with: `pytest -m network study_pipeline/tests/`
    """
    from study_pipeline.inventory import build_inventory as build
    from study_pipeline.workspace import study_workspace

    with study_workspace("https://github.com/psf/requests") as clone:
        inventory = build(clone.path)
        assert inventory.total_files > 50
        assert inventory.primary_language == "Python"
        assert "src/requests" in inventory.packages
        # A test directory must never be reported as a shipped package.
        assert not any(pkg == "tests" for pkg in inventory.packages)
