"""Verify that CI and the Makefile agree about which gates exist.

Why this test exists
--------------------
The workflow's own header comment claims it "runs the same gates as `make ci`
so a green pipeline means the same thing as a green local run". That is a
claim, and per charter §4 a claim must match artifacts. Before this test
existed the claim was **false**: CI ran `scripts/repo_status.py` while
`make ci` did not include `status` at all, and the two produced coverage by
different routes. A documented guarantee that nothing checks is exactly the
class of defect charter §20 names ("a rule with no check is a preference").

Why hand-written rather than an existing tool
---------------------------------------------
No general-purpose tool does this. survey of the field: `actionlint` validates
workflow *validity*; `zizmor` checks workflow *security*; `checkmake` lints
Makefiles; `yamllint` checks YAML style; `ci-parity` is Node/npm-specific and
never reads a Makefile. Two real implementations exist in the wild
(`kv-shepherd/shepherd`'s Go checker and `reflex-dev/xy`'s Python one), and
their designs inform this one -- particularly the fixture tests and the
deferral table that keep such a gate from being deleted the first time it is
inconvenient.

Design notes that are load-bearing
----------------------------------
1. **It asks make, it does not scrape.** The gate list comes from
   `make print-gates`, so this test cannot disagree with the Makefile about
   what the Makefile says. Scraping with a regex would make the test a second
   source of truth about the first.

2. **The MAKELEVEL trap.** `make print-gates` is invoked from inside pytest.
   If pytest is itself running under make (as `make ci` does), the nested make
   inherits `MAKELEVEL` and writes `make[1]: Entering directory ...` to
   stdout, whose words then parse as gate names. This is a documented real
   incident, not a hypothetical: a drift test in the wild "passed locally
   because pytest was invoked directly and failed in CI because the runner
   goes through the Makefile -- precisely the local-and-CI divergence the
   Makefile was added to remove". Hence `--no-print-directory`, a scrubbed
   environment, and an explicit assertion that the output contains nothing
   that is not a bare target name.

3. **A real YAML parser, never a regex.** A project that scanned workflow
   YAML with regexes rewrote its scanners eighteen times "while CI stayed
   fully green". `yaml.compose` is used so node marks give file:line in
   failure messages.

4. **An anti-silent-skip floor.** If discovery breaks -- the YAML key is
   renamed, the workflow is restructured -- this test would compare two empty
   sets and pass having verified nothing. An empty result is therefore a
   failure, not a pass.

5. **Presence is asserted, not just absence.** It is not enough that the
   workflow does not run other gates; every gate in the manifest must actually
   appear. Otherwise deleting a gate from CI silently reduces coverage while
   this test stays green.

Charter references: §4, §18, §20, §28, §29.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# A gate name is a make target: lower-case words joined by hyphens.
_TARGET_RE = re.compile(r"^[a-z][a-z0-9-]*$")

# Gates CI runs that are deliberately NOT part of `make ci`, with the reason.
#
# These are not exceptions to hide drift -- each is a gate whose inclusion in
# `make ci` would be WRONG, because it cannot run in every context:
#
#   diff-coverage  needs a base branch to diff against, so it is meaningless
#                  on the default branch and is run only on pull_request.
#
# Any other difference in either direction is a failure. Keeping this list
# explicit (rather than, say, matching a `-` suffix pattern) means adding to it
# is a deliberate edit that a reviewer sees.
_PR_ONLY_GATES = frozenset({"diff-coverage"})

# A nested make prints this when MAKELEVEL is inherited.
_MAKE_NOISE_RE = re.compile(r"^make(\[\d+\])?:", re.IGNORECASE)

# Discovery must find at least this many gates. See design note 4 -- an empty
# or collapsed result is a failure, because it means the check verified
# nothing and would otherwise pass silently.
MIN_EXPECTED_GATES = 5


def _make_gate_manifest() -> list[str]:
    """Ask the Makefile which gates `make ci` runs.

    Returns a clean list of target names. Raises AssertionError with a
    diagnostic if the output contains anything that is not a bare target,
    which is how the MAKELEVEL pollution described in the module docstring
    would present itself.
    """
    env = dict(os.environ)
    # Scrub the variables that make a nested invocation announce itself.
    for key in ("MAKELEVEL", "MAKEFLAGS", "MFLAGS"):
        env.pop(key, None)

    proc = subprocess.run(
        # "make" is deliberately resolved through PATH: this test must exercise
        # the same make that runs the gates, not a bundled one.
        ["make", "--no-print-directory", "print-gates"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, (
        f"`make print-gates` failed with exit {proc.returncode}. "
        f"stderr:\n{proc.stderr}"
    )

    raw_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    noise = [line for line in raw_lines if _MAKE_NOISE_RE.match(line)]
    assert not noise, (
        "`make print-gates` emitted make's own chatter, which would be parsed "
        f"as gate names: {noise!r}. This is the inherited-MAKELEVEL trap: the "
        "nested make inherited MAKELEVEL from an outer make. The guard in this "
        "test scrubs MAKELEVEL/MAKEFLAGS, so if this fires the invocation is "
        "reaching make by another route."
    )

    not_targets = [line for line in raw_lines if not _TARGET_RE.match(line)]
    assert not not_targets, (
        f"`make print-gates` emitted {not_targets!r}, which are not make target "
        f"names. The parity comparison would be comparing garbage."
    )

    assert len(raw_lines) >= MIN_EXPECTED_GATES, (
        f"`make print-gates` reported only {len(raw_lines)} gate(s) "
        f"({raw_lines!r}); at least {MIN_EXPECTED_GATES} are expected. This "
        f"usually means the manifest broke, not that CI was reduced to "
        f"{len(raw_lines)} gate(s). Refusing to pass a check that verified "
        f"nothing."
    )

    return raw_lines


def _workflow_make_invocations() -> list[str]:
    """Return every `make <target>` target named in the CI workflow.

    Parses the workflow with a real YAML parser (`yaml.compose` preserves node
    marks for diagnostics) rather than scanning lines. See design note 3.
    """
    assert WORKFLOW.exists(), f"workflow not found at {WORKFLOW}"

    text = WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert isinstance(data, dict), "workflow did not parse to a mapping"

    # NOTE: YAML 1.1 parses the bare key `on:` as the boolean True, so the
    # trigger key is not necessarily the string "on". Only `jobs` is needed
    # here, which avoids the gotcha entirely -- recorded because it is a real
    # trap for anyone extending this test to inspect triggers.
    jobs = data.get("jobs")
    assert isinstance(jobs, dict), "workflow has no `jobs` mapping"

    targets: list[str] = []
    target_re = re.compile(r"\bmake\s+([a-z][a-z0-9-]*)")

    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            targets.extend(target_re.findall(run))

    return targets


def test_workflow_invokes_make() -> None:
    """CI must route its gates through the Makefile, not re-implement them.

    If the workflow stops calling make, the Makefile silently stops being the
    single source of truth and this whole test becomes vacuous -- so the
    precondition is asserted explicitly rather than assumed.
    """
    targets = _workflow_make_invocations()
    assert targets, (
        "The CI workflow contains no `make <target>` invocation. Either it "
        "stopped delegating to the Makefile (in which case the Makefile is no "
        "longer the single source of truth and this test verifies nothing), or "
        "the parsing above broke. Both need fixing."
    )


def test_every_manifest_gate_appears_in_ci() -> None:
    """Every gate `make ci` runs must be run by CI, and vice versa.

    This is the drift assertion. Both directions matter:
      * missing from CI  -> a gate the repository claims to enforce does not run
      * extra in CI      -> CI enforces something the Makefile does not describe,
                            so a green local run does not predict a green CI run
                            (this is the defect that existed before this test)

    `_PR_ONLY_GATES` names the gates that are CI-only by design; see its
    definition. Everything else must match exactly.
    """
    manifest = set(_make_gate_manifest())
    in_ci = set(_workflow_make_invocations())

    missing_from_ci = sorted(manifest - in_ci)
    extra_in_ci = sorted(in_ci - manifest - _PR_ONLY_GATES)

    assert not missing_from_ci, (
        f"`make ci` runs {missing_from_ci!r} but .github/workflows/ci.yml does "
        f"not invoke them. A gate in the Makefile that CI never runs is not "
        f"enforced."
    )
    assert not extra_in_ci, (
        f".github/workflows/ci.yml invokes {extra_in_ci!r}, which `make ci` "
        f"does not run. A green local `make ci` would not predict a green "
        f"pipeline. Either add them to the Makefile's CI_GATES or remove them "
        f"from the workflow."
    )


def test_aggregate_target_runs_the_manifest() -> None:
    """`make ci` must actually depend on the targets the manifest prints.

    Guards against the manifest being updated while the `ci:` target's
    prerequisites are not, which would make `print-gates` describe something
    that does not happen.

    HOW this is checked matters. `make -n ci` does NOT print the names of
    prerequisite targets -- it prints their expanded RECIPES, so searching its
    output for a gate name finds nothing even when the dependency is correct
    (this test was written that way first, and failed against a correct
    Makefile). `make -pn` instead prints the database, including the explicit
    prerequisite list for each target, which is what is actually wanted here.
    """
    env = dict(os.environ)
    for key in ("MAKELEVEL", "MAKEFLAGS", "MFLAGS"):
        env.pop(key, None)

    proc = subprocess.run(
        # -p prints the make database; -n prevents any recipe from running.
        ["make", "--no-print-directory", "-pn"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, f"`make -pn` failed: {proc.stderr}"

    database = proc.stdout

    # Find the `ci:` rule's prerequisite list in the printed database.
    match = re.search(
        r"(?m)^ci:\s*(?P<prereqs>[^\n]*)$",
        database,
    )
    assert match is not None, (
        "could not find the `ci:` rule in `make -pn` output; the Makefile's "
        "structure changed and this test needs updating"
    )

    declared = set(match.group("prereqs").split())
    manifest = set(_make_gate_manifest())

    assert manifest <= declared, (
        f"`make print-gates` lists {sorted(manifest - declared)!r}, but the "
        f"`ci:` target does not depend on them (it depends on {sorted(declared)!r}). "
        f"The manifest and the target have drifted apart."
    )


def test_registry_lists_the_gates_it_claims() -> None:
    """`print-gates` output must be non-trivial and sorted-unique.

    A cheap invariant: duplicate entries would mean a gate runs twice, and the
    test that compares sets would not notice (sets deduplicate).
    """
    gates = _make_gate_manifest()
    assert len(gates) == len(set(gates)), f"duplicate gates in manifest: {gates!r}"
    assert "check-strict" in gates, (
        "`check-strict` is the package-level gate and must always be part of "
        "`make ci`; its absence means CI is not running the repository's own "
        "definition of done."
    )


if __name__ == "__main__":  # pragma: no cover - convenience only
    sys.exit(pytest.main([__file__, "-v"]))
