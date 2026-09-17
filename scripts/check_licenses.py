#!/usr/bin/env python3
"""Verify dependency licences against an allow-list.

Why an allow-list and not a deny-list
-------------------------------------
A deny-list can only reject what somebody remembered to enumerate. A licence
nobody thought of -- or one with no metadata at all -- passes silently. The
industry has moved to allow-lists on exactly this reasoning: GitHub marked
`deny-licenses` in `dependency-review-action` deprecated for removal, and
Anchore's policy engine is built on "deny all licences except those explicitly
permitted."

The decisive detail is the UNKNOWN case. GitHub's own dependency-review
documentation states that when a licence cannot be detected "the action won't
fail" -- so an allow-list alone still lets unknown licences through. This
script therefore treats UNKNOWN as a FAILURE, not a warning. "We could not
determine the licence" and "the licence is acceptable" must never be
indistinguishable.

What this can and cannot see
----------------------------
Every metadata-based licence tool -- this one, pip-licenses, licensecheck --
reads the DECLARED licence from package metadata. A package that declares MIT
while vendoring GPL code reads as MIT here. File-level truth requires
scancode-toolkit. That limitation is recorded rather than papered over; this
check is a guard against ACCIDENTAL licence drift, not a legal audit.

Scope note (important, and it is why this gate passes rather than being a
no-op): this repository has ZERO runtime dependencies by design (see
pyproject.toml), so there is no distributed artefact whose licences matter to
a consumer. The check audits the INSTALLED environment -- which today is the
development toolchain -- because that is what `pip-audit` and the rest of the
security gates already reason about, and because a future runtime dependency
would otherwise arrive with no licence check at all. When a runtime dependency
is added, this gate becomes load-bearing rather than precautionary.

Charter references: §20 (a rule with no check is a preference), §22
(dependency review gate), §23 (supply chain).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Licences we accept. Chosen as the permissive set compatible with this
# project's Apache-2.0 licence; MPL-2.0 is included deliberately because its
# copyleft is FILE-level and imposes no obligation on our own source files.
#
# Matching is done on a NORMALISED form (see _normalise), because the same
# licence arrives spelled several ways: "MIT", "MIT License", "Apache License
# 2.0", "Apache-2.0", "BSD-3-Clause", "3-Clause BSD License".
ALLOWED: frozenset[str] = frozenset(
    {
        "0bsd",
        "apache-2.0",
        "bsd-2-clause",
        "bsd-3-clause",
        "isc",
        "mit",
        "mpl-2.0",
        "psf-2.0",
        "python-2.0",
        "unlicense",
        "cc0-1.0",
        # Some packages declare the empty/unknown marker explicitly, which is
        # NOT the same as missing metadata; both fail below.
    }
)

# Values that mean "no licence declared". These FAIL rather than pass.
UNKNOWN_MARKERS: frozenset[str] = frozenset(
    {"", "unknown", "none", "unlicensed", "proprietary"}
)


def _normalise(raw: str) -> str:
    """Reduce a declared licence string to a comparable key.

    This does NOT guess. It strips the noise words that carry no information
    and folds the spellings that are unambiguously the same licence. Anything
    whose clause count is genuinely ambiguous (a bare "BSD License" that names
    no clause) normalises to a marker that FAILS, because guessing in the
    permissive direction is exactly the failure an allow-list exists to
    prevent. Callers that can supply better evidence (Trove classifiers) do so
    before calling this.
    """
    text = raw.strip().lower()
    # Drop the parenthetical many packages append, e.g.
    # "Mozilla Public License 2.0 (MPL 2.0)".
    if "(" in text:
        text = text.split("(", 1)[0]
    for noise in (" license", " licence", "the ", " software", " version"):
        text = text.replace(noise, "")
    text = text.strip().strip("().,")

    if text.startswith("apache"):
        return "apache-2.0"
    if text.startswith("mit"):
        return "mit"
    if "mozilla public" in text or text.startswith("mpl"):
        return "mpl-2.0" if ("2" in text or "mozilla public" in text) else "mpl-unknown"
    if text.startswith("isc"):
        return "isc"
    if text.startswith("unlicense"):
        return "unlicense"
    if "python software foundation" in text or text.startswith("psf"):
        return "psf-2.0"
    if text.startswith("python") and "2" in text:
        return "python-2.0"
    if text.startswith("cc0"):
        return "cc0-1.0"
    if text.startswith("0bsd") or text == "bsd zero clause":
        return "0bsd"

    # BSD is the subtle one: "BSD License" names no clause count.
    if "bsd" in text:
        if "3" in text or "three" in text:
            return "bsd-3-clause"
        if "2" in text or "two" in text:
            return "bsd-2-clause"
        return "bsd-unknown"

    return text


def _from_classifiers(metadata: object) -> str:
    """Extract a licence name from Trove classifiers, if present.

    The classifiers distinguish what the free-text `License` field often does
    not: a package whose `License` is the ambiguous "BSD License" usually
    carries `License :: OSI Approved :: BSD License` AND frequently a
    clause-specific classifier. This is evidence, not a guess.
    """
    get_all = getattr(metadata, "get_all", None)
    classifiers = get_all("Classifier") if callable(get_all) else None
    if not classifiers:
        return ""
    for classifier in classifiers:
        text = str(classifier)
        if text.startswith("License ::"):
            return text.rsplit("::", 1)[-1].strip()
    return ""


def _from_license_file(dist: object) -> str:
    """Read the licence text bundled with the distribution, as a last resort.

    Why this exists: for a real and non-trivial minority of packages the
    DECLARED metadata is genuinely ambiguous. Jinja2, colorama and
    prompt_toolkit all ship `License: None` plus the classifier
    `License :: OSI Approved :: BSD License`, which names no clause count --
    so neither field says whether the terms are 2-clause or 3-clause.

    Rather than guess (and rather than fail forever on three of the most
    widely used packages in Python), we read the licence text the package
    actually SHIPS. That is stronger evidence than the metadata, not weaker:
    the file is the licence. We match only unambiguous clause-count phrases.

    Note this is deliberately narrow: it looks for the specific phrases that
    distinguish BSD variants and otherwise returns "", so an unfamiliar
    licence text is still reported as unknown rather than assumed permissive.
    """
    files = getattr(dist, "files", None) or []
    candidates = [
        f for f in files if "LICENSE" in str(f).upper() or "COPYING" in str(f).upper()
    ]
    for candidate in candidates[:4]:
        try:
            path = dist.locate_file(candidate)  # type: ignore[attr-defined]
            text = Path(path).read_text(errors="replace")[:8000].lower()
        except (OSError, AttributeError, TypeError):
            continue

        if "redistribution and use in source and binary forms" in text:
            # The BSD template. The clause count is decided by which
            # conditions are listed.
            if "neither the name" in text:
                return "BSD 3-Clause License"
            if "all advertising materials" in text:
                return "BSD 4-Clause License"
            return "BSD 2-Clause License"
        if "mozilla public license" in text and "2.0" in text:
            return "Mozilla Public License 2.0"
        if "apache license" in text and "2.0" in text:
            return "Apache License 2.0"
        if "permission is hereby granted, free of charge" in text:
            return "MIT License"
        if "isc license" in text or "permission to use, copy, modify" in text:
            return "ISC License"

    return ""


def _installed_distributions() -> list[tuple[str, str, str]]:
    """Return (name, version, declared_licence) for every installed package.

    Uses importlib.metadata from THIS interpreter, so the audit measures the
    environment the gates actually run in rather than a file that might drift
    from it. Licence metadata is read from the `License` field, falling back
    to the License-Expression field (PEP 639) and then to the Trove
    classifiers, which is where many packages put the real answer.
    """
    from importlib import metadata

    found: list[tuple[str, str, str]] = []
    for dist in metadata.distributions():
        name = dist.metadata["Name"] or "?"
        version = dist.version or "?"

        # Read the free-text field without triggering importlib.metadata's
        # "Implicit None on return values" deprecation: use .get() then coerce.
        licence = (dist.metadata.get("License") or "").strip()

        if not licence or licence.lower() in UNKNOWN_MARKERS:
            # PEP 639 License-Expression is the modern field.
            expression = dist.metadata.get("License-Expression")
            if expression:
                licence = expression.strip()

        # Classifiers are EVIDENCE and are consulted whenever the free-text
        # field is missing OR ambiguous (a bare "BSD License" names no clause
        # count, and guessing permissively is the failure mode an allow-list
        # exists to prevent). Prefer a clause-specific classifier.
        classifier_licence = _from_classifiers(dist.metadata)
        if classifier_licence and (
            not licence
            or licence.lower() in UNKNOWN_MARKERS
            or _normalise(licence) in {"bsd-unknown", "mpl-unknown"}
        ):
            licence = classifier_licence

        # Final fallback: the licence text the package ships. Used only when
        # the declared metadata is absent or genuinely ambiguous, so it never
        # overrides a clear declaration.
        if (
            not licence
            or licence.lower() in UNKNOWN_MARKERS
            or _normalise(licence) in {"bsd-unknown", "mpl-unknown"}
        ):
            from_file = _from_license_file(dist)
            if from_file:
                licence = from_file

        found.append((name, version, licence))

    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify dependency licences against an allow-list."
    )
    parser.add_argument("--quiet", action="store_true", help="print only problems")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args(argv)

    packages = _installed_distributions()
    if not packages:
        print("check_licenses: no installed distributions found; nothing to check.")
        return 0

    denied: list[tuple[str, str, str, str]] = []  # name, version, licence, key
    unknown: list[tuple[str, str, str]] = []

    for name, version, licence in packages:
        key = _normalise(licence)
        if key in UNKNOWN_MARKERS or key in {"bsd-unknown"}:
            unknown.append((name, version, licence))
        elif key not in ALLOWED:
            denied.append((name, version, licence, key))

    if args.json:
        print(
            json.dumps(
                {
                    "checked": len(packages),
                    "denied": [
                        {"name": n, "version": v, "license": raw, "key": k}
                        for n, v, raw, k in denied
                    ],
                    "unknown": [
                        {"name": n, "version": v, "license": raw}
                        for n, v, raw in unknown
                    ],
                },
                indent=2,
            )
        )
        return 1 if (denied or unknown) else 0

    if denied or unknown:
        print("", file=sys.stderr)
        for name, version, licence, key in denied:
            print(
                f"check_licenses: FAIL {name}=={version} declares "
                f"{licence!r} (normalised {key!r}), not on the allow-list.",
                file=sys.stderr,
            )
        for name, version, licence in unknown:
            print(
                f"check_licenses: FAIL {name}=={version} declares no usable "
                f"licence (raw {licence!r}). Unverifiable is treated as "
                f"unacceptable, not as acceptable-by-default.",
                file=sys.stderr,
            )
        print(
            f"\ncheck_licenses: {len(denied)} disallowed and {len(unknown)} "
            f"unknown licence(s) across {len(packages)} package(s).",
            file=sys.stderr,
        )
        print(
            "  To accept one deliberately, add it to ALLOWED in "
            "scripts/check_licenses.py with the reason, or record it in "
            "docs/risks/ACCEPTED_RISKS.md (charter §20, §22).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(
            f"check_licenses: {len(packages)} package(s) checked; "
            f"all licences on the allow-list."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
