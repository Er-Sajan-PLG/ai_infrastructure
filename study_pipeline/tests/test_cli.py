"""Unit tests for the study pipeline CLI (study_pipeline.__main__).

The CLI is thin by design (ADR-0021 Decision 4), so these tests are about its
*contract* rather than its logic:

  * exit codes distinguish "studied and found nothing" from "did not study";
  * a missing taxonomy refuses rather than classifying against a fallback;
  * argument handling is right without needing to clone anything;
  * `--dry-run` writes no file.

One test runs the real end-to-end path against a git repository created on
disk, so the CLI is exercised through `main()` without network access. A
separate network-marked test does the same against a real GitHub repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from study_pipeline import __main__ as cli
from study_pipeline.workspace import _git

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def test_requires_at_least_one_url() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_parser_accepts_multiple_urls() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["https://github.com/a/b", "https://github.com/c/d"])
    assert len(args.urls) == 2


def test_parser_defaults_are_off() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["https://github.com/a/b"])
    assert args.dry_run is False
    assert args.quiet is False


def test_parser_accepts_dry_run() -> None:
    parser = cli._build_parser()
    assert parser.parse_args(["--dry-run", "https://github.com/a/b"]).dry_run is True


def test_parser_accepts_quiet() -> None:
    parser = cli._build_parser()
    assert parser.parse_args(["--quiet", "https://github.com/a/b"]).quiet is True


def test_version_flag_exits_zero() -> None:
    with pytest.raises(SystemExit) as caught:
        cli._build_parser().parse_args(["--version"])
    assert caught.value.code == 0


def test_help_mentions_the_no_execution_guarantee() -> None:
    # The guarantee is the single most important thing a user should know.
    text = cli._build_parser().format_help()
    assert "never executed" in text
    assert "ADRs" not in text  # not a placeholder


def test_usage_mentions_where_reports_go() -> None:
    text = cli._build_parser().format_help()
    assert "study_pipeline/studied_repos/" in text


def test_exit_codes_are_distinct() -> None:
    # A caller scripting this must be able to tell the cases apart.
    assert len({cli.EXIT_OK, cli.EXIT_STUDY_FAILED, cli.EXIT_USAGE}) == 3


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_refuses_an_invalid_url_without_crashing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.study_one("file:///etc/passwd", dry_run=True, quiet=True)
    assert code == cli.EXIT_STUDY_FAILED
    assert "ERROR" in capsys.readouterr().err


def test_refuses_a_url_with_option_injection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = cli.study_one("--upload-pack=evil", dry_run=True, quiet=True)
    assert code == cli.EXIT_STUDY_FAILED
    assert "ERROR" in capsys.readouterr().err


def test_refuses_an_empty_url(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.study_one("", dry_run=True, quiet=True) == cli.EXIT_STUDY_FAILED
    assert "ERROR" in capsys.readouterr().err


def test_missing_taxonomy_refuses_rather_than_guessing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Classification needs the real TAXONOMY.md.

    Classifying against a hardcoded fallback is the bug this pipeline already
    fixed once — a constant drifted from the file and produced confident,
    authoritative, wrong output. Refusing is the correct behaviour.
    """
    monkeypatch.setattr(cli, "repo_root", lambda: tmp_path)
    code = cli.study_one("https://github.com/psf/requests", dry_run=True, quiet=True)
    assert code == cli.EXIT_STUDY_FAILED
    assert "TAXONOMY.md" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# End-to-end against a local git repository (no network)
# ---------------------------------------------------------------------------


@pytest.fixture
def local_repo(tmp_path: Path) -> str:
    """A real git repository on disk that LOOKS like an AI infra project.

    Using a real repository rather than mocks means the CLI exercises the real
    clone path: `git clone`, `rev-parse`, the size guard, and cleanup.
    """
    origin = tmp_path / "origin"
    (origin / "src" / "pkg" / "retrieval").mkdir(parents=True)
    (origin / "src" / "pkg" / "retrieval" / "__init__.py").write_text("")
    (origin / "src" / "pkg" / "retrieval" / "index.py").write_text("x = 1\n")
    (origin / "src" / "pkg" / "tools").mkdir(parents=True)
    (origin / "src" / "pkg" / "tools" / "__init__.py").write_text("")
    (origin / "src" / "pkg" / "tools" / "registry.py").write_text("x = 1\n")
    (origin / "pyproject.toml").write_text(
        '[project]\nname = "fake"\nversion = "1"\ndependencies = ["chromadb"]\n'
    )
    (origin / "README.md").write_text("# fake\n")

    _git("init", "--quiet", "--initial-branch=main", cwd=origin)
    _git("config", "user.email", "t@example.com", cwd=origin)
    _git("config", "user.name", "T", cwd=origin)
    _git("add", "-A", cwd=origin)
    _git("commit", "--quiet", "-m", "initial", cwd=origin)
    return f"file://{origin}"


def test_local_clone_is_refused_by_the_host_allowlist(
    local_repo: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # A file:// URL is refused even when it IS a real repository. This is the
    # injection guard working, not a test limitation: the pipeline studies
    # public repositories over HTTPS only.
    assert cli.study_one(local_repo, dry_run=True, quiet=True) == cli.EXIT_STUDY_FAILED
    assert "ERROR" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Network-marked end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_studies_a_real_repository_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full CLI against a real GitHub repository.

    Marked `network` so the default gate run stays offline; run with
    `make test-network`. Uses a redirected repo root so it never writes into
    the real tree, and asserts the dry-run path wrote nothing.
    """
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "TAXONOMY.md").write_text((REPO_ROOT / "TAXONOMY.md").read_text())
    monkeypatch.setattr(cli, "repo_root", lambda: sandbox)

    code = cli.study_one("https://github.com/psf/requests", dry_run=True, quiet=True)
    output = capsys.readouterr().out

    assert code == cli.EXIT_OK
    assert "## Provenance" in output
    assert "| `code_reused` | `false` |" in output
    assert "requests.md" not in output, "--dry-run must not print a written path"
    assert not list(
        (sandbox / "study_pipeline").glob("**/*.md")
    ), "--dry-run wrote a report file"


@pytest.mark.network
def test_written_report_lands_in_studied_repos(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Redirect the repo root so the test never writes into the real tree.
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    (sandbox / "TAXONOMY.md").write_text((REPO_ROOT / "TAXONOMY.md").read_text())
    monkeypatch.setattr(cli, "repo_root", lambda: sandbox)

    code = cli.study_one("https://github.com/psf/requests", dry_run=False, quiet=True)
    assert code == cli.EXIT_OK
    written = list((sandbox / "study_pipeline" / "studied_repos").glob("*.md"))
    assert len(written) == 1
    assert written[0].name == "requests.md"
    capsys.readouterr()


def test_module_runs_as_a_subprocess() -> None:
    """`python -m study_pipeline` must work, since `make study` uses it.

    Uses `--help` so nothing is cloned and no network is touched.
    """
    result = subprocess.run(
        [sys.executable, "-m", "study_pipeline", "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0
    assert "REPO_URL" in result.stdout
