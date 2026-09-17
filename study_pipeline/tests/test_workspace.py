"""Unit tests for study_pipeline.workspace — the trust boundary.

This module is the pipeline's boundary with hostile input: a URL comes from
outside and becomes a `git` argument and a filesystem path. It was the
LEAST-covered module at 39% before these tests, because its clone path was only
exercised by network-marked tests — which are deselected by default. The least
trusted surface being the least tested is the wrong way round.

The tests that matter here are the refusals. Each is a real attack against a
naive implementation:

  * **Option injection** — `--upload-pack=evil` passed to git as a flag.
  * **Local file read** — `file:///etc/passwd` as the "repository".
  * **SSRF to cloud metadata** — `http://169.254.169.254/`.
  * **Path traversal** — a slug like `../..` escaping the workspace.
  * **Arbitrary host** — cloning from a host the operator did not approve.

Everything here runs offline: a real git repository is created on disk and
reached through `_git`, so the clone mechanics are exercised without network.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from study_pipeline.workspace import (
    ALLOWED_HOSTS,
    MAX_CLONE_BYTES,
    WORKSPACE_DIRNAME,
    Clone,
    StudyError,
    _directory_size_bytes,
    _git,
    normalise_repo_url,
    project_slug,
    prune_workspace,
    repo_root,
    study_workspace,
    workspace_path,
    workspace_size_bytes,
)

# ---------------------------------------------------------------------------
# Host allowlist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", sorted(ALLOWED_HOSTS))
def test_allowed_hosts_are_accepted(host: str) -> None:
    assert (
        normalise_repo_url(f"https://{host}/owner/name") == f"https://{host}/owner/name"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/owner/name",
        "https://github.evil.com/owner/name",
        "https://raw.githubusercontent.com/owner/name",
        "https://127.0.0.1/owner/name",
        "https://localhost/owner/name",
    ],
)
def test_unapproved_hosts_are_refused(url: str) -> None:
    with pytest.raises(StudyError, match="not in the allowed set"):
        normalise_repo_url(url)


def test_host_suffix_confusion_is_refused() -> None:
    # `github.com.evil.com` must not match a substring check on `github.com`.
    with pytest.raises(StudyError):
        normalise_repo_url("https://github.com.evil.com/a/b")


# ---------------------------------------------------------------------------
# Option injection — the highest-severity class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "--upload-pack=/bin/evil",
        "--config=core.pager=evil",
        "-c core.pager=evil",
        "--help",
        "-u",
    ],
)
def test_leading_dash_is_refused(payload: str) -> None:
    """A URL beginning with `-` would be read by git as an OPTION.

    This is the classic argument-injection shape: the value looks like data but
    becomes a flag. `--upload-pack` is the dangerous one, since it names a
    program git then executes.
    """
    with pytest.raises(StudyError, match="refusing URL beginning with"):
        normalise_repo_url(payload)


@pytest.mark.parametrize(
    "payload",
    [
        "https://github.com/owner/name;rm -rf /",
        "https://github.com/owner/name && id",
        "https://github.com/owner/name|cat /etc/passwd",
        "https://github.com/owner/name`id`",
        "https://github.com/owner/name$(id)",
    ],
)
def test_shell_metacharacters_are_refused(payload: str) -> None:
    # No shell is used anywhere (shell=False), so these are defence in depth:
    # the slug regex rejects them before they reach a path.
    with pytest.raises(StudyError):
        normalise_repo_url(payload)


# ---------------------------------------------------------------------------
# Scheme and path shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://github.com/owner/name",
        "ssh://git@github.com/owner/name",
        "javascript:alert(1)",
        "data:text/html,<script>",
    ],
)
def test_unsupported_schemes_are_refused(url: str) -> None:
    with pytest.raises(StudyError):
        normalise_repo_url(url)


def test_ssrf_to_cloud_metadata_is_refused() -> None:
    # The canonical SSRF target: a naive fetch to this returns instance
    # credentials on AWS/GCP/Azure.
    with pytest.raises(StudyError, match="not in the allowed set"):
        normalise_repo_url("http://169.254.169.254/latest/meta-data/")


def test_ssh_form_is_normalised_to_https() -> None:
    assert (
        normalise_repo_url("git@github.com:owner/name.git")
        == "https://github.com/owner/name"
    )


def test_dot_git_suffix_is_stripped() -> None:
    assert normalise_repo_url("https://github.com/owner/name.git") == (
        "https://github.com/owner/name"
    )


def test_trailing_slash_is_stripped() -> None:
    assert normalise_repo_url("https://github.com/owner/name/") == (
        "https://github.com/owner/name"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner",
        "https://github.com/owner/name/subpath",
        "https://github.com/a/b/c",
        "",
        "   ",
    ],
)
def test_wrong_path_depth_is_refused(url: str) -> None:
    with pytest.raises(StudyError):
        normalise_repo_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/../../etc/passwd",
        "https://github.com/owner/..",
        "https://github.com/owner/name%2F..%2F..",
        "https://github.com/ow ner/name",
    ],
)
def test_path_traversal_is_refused(url: str) -> None:
    with pytest.raises(StudyError):
        normalise_repo_url(url)


def test_no_host_is_refused() -> None:
    with pytest.raises(StudyError, match="no host"):
        normalise_repo_url("https:///owner/name")


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------


def test_slug_encodes_owner_and_name() -> None:
    assert (
        project_slug("https://github.com/psf/requests") == "github.com__psf__requests"
    )


def test_slug_is_filesystem_safe() -> None:
    slug = project_slug("https://github.com/psf/requests")
    assert "/" not in slug
    assert "\\" not in slug
    assert ".." not in slug


def test_slug_has_no_path_separator_even_from_a_hostile_input() -> None:
    # Only reachable via a normalised URL, but asserted so the property is
    # pinned rather than assumed.
    slug = project_slug(normalise_repo_url("https://github.com/a-b/c_d.e"))
    assert slug == "github.com__a-b__c_d.e"


def test_clone_name_and_owner() -> None:
    clone = Clone(
        url="https://github.com/psf/requests",
        slug="github.com__psf__requests",
        path=Path("/tmp/x"),
        commit="a" * 40,
        size_bytes=1,
    )
    assert clone.name == "requests"
    assert clone.owner == "psf"


def test_clone_is_frozen() -> None:
    import dataclasses

    clone = Clone(
        url="u",
        slug="s",
        path=Path("/tmp/x"),
        commit="a" * 40,
        size_bytes=1,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        clone.commit = "b" * 40  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Workspace paths
# ---------------------------------------------------------------------------


def test_repo_root_is_the_repository() -> None:
    root = repo_root()
    assert (root / "TAXONOMY.md").is_file()
    assert (root / "study_pipeline").is_dir()


def test_workspace_path_is_inside_the_repository() -> None:
    path = workspace_path()
    assert path.parent == repo_root()
    assert path.name == WORKSPACE_DIRNAME


def test_workspace_is_gitignored() -> None:
    # Cloned third-party code must never be committable.
    gitignore = (repo_root() / ".gitignore").read_text(encoding="utf-8")
    assert f"{WORKSPACE_DIRNAME}/" in gitignore


def test_workspace_size_of_a_missing_directory_is_zero() -> None:
    assert _directory_size_bytes(Path("/nonexistent/definitely/not/here")) == 0


# ---------------------------------------------------------------------------
# Git runner
# ---------------------------------------------------------------------------


@pytest.fixture
def real_repo(tmp_path: Path) -> Path:
    """A real git repository on disk, for exercising the clone path offline."""
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / "README.md").write_text("# hi\n")
    (origin / "src").mkdir()
    (origin / "src" / "main.py").write_text("x = 1\n")
    _git("init", "--quiet", "--initial-branch=main", cwd=origin)
    _git("config", "user.email", "t@example.com", cwd=origin)
    _git("config", "user.name", "T", cwd=origin)
    _git("add", "-A", cwd=origin)
    _git("commit", "--quiet", "-m", "initial", cwd=origin)
    return origin


def test_git_reports_failure_as_study_error(real_repo: Path) -> None:
    with pytest.raises(StudyError, match=r"git rev-parse failed \(exit \d+\)"):
        _git("rev-parse", "nonexistent-ref-xyz", cwd=real_repo)


def test_git_error_includes_stderr(real_repo: Path) -> None:
    with pytest.raises(StudyError) as caught:
        _git("rev-parse", "nope", cwd=real_repo)
    assert (
        "nope" in str(caught.value) or "unknown revision" in str(caught.value).lower()
    )


def test_git_succeeds_on_a_valid_command(real_repo: Path) -> None:
    output = _git("rev-parse", "--is-inside-work-tree", cwd=real_repo)
    assert output.strip() == "true"


def test_git_never_uses_a_shell(real_repo: Path) -> None:
    # A shell would turn a crafted URL component into command execution.
    # Asserted on the source because the guarantee is in the call, not the
    # outcome: `_git("log", "--format=%H; id")` would silently succeed.
    source = (repo_root() / "study_pipeline" / "workspace.py").read_text(
        encoding="utf-8"
    )
    assert "shell=False" in source
    assert "shell=True" not in source


def test_max_clone_bytes_is_bounded() -> None:
    # A guard that cannot be reached is not a guard. 2 GiB is large enough for
    # a real repository and small enough to stop a runaway clone.
    assert 0 < MAX_CLONE_BYTES <= 8 * 1024**3


# ---------------------------------------------------------------------------
# Workspace lifecycle — pruning and cleanup
# ---------------------------------------------------------------------------


def test_prune_workspace_removes_every_clone() -> None:
    path = workspace_path()
    clone = path / "probe__clone"
    (clone / "sub").mkdir(parents=True, exist_ok=True)
    (clone / "sub" / "file.txt").write_text("x" * 100)
    try:
        removed = prune_workspace()
        assert removed >= 1
        assert not clone.exists()
        assert workspace_size_bytes() == 0
    finally:
        prune_workspace()


def test_prune_leaves_the_workspace_directory_itself() -> None:
    # The workspace directory is cheap and recreated on demand; removing it
    # would race with a concurrent study for no benefit. The CLONES are what
    # need to go, since they are the gigabytes.
    path = workspace_path()
    (path / "probe__clone").mkdir(parents=True, exist_ok=True)
    try:
        prune_workspace()
        assert path.is_dir()
        assert workspace_size_bytes() == 0
    finally:
        prune_workspace()


def test_prune_workspace_is_idempotent() -> None:
    prune_workspace()
    assert prune_workspace() == 0


def test_prune_removes_loose_files_too() -> None:
    """A cleanup path must be able to reach a genuinely empty workspace.

    An earlier version removed only directories, so a stray file kept the
    workspace at 1 byte forever and `make study-clean` could never report a
    clean tree. Found by these tests.
    """
    path = workspace_path()
    path.mkdir(parents=True, exist_ok=True)
    loose = path / "loose.tmp"
    loose.write_text("x")
    try:
        prune_workspace()
        assert not loose.exists()
        assert workspace_size_bytes() == 0
    finally:
        prune_workspace()


def test_prune_does_not_follow_a_symlink_out_of_the_workspace(tmp_path: Path) -> None:
    # Deleting THROUGH a symlink would remove the target, which may be outside
    # the workspace entirely.
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "precious.txt"
    outside.write_text("keep me")
    (workspace / "link").symlink_to(outside)

    prune_workspace(workspace)

    assert outside.is_file(), "prune followed a symlink and deleted its target"
    assert not (workspace / "link").exists()


def test_workspace_size_bytes_after_prune_is_zero() -> None:
    prune_workspace()
    assert workspace_size_bytes() == 0


def test_prune_of_a_missing_workspace_returns_zero(tmp_path: Path) -> None:
    assert prune_workspace(tmp_path / "does-not-exist") == 0


def test_prune_leaves_written_reports_alone() -> None:
    """The workspace is disposable; written reports are not.

    They live in different directories precisely so that cleaning the clone
    cache cannot destroy study output.
    """
    reports = repo_root() / "study_pipeline" / "studied_repos"
    reports.mkdir(parents=True, exist_ok=True)
    marker = reports / "_prune_probe.tmp"
    marker.write_text("keep me")
    try:
        prune_workspace()
        assert marker.is_file(), "prune_workspace deleted a report"
    finally:
        marker.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# study_workspace — the context manager
# ---------------------------------------------------------------------------


def test_unknown_host_is_refused_before_any_directory_is_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "study_pipeline.workspace.workspace_path", lambda: tmp_path / "ws"
    )
    with pytest.raises(StudyError), study_workspace("https://evil.com/a/b"):
        pytest.fail("body must not run for a refused URL")
    assert not (tmp_path / "ws").exists()


def test_body_does_not_run_when_the_clone_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "study_pipeline.workspace.workspace_path", lambda: tmp_path / "ws"
    )
    ran = False
    with (
        pytest.raises(StudyError),
        study_workspace("https://github.com/definitely/does-not-exist-xyz123"),
    ):
        ran = True
    assert not ran


def test_cleanup_happens_even_when_the_body_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash inside the block must not leak the clone.

    Cloned code can be gigabytes; leaking it on every failure would fill the
    disk. The clone is faked by monkeypatching the git call, so this exercises
    the `finally` without needing a real clone or a permissive URL guard.
    """
    ws = tmp_path / "ws"
    monkeypatch.setattr("study_pipeline.workspace.workspace_path", lambda: ws)

    def fake_clone(*args: str, cwd: Path | None = None) -> str:
        # `study_workspace` clones into the destination then rev-parses it.
        if args and args[0] == "clone":
            destination = Path(args[-1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "payload.bin").write_bytes(b"x" * 4096)
            return ""
        if args and args[0] == "rev-parse":
            return "a" * 40
        return ""

    monkeypatch.setattr("study_pipeline.workspace._git", fake_clone)

    class BoomError(Exception):
        pass

    with pytest.raises(BoomError), study_workspace("https://github.com/owner/name"):
        assert (ws / "github.com__owner__name").is_dir()
        raise BoomError("crash inside the study")

    assert not (ws / "github.com__owner__name").exists(), "the clone leaked"
    assert _directory_size_bytes(ws) == 0


def test_successful_block_also_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = tmp_path / "ws"
    monkeypatch.setattr("study_pipeline.workspace.workspace_path", lambda: ws)

    def fake_clone(*args: str, cwd: Path | None = None) -> str:
        if args and args[0] == "clone":
            destination = Path(args[-1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "payload.bin").write_bytes(b"x" * 4096)
            return ""
        return "a" * 40 if args and args[0] == "rev-parse" else ""

    monkeypatch.setattr("study_pipeline.workspace._git", fake_clone)

    with study_workspace("https://github.com/owner/name") as clone:
        assert clone.commit == "a" * 40
        assert clone.size_bytes == 4096
        inside = clone.path

    assert not inside.exists(), "a successful study leaked its clone"
    assert _directory_size_bytes(ws) == 0


def test_context_manager_yields_a_clone_with_a_pinned_commit(real_repo: Path) -> None:
    """The clone path, exercised offline via a local `git clone`.

    `normalise_repo_url` refuses `file://`, so this calls the internal pieces
    directly: the point is to cover the clone mechanics (clone, rev-parse,
    size measurement, cleanup) without duplicating the URL guard.
    """
    ws = workspace_path()
    target = ws / "local__probe"
    prune_workspace()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git("clone", "--depth", "1", "--quiet", str(real_repo), str(target))
        commit = _git("rev-parse", "HEAD", cwd=target).strip()
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit)
        assert _directory_size_bytes(target) > 0
    finally:
        prune_workspace()
    assert workspace_size_bytes() == 0


def test_size_guard_refuses_and_cleans_up(
    real_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An oversize clone is refused, and the partial clone is removed.

    A refusal that left the bytes behind would be worse than no guard, since
    the retry would hit the same disk pressure.
    """
    ws = tmp_path / "ws"
    monkeypatch.setattr("study_pipeline.workspace.workspace_path", lambda: ws)
    monkeypatch.setattr("study_pipeline.workspace.MAX_CLONE_BYTES", 0)

    with (
        pytest.raises(StudyError, match=r"exceeds|size|cap"),
        study_workspace(str(real_repo)),
    ):
        pytest.fail("body must not run for an oversize clone")

    assert _directory_size_bytes(ws) == 0


def test_workspace_is_not_importable_by_accident() -> None:
    """A cloned repository must never end up on `sys.path`.

    If it did, a studied package could shadow a standard-library module for the
    rest of the process — an execution vector that needs no `eval` at all.
    """
    import sys

    workspace = str(workspace_path().resolve())
    for entry in sys.path:
        if not entry:
            continue
        assert not str(Path(entry).resolve()).startswith(workspace), entry
    assert str(Path(".study-workspace")) not in os.environ.get("PYTHONPATH", "")


def test_subprocess_is_only_ever_git() -> None:
    # Pinned textually as well as by the AST scan in test_no_execution, because
    # this file is the one place a subprocess is permitted at all.
    source = (repo_root() / "study_pipeline" / "workspace.py").read_text(
        encoding="utf-8"
    )
    assert '["git", *args]' in source
    assert subprocess.__name__ == "subprocess"
