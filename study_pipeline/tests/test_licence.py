"""Unit tests for study_pipeline.licence — declared-metadata licence detection.

The risk this module manages is not crashing; it is **stating a licence that is
wrong**, which is a legal exposure rather than a display bug. So the tests are
organised around the refusals as much as the detections:

  * a file that names no licence must yield nothing, not a guess;
  * disagreeing declarations must be reported as a conflict, not resolved;
  * a copyright-only first line must not be read as a licence;
  * the licence body must NOT be phrase-searched.

That last one is a real correction. While building this detector the author
believed `microsoft/autogen` was MIT and its `LICENSE` file mislabelled. The
file was right and the belief was wrong — it genuinely is CC-BY-4.0. A detector
that phrase-searched the body would have been "corrected" to agree with a faulty
memory. The test below pins the behaviour that prevents that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from study_pipeline.licence import (
    LICENCE_FILENAMES,
    Licence,
    LicenceConfidence,
    _reuse_licences,
    _spdx_from_header,
    _spdx_from_package_json,
    _spdx_from_pyproject,
    detect_licence,
)

MIT_TEXT = """MIT License

Copyright (c) 2024 Someone

Permission is hereby granted, free of charge, to any person obtaining a copy
"""

APACHE_TEXT = """                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/
"""

BSD_TEXT = """BSD 3-Clause License

Copyright (c) 2024, Someone
All rights reserved.
"""


def _write(root: Path, relative: str, content: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Declared metadata — the strongest evidence
# ---------------------------------------------------------------------------


def test_pep639_string_license(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = "MIT"\n',
    )
    result = detect_licence(tmp_path)
    assert result.spdx_id == "MIT"
    assert result.confidence is LicenceConfidence.DECLARED
    assert result.determined


def test_legacy_table_license_text(tmp_path: Path) -> None:
    # PEP 621's original table form, still widely used.
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = {text = "Apache-2.0"}\n',
    )
    assert detect_licence(tmp_path).spdx_id == "Apache-2.0"


def test_legacy_table_license_file_yields_nothing(tmp_path: Path) -> None:
    # `{file = "LICENSE"}` names a file, not an identifier. Reading the file is
    # a separate step; inventing an id from the filename would be a guess.
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = {file = "LICENSE"}\n',
    )
    _write(tmp_path, "LICENSE", MIT_TEXT)
    result = detect_licence(tmp_path)
    assert result.confidence is not LicenceConfidence.DECLARED


def test_dual_licence_expression_is_kept_whole(tmp_path: Path) -> None:
    # Reporting only the first term of `MIT OR Apache-2.0` would misstate a
    # dual licence as a single one.
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = "MIT OR Apache-2.0"\n',
    )
    assert detect_licence(tmp_path).spdx_id == "MIT OR Apache-2.0"


def test_package_json_license(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name":"x","license":"ISC"}')
    result = detect_licence(tmp_path)
    assert result.spdx_id == "ISC"
    assert result.confidence is LicenceConfidence.DECLARED


def test_package_json_deprecated_licenses_array(tmp_path: Path) -> None:
    _write(
        tmp_path, "package.json", '{"name":"x","licenses":[{"type":"BSD-2-Clause"}]}'
    )
    assert detect_licence(tmp_path).spdx_id == "BSD-2-Clause"


def test_private_monorepo_root_declares_nothing(tmp_path: Path) -> None:
    # vercel/ai is a real instance: the root package.json is {"private": true}
    # and the licences live in per-package manifests.
    _write(tmp_path, "package.json", '{"private":true,"name":"monorepo"}')
    _write(tmp_path, "LICENSE", MIT_TEXT)
    result = detect_licence(tmp_path)
    assert result.spdx_id == "MIT"
    assert result.confidence is LicenceConfidence.HEADER


# ---------------------------------------------------------------------------
# Conflicts — reported, never resolved
# ---------------------------------------------------------------------------


def test_disagreeing_declarations_are_a_conflict(tmp_path: Path) -> None:
    """Picking one of several disagreeing licences is how a report lies.

    `licensee` makes the same choice: it reports no licence rather than
    choosing among matches that do not agree.
    """
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = "MIT"\n',
    )
    _write(tmp_path, "package.json", '{"name":"x","license":"Apache-2.0"}')
    result = detect_licence(tmp_path)

    assert result.spdx_id == "", "a conflict must not resolve to one identifier"
    assert set(result.conflicts) == {"MIT", "Apache-2.0"}
    assert "CONFLICT" in result.summary
    assert "needs review" in result.summary


def test_agreement_is_not_a_conflict(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = "MIT"\n',
    )
    _write(tmp_path, "package.json", '{"name":"x","license":"MIT"}')
    result = detect_licence(tmp_path)
    assert result.spdx_id == "MIT"
    assert result.conflicts == ()


# ---------------------------------------------------------------------------
# SPDX tags and REUSE
# ---------------------------------------------------------------------------


def test_spdx_tag_in_licence_file(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSE", "SPDX-License-Identifier: MPL-2.0\n\nsome text\n")
    result = detect_licence(tmp_path)
    assert result.spdx_id == "MPL-2.0"
    assert result.confidence is LicenceConfidence.TAGGED


def test_declared_metadata_beats_a_tag(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\nversion="1"\nlicense = "MIT"\n',
    )
    _write(tmp_path, "LICENSE", "SPDX-License-Identifier: Apache-2.0\n")
    # Both are present and agree in being explicit; the declared field wins.
    assert detect_licence(tmp_path).spdx_id == "MIT"


def test_reuse_licences_directory(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSES/Apache-2.0.txt", APACHE_TEXT)
    result = detect_licence(tmp_path)
    assert result.spdx_id == "Apache-2.0"
    assert result.confidence is LicenceConfidence.REUSE_FILENAME


def test_reuse_directory_ignores_non_spdx_names(tmp_path: Path) -> None:
    (tmp_path / "LICENSES").mkdir()
    (tmp_path / "LICENSES" / "README").write_text("about licences")
    assert _reuse_licences(tmp_path) == ()


def test_reuse_directory_is_optional(tmp_path: Path) -> None:
    assert _reuse_licences(tmp_path) == ()


# ---------------------------------------------------------------------------
# Title-line detection — exact allowlist only
# ---------------------------------------------------------------------------


def test_mit_title_line(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSE", MIT_TEXT)
    result = detect_licence(tmp_path)
    assert result.spdx_id == "MIT"
    assert result.confidence is LicenceConfidence.HEADER


def test_apache_title_line(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSE", APACHE_TEXT)
    assert detect_licence(tmp_path).spdx_id == "Apache-2.0"


def test_bsd_title_line(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSE", BSD_TEXT)
    assert detect_licence(tmp_path).spdx_id == "BSD-3-Clause"


def test_creative_commons_title_line(tmp_path: Path) -> None:
    # autogen's real first line.
    _write(
        tmp_path,
        "LICENSE",
        "Attribution 4.0 International\n\n====\n\nCreative Commons Corporation...\n",
    )
    assert detect_licence(tmp_path).spdx_id == "CC-BY-4.0"


def test_copyright_first_line_is_not_a_licence(tmp_path: Path) -> None:
    # crewAI's real first line. A copyright notice does not state a licence,
    # and treating it as one would be a fabrication.
    _write(
        tmp_path, "LICENSE", "Copyright (c) 2025 crewAI, Inc.\n\nAll rights reserved.\n"
    )
    result = detect_licence(tmp_path)
    assert result.spdx_id == ""
    assert result.confidence is LicenceConfidence.UNIDENTIFIED


def test_title_line_search_is_limited_to_the_first_line(tmp_path: Path) -> None:
    """A licence body that MENTIONS another licence must not override its title.

    This is the behavioural guard against phrase-searching the whole file.
    """
    body = (
        "Copyright (c) 2024 Someone\n\n"
        "This project was previously released under the MIT License.\n"
        "It is now distributed under the terms below.\n"
    )
    _write(tmp_path, "LICENSE", body)
    assert detect_licence(tmp_path).spdx_id == ""


def test_autogen_case_is_not_phrase_matched(tmp_path: Path) -> None:
    """The correction that shaped this module.

    The author believed autogen was MIT and its LICENSE mislabelled; the file
    genuinely IS CC-BY-4.0. A whole-file phrase match ("Permission is hereby
    granted") would also hit BSD and MIT-0, so it cannot distinguish them
    either. Only an exact title-line allowlist is trustworthy.
    """
    _write(
        tmp_path,
        "LICENSE",
        "Attribution 4.0 International\n\nCreative Commons Corporation is not a law firm\n",
    )
    result = detect_licence(tmp_path)
    assert result.spdx_id == "CC-BY-4.0", "the file is authoritative"
    assert "MIT" not in result.spdx_id


@pytest.mark.parametrize(
    ("first_line", "expected"),
    [
        ("MIT License", "MIT"),
        ("The MIT License", "MIT"),
        ("Apache License", "Apache-2.0"),
        ("GNU GENERAL PUBLIC LICENSE", "GPL-3.0"),
        ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
        ("Mozilla Public License Version 2.0", "MPL-2.0"),
        ("ISC License", "ISC"),
        ("The Unlicense", "Unlicense"),
        ("", ""),
        ("Some other text", ""),
    ],
)
def test_header_allowlist(tmp_path: Path, first_line: str, expected: str) -> None:
    path = tmp_path / "LICENSE"
    path.write_text(f"{first_line}\n\nbody\n", encoding="utf-8")
    assert _spdx_from_header(path)[0] == expected


def test_header_of_a_missing_file(tmp_path: Path) -> None:
    assert _spdx_from_header(tmp_path / "nope") == ("", "")


def test_header_is_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "LICENSE"
    path.write_text("mit license\n\nbody\n", encoding="utf-8")
    assert _spdx_from_header(path)[0] == "MIT"


def test_header_ignores_leading_comment_markers(tmp_path: Path) -> None:
    path = tmp_path / "LICENSE"
    path.write_text("# MIT License\n\nbody\n", encoding="utf-8")
    assert _spdx_from_header(path)[0] == "MIT"


# ---------------------------------------------------------------------------
# Absence and unidentified
# ---------------------------------------------------------------------------


def test_no_licence_at_all(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# hi\n")
    result = detect_licence(tmp_path)
    assert result.spdx_id == ""
    assert result.confidence is LicenceConfidence.ABSENT
    assert not result.determined
    assert result.summary == "not declared"


def test_unidentified_licence_file_says_so(tmp_path: Path) -> None:
    _write(tmp_path, "LICENSE", "This software is provided as-is under terms.\n")
    result = detect_licence(tmp_path)
    assert result.confidence is LicenceConfidence.UNIDENTIFIED
    assert "not determined" in result.summary
    assert "LICENSE" in result.summary


def test_licence_file_name_is_recorded(tmp_path: Path) -> None:
    _write(tmp_path, "COPYING", MIT_TEXT)
    assert detect_licence(tmp_path).licence_file == "COPYING"


@pytest.mark.parametrize("name", LICENCE_FILENAMES)
def test_every_known_licence_filename_is_detected(tmp_path: Path, name: str) -> None:
    _write(tmp_path, name, MIT_TEXT)
    assert detect_licence(tmp_path).determined


# ---------------------------------------------------------------------------
# Malformed input never crashes
# ---------------------------------------------------------------------------


def test_malformed_pyproject_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "this is not toml [[[")
    _write(tmp_path, "LICENSE", MIT_TEXT)
    assert detect_licence(tmp_path).spdx_id == "MIT"


def test_malformed_package_json_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", "{not json")
    _write(tmp_path, "LICENSE", MIT_TEXT)
    assert detect_licence(tmp_path).spdx_id == "MIT"


def test_non_string_license_values_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name":"x","license":42}')
    assert detect_licence(tmp_path).spdx_id == ""


def test_empty_pyproject_yields_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "")
    assert _spdx_from_pyproject(tmp_path) == ()


def test_package_json_array_at_root_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", "[1,2,3]")
    assert _spdx_from_package_json(tmp_path) == ()


def test_empty_project_table_yields_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", '[project]\nname="x"\n')
    assert _spdx_from_pyproject(tmp_path) == ()


# ---------------------------------------------------------------------------
# Real repository — the detector must agree with a known case
# ---------------------------------------------------------------------------


def test_this_repository_is_apache_2() -> None:
    """This repository declares Apache-2.0 (ADR-0002, human-decided).

    A detector that disagreed with a human-verified fact would be wrong, and
    this is the one case where the correct answer is independently known.
    """
    root = Path(__file__).resolve().parent.parent.parent
    result = detect_licence(root)
    assert result.spdx_id == "Apache-2.0"
    assert result.confidence is LicenceConfidence.DECLARED


def test_licence_dataclass_is_frozen() -> None:
    import dataclasses

    licence = Licence("MIT", LicenceConfidence.DECLARED, ("x",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        licence.spdx_id = "GPL-3.0"  # type: ignore[misc]
