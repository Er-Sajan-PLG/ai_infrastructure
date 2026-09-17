"""Unit tests for scripts/check_commit_msg.py.

The gate these cover validates every commit header in this repository, so a bug
in it is either a permanently-red build or a silently-disabled rule. Both
directions are tested deliberately:

  * a VALID message must exit 0 — a checker that rejects correct input gets
    disabled within a day;
  * an INVALID message must exit non-zero — a checker that accepts it is
    decoration.

The specification is deliberately only partly enforced (header shape plus the
blank line after it), so the tests also pin down what is deliberately allowed:
lower-case violations of the subject, an unusual but permitted type, a long
subject, and git's own `Merge`/`Revert` headers. If someone later tightens the
checker, these tests fail and force the change to be a decision rather than an
accident.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_commit_msg import (  # noqa: E402
    HEADER_RE,
    KNOWN_TYPES,
    SKIP_MARKER,
    check_message,
    main,
)

# Every test below calls check_message directly with a synthetic sha; the sha
# only appears in the finding text.
SHA = "a" * 40


def _errors(message: str) -> list[str]:
    return [f.message for f in check_message(SHA, message) if f.severity == "error"]


def _warnings(message: str) -> list[str]:
    return [f.message for f in check_message(SHA, message) if f.severity == "warning"]


# ---------------------------------------------------------------------------
# Accepted forms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "feat: add a capability",
        "fix(ci): correct the coverage invocation",
        "docs(readme): explain the setup",
        "refactor!: drop the legacy path",
        "chore(deps): bump ruff",
        "test: cover the new checker",
        "build(ci): pin the tools",
        "perf: avoid the extra copy",
        "style: reformat",
        "revert: undo the experiment",
        "ci(actions): pin by sha",
    ],
)
def test_valid_headers_are_accepted(message: str) -> None:
    assert check_message(SHA, message) == []


def test_header_with_blank_line_then_body_is_accepted() -> None:
    message = "feat: add a capability\n\nWhy it was added, at length.\n"
    assert check_message(SHA, message) == []


def test_scope_may_contain_several_areas() -> None:
    # `type(a,b): ...` is rejected by the regex (the scope excludes parens),
    # so the conventional way to span areas is a hyphenated or slashed scope.
    assert check_message(SHA, "fix(ci-parity): align the gate lists") == []


# ---------------------------------------------------------------------------
# Rejected forms
# ---------------------------------------------------------------------------


def test_prose_header_is_an_error() -> None:
    errors = _errors("Added some hardening stuff")
    assert len(errors) == 1
    assert "not `type(scope): description`" in errors[0]


def test_missing_space_after_colon_is_an_error() -> None:
    # "feat:no space" — the spec requires ": " (colon SPACE).
    assert _errors("feat:no space") != []


def test_empty_description_is_an_error() -> None:
    # "feat: " has a trailing space, so the description group is whitespace.
    errors = _errors("feat:   ")
    assert any("description" in e for e in errors)


def test_upper_case_type_is_an_error() -> None:
    errors = _errors("FEAT: shout")
    assert any("lower-case" in e for e in errors)


def test_missing_blank_line_before_body_is_an_error() -> None:
    # The one structural rule enforced: without the blank line the header is no
    # longer the first paragraph, so log views and changelog generators show
    # the wrong text.
    errors = _errors("fix: a thing\nBody immediately after.\n")
    assert len(errors) == 1
    assert "line 2 is not blank" in errors[0]


def test_empty_message_is_an_error() -> None:
    errors = _errors("")
    assert errors == ["commit message is empty"]


# ---------------------------------------------------------------------------
# Deliberately NOT enforced
# ---------------------------------------------------------------------------


def test_unknown_type_is_only_a_warning() -> None:
    # The specification explicitly allows types beyond feat/fix, so rejecting
    # one would enforce a vocabulary the spec does not define.
    findings = check_message(SHA, "wibble: something unusual")
    assert [f.severity for f in findings] == ["warning"]
    assert "not in the conventional set" in findings[0].message


def test_long_subject_is_only_a_warning() -> None:
    # 72 characters is convention, not specification.
    findings = check_message(SHA, f"feat: {'x' * 90}")
    assert [f.severity for f in findings] == ["warning"]
    assert "characters" in findings[0].message


def test_upper_case_subject_is_not_checked() -> None:
    # Lower-case subject is a popular config choice, not a spec rule.
    assert check_message(SHA, "feat: Add The Thing") == []


def test_missing_scope_is_fine() -> None:
    assert check_message(SHA, "feat: no scope here") == []


# ---------------------------------------------------------------------------
# Git's own headers and the escape hatch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        'Merge branch "feature" into main',
        "Merge pull request #1 from someone/branch",
        'Revert "feat: add a capability"',
    ],
)
def test_git_generated_headers_are_exempt(message: str) -> None:
    assert check_message(SHA, message) == []


def test_skip_marker_is_a_warning_not_an_error() -> None:
    findings = check_message(SHA, f"whatever happened here {SKIP_MARKER}")
    assert [f.severity for f in findings] == ["warning"]
    assert SKIP_MARKER in findings[0].message


def test_skip_marker_suppresses_the_shape_error() -> None:
    # The point of the marker: it must let a legitimate exception through.
    assert _errors(f"imported upstream commit {SKIP_MARKER}") == []


# ---------------------------------------------------------------------------
# The regex and the type vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("feat: x", ("feat", None, None)),
        ("feat(core): x", ("feat", "core", None)),
        ("feat!: x", ("feat", None, "!")),
        ("feat(core)!: x", ("feat", "core", "!")),
    ],
)
def test_header_regex_groups(
    header: str, expected: tuple[str, str | None, str | None]
) -> None:
    match = HEADER_RE.match(header)
    assert match is not None
    assert (
        match.group("type"),
        match.group("scope"),
        match.group("breaking"),
    ) == expected


def test_known_types_includes_the_common_conventional_set() -> None:
    for expected in ("feat", "fix", "docs", "chore", "ci", "test", "refactor"):
        assert expected in KNOWN_TYPES


# ---------------------------------------------------------------------------
# main() — the CLI surface the hook and the Makefile actually call
# ---------------------------------------------------------------------------


def test_main_accepts_a_valid_message_file(tmp_path: Path) -> None:
    path = tmp_path / "msg"
    path.write_text("feat: a valid message\n", encoding="utf-8")
    assert main(["--message-file", str(path)]) == 0


def test_main_rejects_an_invalid_message_file(tmp_path: Path) -> None:
    path = tmp_path / "msg"
    path.write_text("not a conventional commit\n", encoding="utf-8")
    assert main(["--message-file", str(path)]) == 1


def test_main_reports_a_missing_message_file(tmp_path: Path) -> None:
    # A hook that silently passes when it cannot read its input is worse than
    # no hook: an unrun check must not look like a passed one.
    assert main(["--message-file", str(tmp_path / "absent")]) == 1


def test_main_strict_turns_a_warning_into_a_failure(tmp_path: Path) -> None:
    path = tmp_path / "msg"
    path.write_text("wibble: an unusual type\n", encoding="utf-8")
    assert main(["--message-file", str(path)]) == 0
    assert main(["--message-file", str(path), "--strict"]) == 1


def test_main_checks_a_commit_range() -> None:
    # HEAD~1..HEAD in this repository is a real, valid commit once the message
    # convention is in use; assert only that the range path runs and returns an
    # int, since history content is not this test's subject.
    result = main(["--range", "HEAD~1..HEAD", "--strict"])
    assert result in (0, 1)


def test_main_fails_on_an_unresolvable_range() -> None:
    # Silently skipping an unreadable range would mean the gate reports success
    # having checked nothing.
    assert main(["--range", "no-such-ref..HEAD"]) == 1
