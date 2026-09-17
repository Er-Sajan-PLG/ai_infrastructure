"""Structural inventory of a cloned study target — static, never executed.

WHAT THIS PRODUCES, AND WHAT IT CANNOT
--------------------------------------
This module answers *structural* questions about a repository: what is in it,
how it is laid out, what it declares as its dependencies, which marker files
are present. It answers them by reading files as data.

It deliberately does **not** answer questions that require running the target:
there is no "how many tests pass", no "what is the resolved dependency set", no
"what does this function return". Those would require executing or installing
third-party code, which ADR-0021 Decision 1 forbids without exception.

The consequence is a real depth limit and it is stated in every report:
this module reports *"declares 14 dependencies"*, not *"resolves to 63
packages"*. That is a loss, recorded in ADR-0021's consequences with a reversal
condition, rather than an oversight. A structural map is what a study report
actually needs; the rest is inference that a session performs, not a fact this
module can assert.

Manifests are PARSED, not resolved
----------------------------------
Reading `pyproject.toml` with `tomllib` extracts declared requirement *strings*.
Nothing is fetched, and no version is resolved against an index. A requirement
like `requests>=2.31,<3` is reported as that string.
"""

from __future__ import annotations

import contextlib
import json
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

#: Directories excluded from every walk. These are not "the repository" for the
#: purpose of understanding its structure: they are version control, build
#: output, or dependency caches. Including them would swamp the counts and make
#: two studies of the same project at different commits incomparable.
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        # uv's workspace-local cache. This repository sets UV_CACHE_DIR to
        # `.uv-cache/` (see the Makefile), and a cache directory contains
        # hundreds of extracted packages with their own __init__.py files.
        # Found by testing against this repository as a KNOWN fixture: the
        # inventory reported 4602 files for a 214-file repository, and listed
        # 60+ third-party packages as if they were ours.
        ".uv-cache",
        # Other dependency caches that extract packages into the tree.
        ".cache",
        ".gradle",
        ".cargo",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".eggs",
        "build",
        "dist",
        ".next",
        ".nuxt",
        "target",
        "vendor",
    }
)

#: Files whose presence says something specific about how a project is built.
#: Grouped by what the presence *means*, because that is what a report needs —
#: a bare filename list makes the reader do the interpretation.
MARKER_FILES: Final[dict[str, tuple[str, ...]]] = {
    "python-packaging": ("pyproject.toml", "setup.py", "setup.cfg", "Pipfile"),
    "python-requirements": ("requirements.txt", "requirements-dev.txt"),
    "node-packaging": (
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package-lock.json",
    ),
    "rust-packaging": ("Cargo.toml",),
    "go-packaging": ("go.mod",),
    "containers": ("Dockerfile", "docker-compose.yml", "compose.yaml"),
    "ci-github": (".github/workflows",),
    "ci-gitlab": (".gitlab-ci.yml",),
    "ci-other": (".circleci", "Jenkinsfile", ".travis.yml", "azure-pipelines.yml"),
    "docs": ("docs", "mkdocs.yml", "doc", "documentation"),
    "tests": ("tests", "test", "testing"),
    "type-checking": ("mypy.ini", ".mypy.ini", "pyrightconfig.json"),
    "linting": (".pre-commit-config.yaml", ".flake8", ".pylintrc", "ruff.toml"),
    "governance": (
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "COPYING",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "GOVERNANCE.md",
        "CHANGELOG.md",
        "CITATION.cff",
    ),
    "adr": ("docs/decisions", "docs/adr", "adr", "decisions"),
    "editor": (".editorconfig", ".gitattributes"),
    "packaging-meta": ("MANIFEST.in", ".dockerignore", ".gitignore"),
    "notebooks": ("notebooks", "examples/tutorials"),
}

#: Extensions counted separately in :attr:`Inventory.extension_counts`. Kept to
#: a known set rather than "every extension seen", because a dependency cache
#: or a vendored tree produces hundreds of one-off extensions that are noise.
COUNTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".md",
        ".rst",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".cfg",
        ".ini",
        ".sh",
        ".sql",
        ".proto",
        ".ipynb",
    }
)

#: Directories that conventionally hold tests, used to estimate test layout
#: without importing anything.
_TEST_DIR_NAMES: Final[frozenset[str]] = frozenset({"tests", "test", "testing", "spec"})

#: A published package name is 1-2 path segments deep for the layouts we study.
_MAX_PACKAGE_DEPTH: Final = 3

#: Guards against a pathological tree (a fork bomb of directories, or a
#: deliberately hostile repository) turning a study into an unbounded walk.
MAX_FILES_WALKED: Final = 200_000


@dataclass(frozen=True, slots=True)
class Manifest:
    """A dependency manifest that was read and parsed.

    :attr:`requirements` holds declared requirement *strings*, not resolved
    versions. See the module docstring.
    """

    path: str
    kind: str
    requirements: tuple[str, ...] = ()
    error: str = ""


@dataclass(frozen=True, slots=True)
class Inventory:
    """The structural map of a studied repository.

    Every field is derived from reading files. No field asserts anything about
    runtime behaviour, and the report's wording must reflect that (ADR-0021).
    """

    total_files: int
    total_bytes: int
    extension_counts: dict[str, int]
    top_level_entries: tuple[str, ...]
    directories: tuple[str, ...]
    packages: tuple[str, ...]
    test_dirs: tuple[str, ...]
    test_file_count: int
    markers: dict[str, tuple[str, ...]]
    manifests: tuple[Manifest, ...]
    truncated: bool = False
    notes: tuple[str, ...] = field(default=())

    @property
    def declared_dependencies(self) -> tuple[str, ...]:
        """Every requirement string declared across all manifests, deduplicated.

        Deduplicated because the same package frequently appears in both
        `pyproject.toml` and `requirements.txt`, and reporting it twice
        overstates the dependency surface a reader is trying to assess.
        """
        seen: dict[str, None] = {}
        for manifest in self.manifests:
            for requirement in manifest.requirements:
                seen.setdefault(requirement, None)
        return tuple(seen)

    @property
    def primary_language(self) -> str:
        """Best-effort dominant language, from counted extensions only.

        `OBSERVATION`, not understanding: the largest file count by extension.
        A report must not phrase this as "this project is written in X" without
        the reader knowing it is a counting result. Docs and config extensions
        are excluded so a heavily documented project does not report as
        "Markdown".
        """
        code_extensions = {
            ".py": "Python",
            ".pyi": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".mjs": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".kt": "Kotlin",
            ".rb": "Ruby",
        }
        totals: Counter[str] = Counter()
        for extension, count in self.extension_counts.items():
            language = code_extensions.get(extension)
            if language:
                totals[language] += count
        if not totals:
            return "unknown"
        return totals.most_common(1)[0][0]


def _walk(root: Path) -> tuple[list[Path], bool]:
    """List every file under `root`, skipping :data:`SKIP_DIRS`.

    Returns `(files, truncated)`. Truncation is reported rather than silently
    applied: a study that quietly walked half a repository would produce a
    report whose numbers look complete and are not.
    """
    files: list[Path] = []
    truncated = False

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            # An unreadable directory is skipped, not fatal: a permissions
            # quirk in a third-party tree must not abort a study.
            continue
        for entry in entries:
            if len(files) >= MAX_FILES_WALKED:
                return files, True
            try:
                if entry.is_symlink():
                    # Symlinks are never followed: a studied repository can
                    # contain a link to `/` or to a huge tree, which would make
                    # the walk unbounded.
                    continue
                if entry.is_dir():
                    if entry.name in SKIP_DIRS:
                        continue
                    stack.append(entry)
                elif entry.is_file():
                    files.append(entry)
            except OSError:
                continue
    return files, truncated


def _relative(path: Path, root: Path) -> str:
    """POSIX-style path relative to the repository root."""
    return path.relative_to(root).as_posix()


def _detect_markers(root: Path) -> dict[str, tuple[str, ...]]:
    """Return marker groups whose members are present, with the names found.

    Reports *which* members were found rather than a boolean: "has governance
    files" is much weaker evidence than "has LICENSE, SECURITY.md and
    CHANGELOG.md but not CONTRIBUTING.md", and the second is what a reader
    assessing project maturity needs.
    """
    found: dict[str, tuple[str, ...]] = {}
    for group, names in MARKER_FILES.items():
        present = tuple(name for name in names if (root / name).exists())
        if present:
            found[group] = present
    return found


def _parse_pep508_ish(text: str) -> tuple[str, ...]:
    """Extract requirement strings from a `requirements.txt`-style file.

    Line-oriented, which is what the format is. Comments, blank lines, options
    (`-r other.txt`, `--index-url ...`) and environment markers are handled by
    keeping the requirement and dropping the rest. Nothing is resolved and no
    index is contacted.
    """
    requirements: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            # Options and nested includes are skipped rather than followed: a
            # transitive file is outside the tree we were asked to study.
            continue
        requirements.append(line)
    return tuple(requirements)


def _parse_pyproject(path: Path) -> Manifest:
    """Parse `pyproject.toml` for declared dependencies and tooling signals."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return Manifest(path=path.name, kind="pyproject", error=f"unreadable: {exc}")

    try:
        data = tomllib.loads(raw.decode("utf-8", errors="replace"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        # A malformed manifest is a FINDING about the project, not a crash.
        # Report it and continue: one bad file must not abort a study.
        return Manifest(path=path.name, kind="pyproject", error=f"invalid TOML: {exc}")

    requirements: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        for key in ("dependencies",):
            value = project.get(key)
            if isinstance(value, list):
                requirements.extend(str(item) for item in value)
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group_items in optional.values():
                if isinstance(group_items, list):
                    # Grouped extras are labelled so a reader can see that
                    # `pytest` is a dev dependency, not a runtime one.
                    requirements.extend(f"[extras] {item}" for item in group_items)

    # Poetry-style declarations predate PEP 621 and are still common.
    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            deps = poetry.get("dependencies", {})
            if isinstance(deps, dict):
                requirements.extend(name for name in deps if name.lower() != "python")
            dev = poetry.get("dev-dependencies", {})
            if isinstance(dev, dict):
                requirements.extend(f"[extras] {name}" for name in dev)

    return Manifest(path=path.name, kind="pyproject", requirements=tuple(requirements))


def _parse_package_json(path: Path) -> Manifest:
    """Parse `package.json` for declared dependencies (Node targets)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        return Manifest(
            path=path.name, kind="package.json", error=f"invalid JSON: {exc}"
        )

    requirements: list[str] = []
    if isinstance(data, dict):
        for key, label in (
            ("dependencies", ""),
            ("devDependencies", "[extras] "),
            ("peerDependencies", "[peer] "),
        ):
            block = data.get(key)
            if isinstance(block, dict):
                requirements.extend(f"{label}{name}" for name in block)
    return Manifest(
        path=path.name, kind="package.json", requirements=tuple(requirements)
    )


def _parse_cargo(path: Path) -> Manifest:
    """Parse `Cargo.toml` for declared dependencies."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Manifest(path=path.name, kind="cargo", error=f"invalid TOML: {exc}")

    requirements: list[str] = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            label = "[extras] " if "dev" in section or "build" in section else ""
            requirements.extend(f"{label}{name}" for name in block)
    return Manifest(path=path.name, kind="cargo", requirements=tuple(requirements))


def _count_nested_manifests(root: Path, directories: tuple[str, ...]) -> int:
    """Count recognised manifests that exist BELOW the repository root.

    Uses the already-computed directory list, so this costs one `is_file` per
    directory plus the root, rather than a second walk of the tree.

    The root-only parsing policy in :func:`_read_manifests` is unchanged: a
    nested manifest describes its own package, and folding 620 of them into one
    dependency list would misstate the project. This exists so the report can
    say the count is root-only rather than leaving a reader to conclude the
    project has four dependencies.
    """
    return sum(
        1
        for directory in directories
        for name in _manifest_filenames()
        if (root / directory / name).is_file()
    )


def _manifest_filenames() -> tuple[str, ...]:
    """Every filename this module knows how to parse."""
    return (
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "package.json",
    )


def _read_manifests(root: Path) -> tuple[Manifest, ...]:
    """Read every recognised manifest present at the repository root.

    Root only, deliberately. Manifests nested in `examples/` describe the
    examples, not the project, and folding them in would misstate what the
    project itself depends on.
    """
    manifests: list[Manifest] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        manifests.append(_parse_pyproject(pyproject))

    for name in ("requirements.txt", "requirements-dev.txt"):
        candidate = root / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                manifests.append(
                    Manifest(path=name, kind="requirements", error=str(exc))
                )
                continue
            manifests.append(
                Manifest(
                    path=name,
                    kind="requirements",
                    # Dev requirements are labelled so the distinction between
                    # shipping and development dependencies survives the report.
                    requirements=tuple(
                        f"[extras] {r}" if "dev" in name else r
                        for r in _parse_pep508_ish(text)
                    ),
                )
            )

    package_json = root / "package.json"
    if package_json.is_file():
        manifests.append(_parse_package_json(package_json))

    cargo = root / "Cargo.toml"
    if cargo.is_file():
        manifests.append(_parse_cargo(cargo))

    return tuple(manifests)


def _detect_packages(root: Path, directories: tuple[str, ...]) -> tuple[str, ...]:
    """Guess importable package roots from directory shape alone.

    Uses conventional markers (`__init__.py`) rather than importing anything.
    A `src/` layout is handled because it is now the common correct default and
    looking only at the root would miss it entirely.
    """
    packages: list[str] = []

    for name in ("src", "lib"):
        if (root / name).is_dir():
            for child in sorted((root / name).iterdir()):
                if child.is_dir() and (child / "__init__.py").is_file():
                    packages.append(f"{name}/{child.name}")

    for directory in directories:
        if directory.count("/") > _MAX_PACKAGE_DEPTH:
            continue
        # Belt and braces: even if a cache directory evaded SKIP_DIRS, it must
        # never be reported as one of the project's own packages.
        if any(part in SKIP_DIRS for part in directory.split("/")):
            continue
        # A test directory frequently carries an `__init__.py` so the test
        # runner can import it. That makes it importable, not a package the
        # project SHIPS. Found by studying psf/requests, where this listed
        # `tests` and `tests/testserver` alongside the real `src/requests`.
        if any(part in _TEST_DIR_NAMES for part in directory.split("/")):
            continue
        if (root / directory / "__init__.py").is_file():
            packages.append(directory)

    return tuple(dict.fromkeys(packages))


_EXTENSION_RE: Final = re.compile(r"(\.[A-Za-z0-9]+)$")


def build_inventory(root: Path) -> Inventory:
    """Build the structural map for a cloned repository.

    Pure with respect to its input: reads `root` and returns a value. It
    executes nothing from `root` and imports nothing from it (ADR-0021).
    """
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    files, truncated = _walk(root)

    extension_counts: Counter[str] = Counter()
    total_bytes = 0
    test_file_count = 0
    test_dirs: set[str] = set()

    for path in files:
        # A file can be unreadable or vanish mid-walk. Size accounting is
        # advisory, so skipping is correct where crashing is not.
        with contextlib.suppress(OSError):
            total_bytes += path.stat().st_size

        match = _EXTENSION_RE.search(path.name)
        if match and match.group(1).lower() in COUNTED_EXTENSIONS:
            extension_counts[match.group(1).lower()] += 1

        relative = _relative(path, root)
        parts = relative.split("/")
        # A test file is one inside a conventional test directory. This is a
        # naming convention, not a measured fact about what runs; reports must
        # say "test files" rather than "tests".
        if any(part in _TEST_DIR_NAMES for part in parts[:-1]):
            test_file_count += 1
            for index, part in enumerate(parts[:-1]):
                if part in _TEST_DIR_NAMES:
                    test_dirs.add("/".join(parts[: index + 1]))
                    break

    directories = tuple(
        sorted(
            _relative(path, root)
            for path in root.rglob("*")
            if path.is_dir()
            and not path.is_symlink()
            and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)
        )
    )

    notes: list[str] = []
    if truncated:
        notes.append(
            f"walk stopped at {MAX_FILES_WALKED} files; counts below are a lower "
            "bound, not a total"
        )

    nested = _count_nested_manifests(root, directories)
    if nested:
        # A monorepo is not a root-only project, and reporting "4 declared
        # dependencies" for one is confidently misleading rather than merely
        # incomplete. Found by studying LlamaIndex: it has 620 nested
        # `pyproject.toml` files (one per integration package) and the root
        # manifest names four. Root-only reading is still correct for the
        # DEPENDENCY LIST -- a nested manifest describes its own package, not
        # the project -- but the report must not then imply the project has
        # almost no components.
        notes.append(
            f"{nested} manifest(s) exist below the root (this is a monorepo or "
            "multi-package repository). Only root manifests are parsed, so the "
            "declared-dependency count is that of the root project alone, not "
            "the total across packages."
        )

    return Inventory(
        total_files=len(files),
        total_bytes=total_bytes,
        extension_counts=dict(extension_counts.most_common()),
        top_level_entries=tuple(sorted(entry.name for entry in root.iterdir())),
        directories=directories,
        packages=_detect_packages(root, directories),
        test_dirs=tuple(sorted(test_dirs)),
        test_file_count=test_file_count,
        markers=_detect_markers(root),
        manifests=_read_manifests(root),
        truncated=truncated,
        notes=tuple(notes),
    )
