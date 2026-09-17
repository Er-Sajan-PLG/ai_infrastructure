"""License detection — declared metadata, with refusal where it cannot be sure.

WHY THIS IS DELIBERATELY CONSERVATIVE
-------------------------------------
Track 2B requires each studied repository's licence *at the studied commit*, and
a wrong licence claim is worse than no claim: it is the input to a reuse
decision (charter §22), and getting it wrong is a legal exposure rather than a
display bug.

Every serious implementation in this space is fuzzy-matching against a full
SPDX corpus and still disclaims legal guarantees:

  * [licensee](https://github.com/licensee/licensee) — GitHub's own detector —
    compares against known licences with a Sorensen-Dice coefficient, and
    **refuses to report a licence** when a project has multiple matches that do
    not agree.
  * [go-license-detector](https://github.com/go-enry/go-license-detector) uses
    MinHash plus Levenshtein and states it "does not provide any legal
    guarantees. The intended area of its usage is data mining."
  * The [SPDX matching guidelines](https://spdx.github.io/spdx-spec/v2.3/license-matching-guidelines-and-templates/)
    exist precisely because naive text comparison gets it wrong.

Hand-rolling that in the standard library would produce a detector that is
confidently wrong on the cases that matter. Verified during design, on four
licence texts: a BSD-3-Clause file matched **nothing** under a naive phrase
detector, and MIT's "Permission is hereby granted, free of charge" also appears
in BSD and MIT-0 variants, so a naive detector conflates them.

SO WHAT IS DETECTED
-------------------
Three sources, in descending order of reliability, each recorded with its own
confidence:

1. **SPDX identifier in a manifest** (`license = "MIT"` in `pyproject.toml`,
   `license` in `package.json`). This is *declared* metadata, machine-readable,
   and unambiguous. It is the same class of evidence as `declared_dependencies`
   — the project says so, and the pipeline does not verify it further.
2. **An SPDX-License-Identifier tag** in a licence file's text. Also explicit.
3. **Filename alone** (`LICENSE`, `COPYING`, `LICENSES/MIT`). The filename is
   evidence that a licence exists; it is not evidence of *which* one, except in
   the REUSE convention where files under `LICENSES/` are named by SPDX id.

Prose matching of licence bodies is **not attempted**. When no declared
identifier is found the result records that, rather than guessing — a report
that says "licence not determined; read `LICENSE`" is honest, and one that says
"MIT" because the file contains the word MIT is not.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

#: Filenames treated as a licence file, matching the conventional set
#: `licensee` scores. Order matters only for reporting determinism.
LICENCE_FILENAMES: Final[tuple[str, ...]] = (
    "LICENSE",
    "LICENCE",
    "LICENSE.txt",
    "LICENCE.txt",
    "LICENSE.md",
    "LICENCE.md",
    "COPYING",
    "COPYING.txt",
    "COPYRIGHT",
    "UNLICENSE",
    "NOTICE",
)

#: Filenames that can appear in a `LICENSES/` directory without being a
#: licence. `README` matches the SPDX-identifier shape and must be excluded by
#: name rather than by pattern.
_NON_LICENCE_NAMES: Final[frozenset[str]] = frozenset(
    {"readme", "license", "licence", "notice", "copying", "index", "manifest"}
)

#: An explicit SPDX tag, as recommended by the SPDX spec for source headers and
#: used by REUSE-compliant projects.
_SPDX_TAG_RE: Final = re.compile(
    r"SPDX-License-Identifier:\s*(?P<id>[A-Za-z0-9.+-]+)", re.IGNORECASE
)

#: A plausible SPDX identifier: letters, digits, dots and dashes.
_SPDX_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")

#: An SPDX *expression*: one or more identifiers joined by the operators the
#: spec defines (`OR`, `AND`), optionally with a `WITH <exception>` clause.
#: Needed because a dual licence written as `MIT OR Apache-2.0` is a single
#: correct value, and matching it with the bare-id pattern rejected it --
#: found by a test, not by inspection. Only the operators are accepted, so a
#: free-text string like "see the LICENSE file" is still refused.
_SPDX_EXPRESSION_RE: Final = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.+-]*"
    r"(?:\s+(?:OR|AND|WITH)\s+[A-Za-z0-9][A-Za-z0-9.+-]*)*$"
)


#: How the licence was established. Ordered strongest to weakest.
class LicenceConfidence(Enum):
    """Where a licence claim came from.

    The distinction matters to a reader deciding whether to rely on it: a
    declared SPDX field is a statement by the project, a filename is only
    evidence that a licence file exists.
    """

    #: An SPDX identifier the project declared in machine-readable metadata.
    DECLARED = "declared"
    #: An `SPDX-License-Identifier:` tag written in the licence file itself.
    TAGGED = "tagged"
    #: A REUSE-style `LICENSES/<SPDX-id>` filename.
    REUSE_FILENAME = "reuse-filename"
    #: The licence file's own title line names the licence, matched against an
    #: exact allowlist (`MIT License`, `Apache License`).
    HEADER = "header"
    #: A licence file exists but its identifier was not determined.
    UNIDENTIFIED = "unidentified"
    #: No licence file and no declared identifier.
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class Licence:
    """What is known about a repository's licence, and how it is known."""

    #: SPDX identifier, or `""` when not determined.
    spdx_id: str
    confidence: LicenceConfidence
    #: The evidence path(s) or field(s) that produced the claim.
    evidence: tuple[str, ...]
    #: Repository-relative path to the primary licence file, or `""`.
    licence_file: str = ""
    #: Identifiers found but not agreeing with each other. Non-empty means the
    #: project is multi-licensed or its metadata disagrees, and a single
    #: identifier must not be reported as THE licence.
    conflicts: tuple[str, ...] = ()

    @property
    def determined(self) -> bool:
        """Whether an SPDX identifier was established."""
        return bool(self.spdx_id)

    @property
    def summary(self) -> str:
        """One line for a report table."""
        if self.conflicts:
            return f"CONFLICT: {', '.join(self.conflicts)} — needs review"
        if self.determined:
            return f"{self.spdx_id} ({self.confidence.value})"
        if self.confidence is LicenceConfidence.UNIDENTIFIED:
            return f"not determined — see {self.licence_file or 'LICENSE'}"
        return "not declared"


def _first_licence_file(root: Path) -> Path | None:
    """The primary licence file, if any."""
    for name in LICENCE_FILENAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _reuse_licences(root: Path) -> tuple[str, ...]:
    """SPDX identifiers from a REUSE-style `LICENSES/` directory.

    In that convention each licence is stored under a filename that IS its SPDX
    identifier, so the filename is authoritative rather than a guess.
    """
    directory = root / "LICENSES"
    if not directory.is_dir():
        return ()
    found: list[str] = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        stem = entry.stem
        # A REUSE `LICENSES/` directory may also hold documentation whose name
        # happens to look like an identifier. `README` does: it matches the
        # bare-id pattern, so an exclusion by shape alone is not enough --
        # found by a test. Only names that look like an SPDX id AND are not a
        # known non-licence file are accepted.
        if stem.lower() in _NON_LICENCE_NAMES:
            continue
        if _SPDX_ID_RE.match(stem):
            found.append(stem)
    return tuple(dict.fromkeys(found))


def _spdx_from_pyproject(root: Path) -> tuple[str, ...]:
    """SPDX identifiers declared in `pyproject.toml`.

    Handles both spellings the PEP has used: `license = "MIT"` (PEP 639 string)
    and the older `license = {text = "MIT"}` / `{file = "LICENSE"}` table. A
    `file` reference names a file rather than an identifier, so it yields
    nothing — the file is read separately.
    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return ()
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8", errors="replace"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError):
        return ()

    project = data.get("project")
    if not isinstance(project, dict):
        return ()

    found: list[str] = []
    licence = project.get("license")
    if isinstance(licence, str) and _SPDX_EXPRESSION_RE.match(licence.strip()):
        # PEP 639 allows an SPDX expression such as `MIT OR Apache-2.0`. Kept
        # whole: reporting only the first term would misstate a dual licence.
        found.append(licence.strip())
    elif isinstance(licence, dict):
        text = licence.get("text")
        if isinstance(text, str) and _SPDX_ID_RE.match(text):
            found.append(text)

    # PEP 639's `license-expression` field, if present.
    expression = project.get("license-expression")
    if isinstance(expression, str) and expression.strip():
        found.append(expression.strip())

    return tuple(dict.fromkeys(found))


def _spdx_from_package_json(root: Path) -> tuple[str, ...]:
    """SPDX identifiers declared in `package.json`."""
    path = root / "package.json"
    if not path.is_file():
        return ()
    try:
        data = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return ()
    if not isinstance(data, dict):
        return ()

    found: list[str] = []
    licence = data.get("license")
    if isinstance(licence, str) and _SPDX_EXPRESSION_RE.match(licence.strip()):
        found.append(licence.strip())
    # `licenses` (plural, array of {type, url}) is the deprecated npm form.
    plural = data.get("licenses")
    if isinstance(plural, list):
        for item in plural:
            if isinstance(item, dict):
                kind = item.get("type")
                if isinstance(kind, str) and _SPDX_ID_RE.match(kind.strip()):
                    found.append(kind.strip())
    return tuple(dict.fromkeys(found))


#: Unambiguous licence-name headers, matched against the FIRST non-blank line of
#: a licence file only.
#:
#: This is a curated allowlist, not prose matching, and the distinction is the
#: whole point. It recognises the convention where a licence file's title line
#: literally names the licence ("MIT License", "Apache License"), which is a
#: declaration rather than an inference.
#:
#: It deliberately does NOT search the whole file for phrases. Verified while
#: building this: microsoft/autogen's LICENSE genuinely IS Creative Commons
#: Attribution 4.0, and a whole-file phrase search is how one ends up
#: "correcting" a correct detection from memory. crewAI's first line is a bare
#: copyright notice, which yields nothing -- correctly, because a copyright
#: line does not state a licence.
_LICENCE_HEADERS: Final[tuple[tuple[str, str], ...]] = (
    ("mit license", "MIT"),
    ("the mit license", "MIT"),
    ("apache license", "Apache-2.0"),
    ("apache 2.0", "Apache-2.0"),
    # The standard Apache preamble, which names the licence mid-sentence rather
    # than as a title. vercel/ai's LICENSE line 2 is exactly this, and omitting
    # it left that repository's licence undetermined until the real file was
    # inspected.
    ("licensed under the apache license", "Apache-2.0"),
    ("licensed under the mit license", "MIT"),
    ("bsd 3-clause", "BSD-3-Clause"),
    ("bsd 2-clause", "BSD-2-Clause"),
    ("gnu affero general public license", "AGPL-3.0"),
    ("gnu lesser general public license", "LGPL-3.0"),
    ("gnu general public license", "GPL-3.0"),
    ("mozilla public license", "MPL-2.0"),
    ("isc license", "ISC"),
    ("the unlicense", "Unlicense"),
    ("creative commons attribution 4.0", "CC-BY-4.0"),
    ("attribution 4.0 international", "CC-BY-4.0"),
    ("attribution-sharealike 4.0", "CC-BY-SA-4.0"),
)


#: How many leading non-blank lines count as the `notice block`. Apache-style
#: licences put a copyright line first and the licence name second; MIT files
#: sometimes do the same. Scanning only the very first line missed both.
_NOTICE_BLOCK_LINES: Final = 3


def _spdx_from_header(licence_file: Path) -> tuple[str, str]:
    """Return `(spdx_id, matched_line)` from a licence file's notice block.

    The notice block is the first few non-blank lines, not the whole file. That
    bound is the entire point: a licence body can *mention* another licence in a
    compatibility note ("previously released under the MIT License"), and
    searching the whole file would let that override the real title. Two real
    cases forced the block to be more than one line:

      * `vercel/ai` — line 1 is `Copyright 2023 Vercel, Inc.`, line 2 is
        `Licensed under the Apache License, Version 2.0 (the "License");`
      * `crewAI` — line 1 is a copyright notice, line 2 carries MIT's grant.

    Both were reported as "not determined" until the block was widened, which is
    the correct failure direction (refusing rather than guessing) but still a
    miss. A licence name is a *declaration*; anywhere in the notice block it is
    as explicit as on line 1.

    Only exact allowlist entries match, so widening the window does not weaken
    the guarantee: an unrecognised string still yields `("", "")`.
    """
    try:
        text = licence_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ("", "")

    checked = 0
    for raw in text.splitlines():
        stripped = raw.strip().strip("#").strip()
        if not stripped:
            continue

        lowered = stripped.lower()
        for needle, spdx_id in _LICENCE_HEADERS:
            if lowered.startswith(needle):
                return (spdx_id, stripped)

        checked += 1
        if checked >= _NOTICE_BLOCK_LINES:
            break

    return ("", "")


def detect_licence(root: Path) -> Licence:
    """Determine a repository's licence from declared metadata or explicit tags.

    Pure with respect to the filesystem: reads only, never writes. Returns an
    :class:`License` whose `confidence` records how the claim was established,
    so a report never presents a filename as though it were a verified
    identifier.
    """
    licence_file = _first_licence_file(root)
    relative_file = licence_file.name if licence_file else ""

    evidence: list[str] = []
    candidates: list[str] = []

    declared = _spdx_from_pyproject(root)
    if declared:
        evidence.extend(f"pyproject.toml: license = {value!r}" for value in declared)
        candidates.extend(declared)

    from_package_json = _spdx_from_package_json(root)
    if from_package_json:
        evidence.extend(
            f"package.json: license = {value!r}" for value in from_package_json
        )
        candidates.extend(from_package_json)

    reuse = _reuse_licences(root)
    if reuse:
        evidence.extend(f"LICENSES/{value}" for value in reuse)
        candidates.extend(reuse)

    # An SPDX tag inside the licence file is explicit but weaker than manifest
    # metadata: it is prose that a tag was written into, not a parsed field.
    tagged: list[str] = []
    if licence_file is not None:
        try:
            text = licence_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        tagged = [match.group("id") for match in _SPDX_TAG_RE.finditer(text)]
        if tagged:
            evidence.extend(
                f"{relative_file}: SPDX-License-Identifier: {value}" for value in tagged
            )

    unique = tuple(dict.fromkeys(candidates))

    # A conflict is reported rather than resolved. `licensee` makes the same
    # choice, and for the same reason: picking one of several disagreeing
    # licences is how a report becomes confidently wrong about a legal fact.
    if len(unique) > 1:
        return Licence(
            spdx_id="",
            confidence=LicenceConfidence.DECLARED,
            evidence=tuple(evidence),
            licence_file=relative_file,
            conflicts=unique,
        )

    if unique:
        confidence = (
            LicenceConfidence.DECLARED
            if declared or from_package_json
            else LicenceConfidence.REUSE_FILENAME
        )
        return Licence(
            spdx_id=unique[0],
            confidence=confidence,
            evidence=tuple(evidence),
            licence_file=relative_file,
        )

    if tagged:
        return Licence(
            spdx_id=tagged[0],
            confidence=LicenceConfidence.TAGGED,
            evidence=tuple(evidence),
            licence_file=relative_file,
        )

    # A title line that names the licence outright. Weaker than a declared
    # field (the project wrote prose, not metadata) but unambiguous when it
    # hits, because the allowlist is exact.
    if licence_file is not None:
        header_id, header_line = _spdx_from_header(licence_file)
        if header_id:
            return Licence(
                spdx_id=header_id,
                confidence=LicenceConfidence.HEADER,
                evidence=(
                    f"{relative_file} title line: {header_line!r}",
                    *tuple(evidence),
                ),
                licence_file=relative_file,
            )

    if licence_file is not None:
        return Licence(
            spdx_id="",
            confidence=LicenceConfidence.UNIDENTIFIED,
            evidence=(
                f"{relative_file} exists; contents not matched against the SPDX list",
            ),
            licence_file=relative_file,
        )

    return Licence(
        spdx_id="",
        confidence=LicenceConfidence.ABSENT,
        evidence=("no licence file and no declared SPDX identifier",),
    )
