"""Unit tests for scripts/check_licenses.py.

This gate decides whether a dependency is acceptable, so its failure modes are
asymmetric and both are tested:

  * it must NOT reject a permissively licensed dependency — a false positive
    blocks every future dependency addition;
  * it must reject a disallowed one, AND treat an unresolvable licence as a
    failure rather than a warning. "We could not determine the licence" and
    "the licence is fine" must never be indistinguishable; that equivalence is
    exactly what an allow-list exists to prevent.

The normaliser is tested against the real spelling variance found in the wild,
including the case that actually occurred here: three packages declare only the
clause-agnostic `License :: OSI Approved :: BSD License`, resolving which
required reading the licence text the package ships.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_licenses import (  # noqa: E402
    ALLOWED,
    UNKNOWN_MARKERS,
    _from_classifiers,
    _from_license_file,
    _installed_distributions,
    _normalise,
    main,
)

# ---------------------------------------------------------------------------
# Normalisation — the spelling variance that exists in the wild
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MIT", "mit"),
        ("MIT License", "mit"),
        ("The MIT License", "mit"),
        ("Apache License 2.0", "apache-2.0"),
        ("Apache-2.0", "apache-2.0"),
        ("Apache Software License", "apache-2.0"),
        ("ISC", "isc"),
        ("ISC License", "isc"),
        ("Unlicense", "unlicense"),
        ("CC0-1.0", "cc0-1.0"),
        ("Python Software Foundation License", "psf-2.0"),
        ("PSF-2.0", "psf-2.0"),
    ],
)
def test_normalise_folds_common_spellings(raw: str, expected: str) -> None:
    assert _normalise(raw) == expected


def test_normalise_handles_the_parenthetical_mpl_form() -> None:
    # A real declaration found on this machine:
    #   "Mozilla Public License 2.0 (MPL 2.0)"
    assert _normalise("Mozilla Public License 2.0 (MPL 2.0)") == "mpl-2.0"


def test_normalise_distinguishes_bsd_clause_counts() -> None:
    assert _normalise("BSD 3-Clause License") == "bsd-3-clause"
    assert _normalise("BSD 2-Clause License") == "bsd-2-clause"
    assert _normalise("3-Clause BSD License") == "bsd-3-clause"


def test_normalise_refuses_to_guess_a_clause_count() -> None:
    # The case that actually occurred: `License: None` plus the classifier
    # `License :: OSI Approved :: BSD License`. Guessing permissively is the
    # failure an allow-list exists to prevent, so this must NOT resolve.
    assert _normalise("BSD License") == "bsd-unknown"
    assert _normalise("BSD") == "bsd-unknown"


def test_bsd_unknown_is_not_on_the_allow_list() -> None:
    assert "bsd-unknown" not in ALLOWED


def test_unknown_markers_include_the_empty_string() -> None:
    assert "" in UNKNOWN_MARKERS


# ---------------------------------------------------------------------------
# Classifier extraction
# ---------------------------------------------------------------------------


class _Metadata:
    """Minimal stand-in for importlib.metadata's Message object."""

    def __init__(self, classifiers: list[str] | None) -> None:
        self._classifiers = classifiers

    def get_all(self, key: str) -> list[str] | None:
        return self._classifiers


def test_from_classifiers_extracts_the_licence() -> None:
    metadata = _Metadata(["License :: OSI Approved :: MIT License"])
    assert _from_classifiers(metadata) == "MIT License"


def test_from_classifiers_ignores_non_licence_classifiers() -> None:
    metadata = _Metadata(["Programming Language :: Python :: 3"])
    assert _from_classifiers(metadata) == ""


def test_from_classifiers_handles_no_classifiers() -> None:
    assert _from_classifiers(_Metadata(None)) == ""


def test_from_classifiers_handles_an_object_without_get_all() -> None:
    class Bare:
        pass

    assert _from_classifiers(Bare()) == ""


# ---------------------------------------------------------------------------
# Reading the shipped licence text — the evidence path
# ---------------------------------------------------------------------------


class _Dist:
    """A fake distribution exposing only what _from_license_file uses."""

    def __init__(self, directory: Path | None, names: list[str]) -> None:
        self._directory = directory
        self.files = [Path(name) for name in names]

    def locate_file(self, relative: Path) -> Path:
        # With no directory the path cannot exist, which is what the checker's
        # own OSError handling is there to survive. Raising the same error the
        # real implementation would is more faithful than asserting here.
        if self._directory is None:
            raise FileNotFoundError(relative)
        return self._directory / relative


def _licence_dist(tmp_path: Path, body: str, name: str = "LICENSE") -> _Dist:
    (tmp_path / name).write_text(body, encoding="utf-8")
    return _Dist(tmp_path, [name])


BSD3 = (
    "Redistribution and use in source and binary forms, with or without\n"
    "modification, are permitted provided that the following conditions are met:\n"
    "1. Redistributions of source code must retain the above copyright notice.\n"
    "2. Redistributions in binary form must reproduce the above copyright notice.\n"
    "3. Neither the name of the copyright holder nor the names of its\n"
    "   contributors may be used to endorse or promote products derived.\n"
)

BSD2 = (
    "Redistribution and use in source and binary forms, with or without\n"
    "modification, are permitted provided that the following conditions are met:\n"
    "1. Redistributions of source code must retain the above copyright notice.\n"
    "2. Redistributions in binary form must reproduce the above copyright notice.\n"
)

MIT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    'of this software and associated documentation files (the "Software").\n'
)


def test_from_license_file_detects_bsd_3_clause(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, BSD3)
    assert _from_license_file(dist) == "BSD 3-Clause License"


def test_from_license_file_detects_bsd_2_clause(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, BSD2)
    assert _from_license_file(dist) == "BSD 2-Clause License"


def test_from_license_file_detects_mit(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, MIT)
    assert _from_license_file(dist) == "MIT License"


def test_from_license_file_detects_apache(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, "Apache License\nVersion 2.0, January 2004\n")
    assert _from_license_file(dist) == "Apache License 2.0"


def test_from_license_file_detects_mpl(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, "Mozilla Public License Version 2.0\n")
    assert _from_license_file(dist) == "Mozilla Public License 2.0"


def test_from_license_file_returns_empty_for_unfamiliar_text(tmp_path: Path) -> None:
    # Deliberately narrow: an unrecognised licence must stay UNKNOWN rather
    # than be assumed permissive.
    dist = _licence_dist(tmp_path, "This software is provided under terms.\n")
    assert _from_license_file(dist) == ""


def test_from_license_file_ignores_a_missing_file() -> None:
    dist = _Dist(None, ["LICENSE"])
    assert _from_license_file(dist) == ""


def test_from_license_file_skips_non_licence_files() -> None:
    dist = _Dist(None, ["README.md", "setup.py"])
    assert _from_license_file(dist) == ""


def test_from_license_file_accepts_copying(tmp_path: Path) -> None:
    dist = _licence_dist(tmp_path, BSD3, name="COPYING")
    assert _from_license_file(dist) == "BSD 3-Clause License"


# ---------------------------------------------------------------------------
# The real environment
# ---------------------------------------------------------------------------


def test_installed_distributions_are_discovered() -> None:
    packages = _installed_distributions()
    assert packages, "the virtualenv must contain packages"
    for name, version, licence in packages:
        assert isinstance(name, str) and name
        assert isinstance(version, str) and version
        assert isinstance(licence, str)


def test_the_repository_environment_passes() -> None:
    # The end-to-end assertion: whatever is installed must be acceptable.
    assert main(["--quiet"]) == 0


def test_every_allowed_entry_is_normalised_already() -> None:
    # ALLOWED holds normalised keys, so a raw spelling in the set would never
    # match anything. This catches that class of typo.
    for value in ALLOWED:
        assert _normalise(value) == value, value


# ---------------------------------------------------------------------------
# main() output modes
# ---------------------------------------------------------------------------


def test_main_json_mode_emits_parseable_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["denied"] == []
    assert payload["unknown"] == []
    assert payload["checked"] > 0


def test_main_reports_success_quietly_only_when_quiet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""

    assert main([]) == 0
    assert "all licences on the allow-list" in capsys.readouterr().out


def test_main_fails_and_explains_for_a_disallowed_licence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_licenses

    fake: list[tuple[str, str, str]] = [("evil-pkg", "1.0", "GPL-3.0-only")]
    monkeypatch.setattr(check_licenses, "_installed_distributions", lambda: fake)

    assert check_licenses.main(["--quiet"]) == 1
    stderr = capsys.readouterr().err
    assert "evil-pkg" in stderr
    assert "not on the allow-list" in stderr


def test_main_fails_for_an_unknown_licence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_licenses

    fake: list[tuple[str, str, str]] = [("mystery", "1.0", "")]
    monkeypatch.setattr(check_licenses, "_installed_distributions", lambda: fake)

    # Unverifiable is unacceptable, not acceptable-by-default.
    assert check_licenses.main(["--quiet"]) == 1
    assert "Unverifiable" in capsys.readouterr().err


def test_main_handles_an_empty_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_licenses

    monkeypatch.setattr(check_licenses, "_installed_distributions", list)
    assert check_licenses.main([]) == 0
    assert "nothing to check" in capsys.readouterr().out


def test_main_json_mode_fails_for_a_denied_licence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import check_licenses

    fake: list[tuple[str, str, str]] = [("evil-pkg", "1.0", "AGPL-3.0")]
    monkeypatch.setattr(check_licenses, "_installed_distributions", lambda: fake)

    assert check_licenses.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["denied"][0]["name"] == "evil-pkg"


def test_allow_list_contains_only_permissive_families() -> None:
    # A guard against a future editor adding a copyleft family by accident:
    # the allow-list is a licensing decision (charter §22), not a convenience.
    assert "gpl-3.0" not in ALLOWED
    assert "agpl-3.0" not in ALLOWED
    assert "apache-2.0" in ALLOWED
    assert "mit" in ALLOWED


def _unused(value: Any) -> None:  # pragma: no cover - typing helper
    del value
