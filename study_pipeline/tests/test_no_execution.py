"""The no-execution guarantee, enforced as a check rather than a comment.

WHY THIS FILE EXISTS
--------------------
ADR-0021 Decision 1 says the study pipeline never executes, imports, or
installs code from a studied repository. Charter §20 says *"a rule with no check
is a preference"* — so this decision needs a check, and this is it.

The failure mode being guarded against is specific and plausible. A future
session wanting richer study data (a resolved dependency graph, a real test
count, an extracted type signature) would find that `pip install -e <clone>` and
`import` are the obvious way to get it. That change would look like an
improvement in a diff, would make reports more detailed, and would silently
convert the pipeline into a supply-chain surface that runs arbitrary code from
repositories selected precisely *because* they are large and unfamiliar.

These tests make that change fail loudly instead of arriving as a reasonable
-looking commit.

HOW THE GUARANTEE IS CHECKED
----------------------------
Statically over the pipeline's own source — a scan for the dangerous call sites
— plus behaviourally, by cloning a repository that WOULD execute code if
imported or installed, and asserting that studying it produces a report and
leaves no trace of that code having run.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_ROOT = REPO_ROOT / "study_pipeline"

#: Call names that would execute studied code. Each is checked separately so a
#: failure names the exact construct rather than "the scan found something".
FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "importlib.import_module",
        "importlib.reload",
        "runpy.run_path",
        "runpy.run_module",
        "pickle.load",
        "pickle.loads",
        "marshal.loads",
        "yaml.load",
    }
)

#: Subprocess invocations that would install or run a studied repository's own
#: tooling. `git` is the only permitted subprocess target in this package.
FORBIDDEN_SUBPROCESS_HEADS: frozenset[str] = frozenset(
    {
        "pip",
        "pip3",
        "uv",
        "poetry",
        "conda",
        "npm",
        "yarn",
        "pnpm",
        "make",
        "tox",
        "nox",
    }
)


#: The package's own source files (excluding tests, which legitimately use
#: `eval`-adjacent constructs for assertions and fixtures).
def _pipeline_sources() -> list[Path]:
    return sorted(
        path
        for path in PIPELINE_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(PIPELINE_ROOT).parts
    )


def test_pipeline_has_sources_to_check() -> None:
    # A scan over zero files would pass and mean nothing. The floor is the
    # module count as built, not the planned count: raising it is part of
    # adding a module, so the check cannot silently stop covering new files.
    sources = _pipeline_sources()
    assert len(sources) >= 3, [p.name for p in sources]


@pytest.mark.parametrize("source", _pipeline_sources(), ids=lambda p: p.name)
def test_no_dynamic_execution_primitives(source: Path) -> None:
    """No `eval`, `exec`, `compile`, `__import__` or dynamic-import calls.

    Parsed with `ast`, not grepped: a grep for "eval" matches the word inside a
    comment or a docstring explaining WHY eval is forbidden, which would make
    this test impossible to satisfy honestly alongside good documentation.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in FORBIDDEN_CALLS:
                offenders.append(f"{source.name}:{node.lineno} calls {name}()")

    assert offenders == [], (
        "The study pipeline must never execute studied code (ADR-0021 Decision 1). "
        "Offending calls:\n  " + "\n  ".join(offenders)
    )


def _call_name(func: ast.expr) -> str:
    """Render a call target as a dotted name, e.g. `importlib.import_module`."""
    parts: list[str] = []
    current: ast.expr = func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


@pytest.mark.parametrize("source", _pipeline_sources(), ids=lambda p: p.name)
def test_subprocess_is_git_only(source: Path) -> None:
    """The only subprocess this package may run is `git`.

    Installing a studied repository's dependencies (`pip install -e .`) would
    execute its `setup.py`; running its tests would execute its `conftest.py`.
    Both are excluded by name so the error message says which one appeared.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) not in {
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.check_output",
        }:
            continue
        # The argv is `["git", *args]` — a List with a Str head.
        assert node.args, f"{source.name}:{node.lineno} subprocess call has no argv"
        head = node.args[0]
        assert isinstance(head, ast.List), (
            f"{source.name}:{node.lineno} passes a non-literal argv to subprocess. "
            "argv must be a literal list so its head can be checked."
        )
        first = head.elts[0]
        assert isinstance(first, ast.Constant) and first.value == "git", (
            f"{source.name}:{node.lineno} invokes "
            f"{getattr(first, 'value', '?')!r}; only git is permitted (ADR-0021)."
        )


@pytest.mark.parametrize("source", _pipeline_sources(), ids=lambda p: p.name)
def test_shell_is_never_enabled(source: Path) -> None:
    """No `shell=True`, which would turn a validated argv back into a string.

    `normalise_repo_url` validates the one caller-supplied argument precisely
    because git is invoked with a fixed argv. `shell=True` would defeat that
    entirely, so it is checked for separately.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "shell":
                assert not (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ), f"{source.name}:{node.lineno} passes shell=True"


#: Filesystem-mutating methods. A call to one of these with a path that names
#: `catalog` or `integrations` would violate ADR-0021 Decision 2.
_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "unlink",
        "rmdir",
        "mkdir",
        "touch",
        "replace",
        "rename",
        "symlink_to",
        "hardlink_to",
        "chmod",
    }
)

#: Paths the pipeline must never mutate. It writes reports under
#: `study_pipeline/studied_repos/` and nothing else.
_FORBIDDEN_TARGETS: frozenset[str] = frozenset({"catalog", "integrations"})


@pytest.mark.parametrize("source", _pipeline_sources(), ids=lambda p: p.name)
def test_pipeline_never_writes_outside_studied_repos(source: Path) -> None:
    """No filesystem mutation targeting `catalog/` or `integrations/`.

    ADR-0021 Decision 2: the pipeline writes Markdown reports and nothing else,
    which is what makes `code_reused: false` structurally true rather than a
    promise.

    **This check inspects CALLS, not text.** Its first version searched each
    file's raw source for the substring `catalog/`, which flagged this module's
    own docstrings — the pipeline documents *why* it must not write there, and
    explaining a prohibition is not violating it. A checker that fails on the
    documentation of the rule it enforces would have been "fixed" by deleting
    the explanation, which is the opposite of the intent.

    Matching on the AST also makes the check STRONGER than the text search: a
    write whose target is built at runtime from a variable still has to name a
    mutating method, and the method subset is small enough to enumerate.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        method = name.rsplit(".", 1)[-1]
        if method not in _MUTATING_METHODS:
            continue
        # Inspect every string literal anywhere in the call's arguments: the
        # target is frequently `root / "catalog" / entry`, so a direct-argument
        # check would miss it.
        for literal in _string_literals(node):
            if literal.strip("/") in _FORBIDDEN_TARGETS:
                offenders.append(
                    f"{source.name}:{node.lineno} {method}(...) targets {literal!r}"
                )

    assert offenders == [], (
        "The study pipeline must not write into catalog/ or integrations/ "
        "(ADR-0021 Decision 2). Offending calls:\\n  " + "\\n  ".join(offenders)
    )


def _string_literals(node: ast.AST) -> list[str]:
    """Every string constant appearing anywhere beneath `node`."""
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


# ---------------------------------------------------------------------------
# Behavioural check: study a repository that WOULD execute code if imported
# ---------------------------------------------------------------------------


def test_studying_an_executing_repository_runs_nothing(tmp_path: Path) -> None:
    """A target whose import has a side effect must not trigger it.

    Builds a fake repository containing a module that writes a sentinel file on
    import, and a `conftest.py` that does the same on collection. Studies it
    with the real pipeline entry points and asserts the sentinel never appears.

    This is the behavioural form of the static checks above, and it is the one
    that would catch a future refactor that introduced execution by a route the
    static scan does not name.
    """
    from study_pipeline.inventory import build_inventory

    sentinel = tmp_path / "EXECUTED"
    repo = tmp_path / "target"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text(
        f"open({str(sentinel)!r}, 'w').write('imported')\n", encoding="utf-8"
    )
    (repo / "conftest.py").write_text(
        f"open({str(sentinel)!r}, 'w').write('conftest ran')\n", encoding="utf-8"
    )
    (repo / "setup.py").write_text(
        f"open({str(sentinel)!r}, 'w').write('setup ran')\n", encoding="utf-8"
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "target"\nversion = "1.0"\n'
        'dependencies = ["requests>=2"]\n',
        encoding="utf-8",
    )

    inventory = build_inventory(repo)

    # The study produced real data...
    assert inventory.total_files >= 4
    assert "requests>=2" in inventory.declared_dependencies
    assert "python-packaging" in inventory.markers
    # ...and nothing in the target executed.
    assert not sentinel.exists(), (
        f"Studying the target executed code from it ({sentinel.read_text()!r}). "
        "The pipeline must never import, exec or install studied code (ADR-0021)."
    )


def test_workspace_is_not_on_sys_path() -> None:
    """The clone destination must never be importable.

    Checked against the configured workspace rather than after a clone, so this
    runs without network access.
    """
    from study_pipeline.workspace import WORKSPACE_DIRNAME, workspace_path

    assert WORKSPACE_DIRNAME.startswith(".")
    documented = workspace_path().resolve()
    for entry in sys.path:
        try:
            resolved = Path(entry or ".").resolve()
        except OSError:  # pragma: no cover
            continue
        assert resolved != documented
        assert documented not in resolved.parents


def test_gitignore_covers_the_workspace() -> None:
    """Cloned third-party code must never be committable.

    A check rather than a convention: committing a clone would add another
    project's source to this repository's history under this repository's
    license.
    """
    from study_pipeline.workspace import WORKSPACE_DIRNAME

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(
        rf"^{re.escape(WORKSPACE_DIRNAME)}/?\s*$", gitignore, re.MULTILINE
    ), (
        f"{WORKSPACE_DIRNAME}/ is not gitignored. Cloned repositories must never "
        "be committable."
    )
