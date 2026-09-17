"""Unit tests for study_pipeline.patterns — candidate pattern extraction.

The module's central risk is not crashing; it is being **confidently wrong**. A
detector that reports a CI pipeline as an agent orchestration loop produces a
study report that reads as authoritative and is incorrect, which is worse than
reporting nothing.

So the tests are organised around false positives as much as true ones:

  * the three false positives found by running this against a repository whose
    shape was known (`.github/workflows/`, `.import_linter_cache/`, and test
    trees) are regression tests with the real paths that exposed them;
  * confidence is asserted to correspond to evidence, because the labels are
    what a reader trusts;
  * the limitations text is asserted to be non-empty, because a detector that
    cannot say what it fails to see invites over-trust.

Fixtures are synthetic repositories built on disk, so the tests state exactly
which structural feature each one exercises and `make check` stays offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from study_pipeline.inventory import Inventory, Manifest, build_inventory
from study_pipeline.patterns import (
    MAX_EVIDENCE_PATHS,
    Confidence,
    _directory_has_modules,
    _manifest_matches,
    _matching_directories,
    _requirement_name,
    extract_candidates,
    slugify,
    summarise,
)


def _write(root: Path, relative: str, content: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _inventory(**overrides: object) -> Inventory:
    """A minimal Inventory with sensible defaults, for pure-function tests."""
    defaults: dict[str, object] = {
        "total_files": 1,
        "total_bytes": 1,
        "extension_counts": {".py": 1},
        "top_level_entries": (),
        "directories": (),
        "packages": (),
        "test_dirs": (),
        "test_file_count": 0,
        "markers": {},
        "manifests": (),
        "truncated": False,
        "notes": (),
    }
    defaults.update(overrides)
    return Inventory(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Discovered patterns
# ---------------------------------------------------------------------------


def test_finds_a_retrieval_directory(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "src/pkg/retrieval/__init__.py")
    _write(repo, "src/pkg/retrieval/index.py", "x = 1\n")
    candidates = extract_candidates(build_inventory(repo))
    assert "retrieval" in {c.pattern_id for c in candidates}


def test_finds_a_tool_registry_directory(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    candidates = extract_candidates(build_inventory(repo))
    assert "tool-registry" in {c.pattern_id for c in candidates}


def test_finds_nothing_in_an_empty_repository(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "README.md", "# nothing\n")
    assert extract_candidates(build_inventory(repo)) == ()


def test_manifest_dependency_is_evidence_on_its_own(tmp_path: Path) -> None:
    # A project can have no `retrieval/` directory and still be doing retrieval
    # through a library; the declared dependency is real evidence.
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname = "d"\nversion = "1"\ndependencies = ["faiss-cpu"]\n',
    )
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert "retrieval" in candidates
    assert any("faiss" in path for path in candidates["retrieval"].evidence_paths)


def test_no_evidence_means_no_candidate(tmp_path: Path) -> None:
    # A candidate with no evidence path would be an unfalsifiable assertion.
    repo = tmp_path / "target"
    _write(repo, "src/pkg/main.py", "x = 1\n")
    for candidate in extract_candidates(build_inventory(repo)):
        assert candidate.evidence_paths


# ---------------------------------------------------------------------------
# False positives — the regression tests that matter most
# ---------------------------------------------------------------------------


def test_ci_workflows_are_not_an_agent_loop(tmp_path: Path) -> None:
    """Regression: `.github/workflows/` matched the agent-loop rule.

    Found by running the extractor against a repository whose shape was known.
    The fragment "workflow" matched the CI directory, so a project with a
    GitHub Actions pipeline reported as having an orchestration loop.
    """
    repo = tmp_path / "target"
    _write(repo, ".github/workflows/ci.yml", "name: ci\n")
    candidates = {c.pattern_id for c in extract_candidates(build_inventory(repo))}
    assert "agent-loop" not in candidates


def test_cache_directories_of_tooling_are_not_caching_layers(tmp_path: Path) -> None:
    """Regression: `.import_linter_cache/` reported as a caching layer.

    A tool's own scratch directory is not a design decision by the project.
    """
    repo = tmp_path / "target"
    _write(repo, ".import_linter_cache/x.json", "{}\n")
    candidates = {c.pattern_id for c in extract_candidates(build_inventory(repo))}
    assert "caching" not in candidates


def test_documentation_trees_are_not_subsystems(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "docs/retrieval/guide.md", "# guide\n")
    _write(repo, "examples/caching/demo.py", "x = 1\n")
    candidates = {c.pattern_id for c in extract_candidates(build_inventory(repo))}
    assert "retrieval" not in candidates
    assert "caching" not in candidates


def test_test_trees_are_not_subsystems(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "tests/retrieval/test_index.py", "def test_x(): pass\n")
    candidates = {c.pattern_id for c in extract_candidates(build_inventory(repo))}
    assert "retrieval" not in candidates


def test_vendored_code_is_not_the_projects_design(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "vendor/otherlib/tools/__init__.py")
    candidates = {c.pattern_id for c in extract_candidates(build_inventory(repo))}
    assert "tool-registry" not in candidates


@pytest.mark.parametrize(
    "directory",
    [
        ".github/workflows",
        ".gitlab",
        ".import_linter_cache",
        "htmlcov",
        "node_modules/pkg/tools",
        "dist/pkg",
    ],
)
def test_infrastructure_directories_never_match(tmp_path: Path, directory: str) -> None:
    repo = tmp_path / "target"
    _write(repo, f"{directory}/thing.py", "x = 1\n")
    assert extract_candidates(build_inventory(repo)) == ()


# ---------------------------------------------------------------------------
# Confidence corresponds to evidence
# ---------------------------------------------------------------------------


def test_two_module_directories_is_strong(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "src/pkg/retrieval/__init__.py")
    _write(repo, "src/pkg/retrieval/index.py", "x = 1\n")
    _write(repo, "src/other/retrieval/__init__.py")
    _write(repo, "src/other/retrieval/store.py", "x = 1\n")
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert candidates["retrieval"].confidence is Confidence.STRONG


def test_directory_plus_manifest_is_strong(tmp_path: Path) -> None:
    # Two independent evidence sources is the definition used, and it is
    # statable in one sentence so a reader can audit the rating.
    repo = tmp_path / "target"
    _write(repo, "src/pkg/retrieval/__init__.py")
    _write(repo, "src/pkg/retrieval/index.py", "x = 1\n")
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname="d"\nversion="1"\ndependencies=["faiss-cpu"]\n',
    )
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert candidates["retrieval"].confidence is Confidence.STRONG


def test_bare_directory_name_is_weak(tmp_path: Path) -> None:
    # An empty directory named `memory/` is a naming convention, not machinery,
    # and the report must not present it as a finding.
    repo = tmp_path / "target"
    (repo / "memory").mkdir(parents=True)
    _write(repo, "keep.py", "x = 1\n")
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert candidates["memory"].confidence is Confidence.WEAK


def test_manifest_only_evidence_is_moderate(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(
        repo,
        "pyproject.toml",
        '[project]\nname="d"\nversion="1"\ndependencies=["chromadb"]\n',
    )
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert candidates["retrieval"].confidence is Confidence.MODERATE


def test_strong_candidates_are_ordered_first(tmp_path: Path) -> None:
    # A reader has limited attention; the most defensible findings go first.
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    _write(repo, "src/pkg/memory/__init__.py")
    _write(repo, "src/pkg/memory/store.py", "x = 1\n")
    (repo / "caching").mkdir(parents=True)

    candidates = extract_candidates(build_inventory(repo))
    order = {Confidence.STRONG: 0, Confidence.MODERATE: 1, Confidence.WEAK: 2}
    ranks = [order[c.confidence] for c in candidates]
    assert ranks == sorted(ranks)


def test_every_candidate_states_its_limitations(tmp_path: Path) -> None:
    # A detector that cannot say what it fails to see invites over-trust.
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    _write(repo, "src/pkg/memory/__init__.py")
    for candidate in extract_candidates(build_inventory(repo)):
        assert len(candidate.limitations) > 40, candidate.pattern_id


def test_candidate_categories_are_non_empty(tmp_path: Path) -> None:
    # The pattern module does NOT validate categories against the taxonomy --
    # that is the classifier's job, because only it reads TAXONOMY.md. This
    # module was briefly carrying a hardcoded category set and it was wrong in
    # both directions (omitted `mcp`, invented `performance`/`reliability`).
    # See test_classify.py for the check that consults the real file.
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    for candidate in extract_candidates(build_inventory(repo)):
        assert candidate.category, candidate.pattern_id
        assert candidate.category == candidate.category.lower()


def test_evidence_paths_are_capped(tmp_path: Path) -> None:
    # An unbounded evidence list would swamp a report for a large project.
    repo = tmp_path / "target"
    for index in range(20):
        _write(repo, f"src/p{index}/tools/__init__.py")
    candidates = {c.pattern_id: c for c in extract_candidates(build_inventory(repo))}
    assert len(candidates["tool-registry"].evidence_paths) <= MAX_EVIDENCE_PATHS


# ---------------------------------------------------------------------------
# Summaries and determinism
# ---------------------------------------------------------------------------


def test_summarise_counts_every_confidence_band(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    counts = summarise(extract_candidates(build_inventory(repo)))
    assert set(counts) == {c.value for c in Confidence}
    assert sum(counts.values()) == len(extract_candidates(build_inventory(repo)))


def test_summarise_of_nothing_is_all_zero() -> None:
    assert summarise(()) == {c.value: 0 for c in Confidence}


def test_extraction_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "target"
    _write(repo, "src/pkg/tools/__init__.py")
    _write(repo, "src/pkg/tools/registry.py", "x = 1\n")
    inventory = build_inventory(repo)
    assert extract_candidates(inventory) == extract_candidates(inventory)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("requests>=2.31", "requests"),
        ("[extras] pytest>=8,<9", "pytest"),
        ("[peer] react-dom", "react-dom"),
        ("faiss_cpu", "faiss-cpu"),
        ("httpx", "httpx"),
        ("pydantic-settings==2.0", "pydantic-settings"),
        ("uvicorn[standard]>=0.30", "uvicorn"),
        ("tomli; python_version < '3.11'", "tomli"),
    ],
)
def test_requirement_name_extraction(requirement: str, expected: str) -> None:
    assert _requirement_name(requirement) == expected


def test_requirement_name_handles_junk() -> None:
    assert _requirement_name("") == ""
    assert _requirement_name("[unclosed") == ""


def test_manifest_matches_ignores_stopwords() -> None:
    inventory = _inventory(
        manifests=(Manifest("p.toml", "pyproject", ("[extras] python",)),)
    )
    assert _manifest_matches(inventory, ("python",)) == ()


def test_manifest_matches_without_hints_is_empty() -> None:
    inventory = _inventory(manifests=(Manifest("p.toml", "pyproject", ("requests",)),))
    assert _manifest_matches(inventory, ()) == ()


def test_manifest_matches_deduplicates() -> None:
    inventory = _inventory(
        manifests=(
            Manifest("p.toml", "pyproject", ("faiss-cpu",)),
            Manifest("r.txt", "requirements", ("faiss-cpu",)),
        )
    )
    assert _manifest_matches(inventory, ("faiss",)) == ("faiss-cpu",)


def test_matching_directories_orders_shallowest_first() -> None:
    directories = ("a/b/c/tools", "tools", "z/tools")
    assert _matching_directories(directories, ("tool",))[0] == "tools"


def test_matching_directories_is_component_wise_not_substring() -> None:
    # `tools_and_tips` contains "tool" as a substring but is not a `tools`
    # component match... except it is a component, so it DOES match. The real
    # assertion is that a non-component substring in a path does not match.
    assert _matching_directories(("docs/tooling.md",), ("tool",)) == ()


def test_directory_has_modules_uses_packages() -> None:
    inventory = _inventory(packages=("src/pkg",))
    assert _directory_has_modules("src/pkg", inventory)
    assert not _directory_has_modules("src/other", inventory)


def test_directory_has_modules_uses_test_layout() -> None:
    inventory = _inventory(test_dirs=("src/pkg/tests",))
    assert _directory_has_modules("src/pkg", inventory)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Retrieval / vector search", "retrieval-vector-search"),
        ("MCP (protocol)", "mcp-protocol"),
        ("  spaced  out  ", "spaced-out"),
        ("", "unnamed"),
        ("!!!", "unnamed"),
        ("Already-slugged", "already-slugged"),
    ],
)
def test_slugify_produces_taxonomy_safe_ids(text: str, expected: str) -> None:
    # Proposed pattern ids must be usable as TAXONOMY.md ids.
    assert slugify(text) == expected
