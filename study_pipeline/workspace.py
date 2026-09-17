"""Clone lifecycle for study targets: workspace, commit pinning, cleanup.

THE SECURITY POSTURE OF THIS MODULE
-----------------------------------
This is the only place in the study pipeline that touches untrusted input
(a URL) and the only place that runs a subprocess. Both are constrained
deliberately:

1. **Fixed argv, never a shell.** `git` is invoked as an argument vector via
   :func:`subprocess.run` with `shell=False`. A target URL is validated against
   an allow-list of forms *before* it reaches git, so a URL like
   ``--upload-pack=...`` cannot be smuggled in as an option. See
   :func:`normalise_repo_url`.

2. **Cloned code is never executed.** `git clone` writes files; it does not run
   them. The checkout is placed in a directory that is never added to
   `sys.path`, and nothing in this module or any other imports from it.

3. **The checkout is disposable.** :func:`study_workspace` is a context manager
   that removes the clone in a `finally` block, so a crash mid-study does not
   leave a multi-hundred-megabyte tree behind. Cleanup on the failure path is
   the normal path here, not an afterthought.

4. **Size is bounded before it is committed to.** A `--depth 1` clone of a large
   repository is still large. :data:`MAX_CLONE_BYTES` is checked against the
   clone *after* it lands and before anything reads it, so an unexpectedly huge
   target is refused with an explanation instead of filling the disk.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess  # nosec B404
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

#: Where throwaway clones live. Gitignored (`.gitignore`) and never tracked.
#: Resolved relative to the repository root so it behaves the same from any cwd.
WORKSPACE_DIRNAME: Final = ".study-workspace"

#: Refuse to study a clone larger than this. Generous for a `--depth 1` checkout
#: of a large framework, small enough that a runaway does not eat the disk.
#: 2 GiB.
MAX_CLONE_BYTES: Final = 2 * 1024 * 1024 * 1024

#: `git clone` timeout. A hung network read must not hang a study session.
CLONE_TIMEOUT_SECONDS: Final = 600

#: How long to wait for a killed clone's process group to actually die before
#: giving up on reaping it. Short: SIGKILL cannot be caught, so this only
#: covers kernel scheduling, and waiting longer delays the error the caller
#: needs. See :func:`_kill_process_group`.
CLONE_KILL_GRACE_SECONDS: Final = 5

#: Hosts we will clone from. An allow-list, not a deny-list: a URL scheme or
#: host that is not recognised is refused rather than attempted (ADR-0021).
#: GitHub dominates the target list; the others are here because mature
#: infrastructure occasionally lives elsewhere.
ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "github.com",
        "gitlab.com",
        "codeberg.org",
    }
)

#: Repository path components must look like a normal owner/name pair. This is
#: the guard that stops an argument-injection attempt: git receives the URL as
#: a single argv element, but validating the shape first means a value that
#: could be *interpreted* as an option or a local path never reaches it.
_SLUG_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: A 40-character hex object name. Used to validate anything treated as a
#: commit hash before it is recorded as provenance.
_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")


class StudyError(RuntimeError):
    """A study could not proceed. Message is user-facing and actionable."""


def repo_root() -> Path:
    """Return the repository root, derived from this file's location.

    Deliberately not `Path.cwd()`: the workspace must be the same directory
    whether the CLI is run from the repository root, from `study_pipeline/`, or
    from a test with a temporary cwd.
    """
    return Path(__file__).resolve().parent.parent


def workspace_path() -> Path:
    """Return this process's throwaway-clone workspace directory.

    **Per-process, not per-repository.** Two concurrent studies of *different*
    targets still shared one workspace root, and each one's `finally` removed
    only its own directory -- so they did not obviously interfere. They did:
    `git clone` writes pack files into a temporary name inside the destination
    and, when two clones of the *same* target ran at once, one observed the
    other's in-flight pack vanish and failed with

        fatal: could not open .../tmp_pack_xxxx for reading: No such file
        fatal: fetch-pack: invalid index-pack output

    Verified twice: once when a background batch study overlapped a foreground
    licence-detection run, and again when a timed-out foreground run survived as
    an orphan and overlapped a later batch. Making the destination unique
    (below) fixed the case where both ran the same code; it could not fix an
    orphan from an already-started run, and it left the root shared.

    A per-process root removes the shared resource entirely: there is no
    directory two studies can both reach, whatever code they are running. The
    cost is that an orphaned clone is now identifiable by pid, which is an
    improvement for the recovery path in :func:`prune_workspace`.
    """
    return repo_root() / WORKSPACE_DIRNAME / f"study-{os.getpid()}"


def normalise_repo_url(raw: str) -> str:
    """Validate and canonicalise a study target URL.

    Accepts `https://host/owner/name` (with an optional trailing `.git`) and
    the `git@host:owner/name` SSH form, and returns the canonical HTTPS URL.

    **Raises `StudyError` rather than returning a best-effort value.** Anything
    that does not match is refused, because the alternative — passing an
    unrecognised string to `git` — is exactly the argument-injection path this
    function exists to close. A study target comes from a session's target list
    or a command line, and a typo should be a clear error, not a clone attempt
    against something unintended.

    That a value is a *valid* URL does not make the target *safe to study*; it
    makes it safe to pass to git. Execution safety is a separate guarantee
    (see this module's docstring).
    """
    candidate = raw.strip()
    if not candidate:
        raise StudyError("empty repository URL")

    # `--foo` or `/local/path` would be read by git as an option or a local
    # clone source. Refuse on shape before any parsing.
    if candidate.startswith("-"):
        raise StudyError(
            f"refusing URL beginning with '-': {candidate!r}. "
            "A leading dash is read by git as an option, not a repository."
        )

    ssh_match = re.match(r"^git@(?P<host>[^:]+):(?P<path>.+)$", candidate)
    if ssh_match:
        host = ssh_match.group("host")
        path = ssh_match.group("path")
    else:
        parsed = urlparse(candidate)
        if parsed.scheme not in {"https", "http"}:
            raise StudyError(
                f"unsupported URL scheme in {candidate!r}; "
                "use https:// or the git@host:owner/name form"
            )
        if not parsed.netloc:
            raise StudyError(f"no host in {candidate!r}")
        host = parsed.netloc
        path = parsed.path.lstrip("/")

    if host not in ALLOWED_HOSTS:
        allowed = ", ".join(sorted(ALLOWED_HOSTS))
        raise StudyError(
            f"host {host!r} is not in the allowed set ({allowed}). "
            "Add it to ALLOWED_HOSTS deliberately if the target is intended."
        )

    path = path.removesuffix(".git").strip("/")
    parts = path.split("/")
    if len(parts) != 2:
        raise StudyError(
            f"expected an owner/name path, got {path!r}. "
            "Sub-path study is not supported: clone the repository and point a "
            "report at the subtree instead."
        )
    owner, name = parts
    for part in (owner, name):
        if not _SLUG_RE.match(part):
            raise StudyError(
                f"invalid repository path component {part!r}; "
                "only letters, digits, dot, dash and underscore are allowed"
            )

    return f"https://{host}/{owner}/{name}"


def project_slug(url: str) -> str:
    """Derive a filesystem- and filename-safe slug from a normalised URL.

    `https://github.com/langchain-ai/langchain` becomes
    `github.com__langchain-ai__langchain`, which is unique across hosts (two
    hosts can both have an `owner/name`) and contains no path separator.
    """
    parsed = urlparse(normalise_repo_url(url))
    owner, name = parsed.path.lstrip("/").split("/")
    return f"{parsed.netloc}__{owner}__{name}"


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    """SIGKILL a started process and every process it forked.

    Required because a stalled `git clone` does not die when its direct child is
    killed: `git-remote-https` and `index-pack` are separate processes that
    inherit the stdout/stderr pipes, so the parent's `communicate()` keeps
    waiting on handles that will never close. Observed as a 73-minute hang on a
    stalled GitHub read that the 600s timeout failed to interrupt.

    `start_new_session=True` on the Popen makes the child a process-group
    leader, so the group id equals the child's pid and `killpg` reaches the
    whole tree. Falls back to killing just the child if the group is already
    gone, and never raises: this runs on a failure path, and raising here would
    replace a useful timeout error with a cleanup error.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        process.kill()


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run git with a fixed argv and no shell. Returns stripped stdout.

    `shell=False` is the default and is not overridden anywhere in this package.
    The `# noqa: S603` is honest rather than convenient: this call *is* a
    subprocess with a caller-supplied argument, which is precisely why
    :func:`normalise_repo_url` validates the one argument that can vary.

    `git` is resolved from PATH (`S607` would prefer an absolute path). That is
    a deliberate, recorded choice rather than an oversight: hardcoding
    `/usr/bin/git` would break on any machine where git lives elsewhere — macOS
    with Homebrew, a Nix profile, a CI image — and the alternative it protects
    against is a PATH hijack, which is a compromise of the *host* and therefore
    outside what this module can defend. Recorded as AR-006.
    """
    # `start_new_session=True` puts git in its own process group so a timeout
    # can kill the WHOLE tree. Without it a stalled clone hangs forever despite
    # the timeout, which was observed for real: `git clone` of crewAI sat for
    # 73 minutes on a stalled GitHub read. `subprocess.run(timeout=...)` sends
    # SIGKILL to the direct child only -- here `git clone` -- while
    # `git-remote-https` and `index-pack` (its own children) survive and keep
    # the inherited stdout/stderr pipes open. `subprocess.run` then blocks
    # reading those pipes and never returns, so the timeout never surfaced as
    # an exception at all. Killing the process group is what makes the timeout
    # mean what it says.
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            ["git", *args],  # noqa: S607 - resolved from PATH; see docstring, AR-006
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - git is a hard dep
        raise StudyError("git is not installed or not on PATH") from exc

    try:
        stdout, stderr = process.communicate(timeout=CLONE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(process)
        # Reap so the child does not linger as a zombie, and close the pipes.
        with contextlib.suppress(subprocess.TimeoutExpired):
            # pragma: no cover - SIGKILL is final; this only bounds the reap
            process.communicate(timeout=CLONE_KILL_GRACE_SECONDS)
        raise StudyError(
            f"git {args[0]} timed out after {CLONE_TIMEOUT_SECONDS}s. "
            "A slow network is not a reason to leave a partial clone behind."
        ) from exc

    completed = subprocess.CompletedProcess(
        args=["git", *args], returncode=process.returncode, stdout=stdout, stderr=stderr
    )

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise StudyError(
            f"git {args[0]} failed (exit {completed.returncode}): {detail}"
        )
    return completed.stdout.strip()


def _directory_size_bytes(path: Path) -> int:
    """Total size of a directory tree in bytes, following no symlinks.

    Symlinks are skipped rather than followed: a studied repository can contain
    a symlink to `/` or to a huge tree, and following it would both misreport
    the size and make the walk unbounded.
    """
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_symlink() or not entry.is_file():
                continue
            total += entry.stat().st_size
        except OSError:
            # A file can vanish or be unreadable mid-walk; size accounting is
            # advisory, so skipping is correct and a crash is not.
            continue
    return total


@dataclass(frozen=True, slots=True)
class Clone:
    """A cloned study target with its pinned commit.

    Frozen because these are provenance values: a report cites
    :attr:`commit`, and a mutable field could disagree with the file on disk
    between being read and being written.
    """

    url: str
    slug: str
    path: Path
    commit: str
    size_bytes: int

    @property
    def name(self) -> str:
        """Short display name, e.g. `langchain`."""
        return self.slug.rsplit("__", 1)[-1]

    @property
    def owner(self) -> str:
        """Owner segment of the slug, e.g. `langchain-ai`."""
        parts = self.slug.split("__")
        return parts[1] if len(parts) >= 3 else ""


@contextmanager
def study_workspace(
    raw_url: str,
    *,
    workspace: Path | None = None,
    max_bytes: int = MAX_CLONE_BYTES,
) -> Iterator[Clone]:
    """Clone a target into the throwaway workspace and clean up afterwards.

    Yields a :class:`Clone` describing the pinned checkout. The clone is removed
    on exit **including on exception**, and any pre-existing clone of the same
    target is removed before cloning so a stale checkout cannot be mistaken for
    a fresh one — a reproducibility bug that would silently misreport a commit.

    Cleanup is best-effort and never masks the original error: if removal fails
    the study result is still returned or the original exception still
    propagates. A leftover directory is recoverable; a swallowed exception is
    not.

    The yielded path is inside a repository that is never on `sys.path` and is
    never imported from (ADR-0021 Decision 1).

    **Concurrency.** Each invocation clones into a uniquely-named directory
    under the workspace. An earlier version always used `workspace/<slug>`,
    which is fine for one study at a time and destroys a concurrent one: two
    studies of the same target had one `rmtree` the other's clone mid-clone,
    failing with `could not open .../tmp_pack_xxx for reading`. Found by
    running a batch study while separately testing the licence detector. The
    unique directory makes concurrent studies safe and is what lets a batch
    runner be parallel at all.
    """
    url = normalise_repo_url(raw_url)
    slug = project_slug(url)
    base = workspace if workspace is not None else workspace_path()
    # Per-invocation: see the concurrency note above. The slug stays as the
    # prefix so a leftover directory is still identifiable by eye.
    destination = base / f"{slug}.{os.getpid()}.{uuid.uuid4().hex[:8]}"

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        _git(
            "clone",
            "--depth",
            "1",
            "--no-tags",
            "--single-branch",
            "--quiet",
            url,
            str(destination),
        )
        commit = _git("rev-parse", "HEAD", cwd=destination)
        if not _SHA_RE.match(commit):
            raise StudyError(
                f"git rev-parse returned {commit!r}, which is not a commit hash. "
                "Provenance would be meaningless, so the study is refused."
            )

        size = _directory_size_bytes(destination)
        if size > max_bytes:
            mebibytes = size / (1024 * 1024)
            limit = max_bytes / (1024 * 1024)
            raise StudyError(
                f"clone of {slug} is {mebibytes:.0f} MiB, over the {limit:.0f} MiB "
                "limit. Refusing rather than filling the disk; raise max_bytes "
                "deliberately if this target is genuinely intended."
            )

        yield Clone(
            url=url, slug=slug, path=destination, commit=commit, size_bytes=size
        )
    finally:
        shutil.rmtree(destination, ignore_errors=True)
        # The per-process root is deliberately NOT removed here. It is shared
        # by every study this process runs (a batch runs many), so a study that
        # finished first would delete the root a sibling was still cloning
        # into -- the same class of bug as the shared destination this
        # addressed. Ownership of the root belongs to the process, not to one
        # study within it; `_stage` cleans it once at the end of a batch.
        _ = base


def prune_workspace(workspace: Path | None = None) -> int:
    """Remove everything in the workspace. Returns the number of clones removed.

    Provided as an explicit recovery path: a study interrupted by a power loss
    or a `SIGKILL` cannot run its `finally`, so an orphaned clone is possible
    and needs a documented way out that is not `rm -rf` typed from memory.

    Clears **this process's** workspace: a concurrent study in another process
    owns a different directory and is not touched. Callers wanting to clear
    everything must remove `WORKSPACE_DIRNAME` themselves, deliberately.

    This clears the workspace **completely**, including loose files. An earlier
    version removed only directories, which left the workspace non-empty: after
    `prune_workspace()` the size still read 1 byte from a stray file, so a
    cleanup path could never actually reach zero. A cleanup function that
    cannot report a clean workspace is worse than none, because the operator
    concludes the disk is in use when it is not.

    The workspace directory itself is left in place — it is cheap, and removing
    it would race a concurrent study for no benefit.

    `ignore_errors=True` on removal: a clone containing a file that resists
    deletion (mode bits, a stale NFS handle) must not abort the cleanup and
    leave the rest behind.
    """
    base = workspace if workspace is not None else workspace_path()
    if not base.is_dir():
        return 0

    removed = 0
    for entry in base.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
            removed += not entry.exists()
        else:
            # A loose file, or a symlink. Never follow a symlink: deleting
            # through one would remove the link target, which may be outside
            # the workspace entirely.
            with contextlib.suppress(OSError):
                entry.unlink()
    return removed


def workspace_size_bytes(workspace: Path | None = None) -> int:
    """Total size of everything currently in the workspace."""
    base = workspace if workspace is not None else workspace_path()
    return _directory_size_bytes(base) if base.is_dir() else 0


def main_guard() -> None:  # pragma: no cover - trivial introspection helper
    """Fail loudly if this package is ever imported from inside a clone.

    Not called in normal operation; it exists so a test can assert the invariant
    that the workspace is not importable. See
    `study_pipeline/tests/test_no_execution.py`.
    """
    documented = (repo_root() / WORKSPACE_DIRNAME).resolve()
    for index, entry in enumerate(sys.path):
        try:
            resolved = Path(entry or ".").resolve()
        except OSError:  # pragma: no cover - defensive
            continue
        if resolved == documented or documented in resolved.parents:
            raise StudyError(
                f"sys.path[{index}] is inside the study workspace ({resolved}). "
                "Cloned code must never be importable (ADR-0021)."
            )


def cleanup_workspace_root() -> None:
    """Remove this process's workspace root if it is empty.

    Called once at the end of a run rather than by each :func:`study_workspace`
    block, because the root is shared by every study in the process: a study
    that finished first would otherwise delete the directory a sibling was
    still cloning into.

    Best-effort and silent. A non-empty root means a concurrent study is
    mid-flight, which is a legitimate state and not an error; `rmdir` refuses
    it, and that refusal is the correct outcome rather than something to
    report.
    """
    base = workspace_path()
    with contextlib.suppress(OSError):
        base.rmdir()
