# ai_infrastructure — developer entry points.
#
# Every check the repository claims to satisfy is runnable from this file.
# If a rule is not enforced here, it is a preference, not a standard.
#
# CI does not re-implement these gates: .github/workflows/ci.yml invokes them
# through `make`, and tests/test_ci_parity.py fails the build if the two ever
# disagree. That is what makes this file the single source of truth rather
# than a second, drifting copy of one.
#
# Charter references: §13 (standards), §18 (testing), §19 (benchmarking),
# §20 (a rule with no check is a preference), §21 (definition of done),
# §28 (never weaken a check), §29 (pipeline is infrastructure too).

# ---------------------------------------------------------------------------
# Shell hardening — read this before editing any recipe.
#
# Without the settings below, a recipe can FAIL and still report success,
# which makes every gate in this file unenforceable. Concretely:
#
#   * make runs each recipe LINE in its own shell by default, so a `cd` or a
#     variable assignment does not carry to the next line;
#   * with .ONESHELL but no `-e`, make sees only the FINAL exit code of the
#     whole recipe, so a mid-recipe failure is invisible;
#   * without `pipefail`, `failing-command | tee log` exits 0 and the gate
#     passes. This was a live defect in this repository until 2026-09-17 --
#     verified by reproduction, not assumed. It is also not theoretical in
#     general: GitHub's own default runner shell is `/usr/bin/bash -e {0}`,
#     `-e` WITHOUT `pipefail` (actions/runner-images#4459), which is how a
#     failing test step piped to `tee` reports success.
#
# `-u` additionally makes a typo'd variable an error instead of an empty
# string, and --warn-undefined-variables reports it at parse time.
#
# The .RECIPEPREFIX guard fails loudly on a make too old to support these
# features, rather than silently ignoring them.
# ---------------------------------------------------------------------------

SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules
.DEFAULT_GOAL := help

ifeq ($(origin .RECIPEPREFIX), undefined)
  $(error GNU Make 4.0 or later is required (for .RECIPEPREFIX and .ONESHELL))
endif

VENV      := .venv
PY        := $(VENV)/bin/python
RUFF      := $(VENV)/bin/ruff
BLACK     := $(VENV)/bin/black
MYPY      := $(VENV)/bin/mypy
PYTEST    := $(VENV)/bin/pytest
UV_CACHE  := $(CURDIR)/.uv-cache

# A literal space, for $(subst) below (a bare space is eaten by make).
empty :=
space := $(empty) $(empty)

# Coverage floor: an INTEGER with margin, enforced by `make coverage`.
#
# This is a REGRESSION FLOOR, not a quality target. Inozemtseva & Holmes
# (ICSE 2014, 31,000 suites) found coverage's correlation with fault detection
# is largely explained by test-suite SIZE, and that "using a fixed coverage
# value as a quality target is unlikely to produce an effective test suite";
# Kochhar et al. (IEEE TR 2017, 100 projects) found coverage has no
# file-level correlation with post-release bugs. 17 of 22 mature Python
# projects surveyed enforce no threshold at all.
#
# So the floor exists for the one thing it is good at -- noticing that
# something catastrophic happened -- and is read the way coverage.py reads its
# own 90%: "a very crude check that nothing catastrophic has happened". The
# real quality signal on a change is `make diff-coverage`.
#
# WHY AN INTEGER WITH MARGIN, AND NOT "just below the measured value":
# coverage DISPLAYS a rounded percentage while --cov-fail-under compares the
# RAW float. Measured here: the report prints "90%" while the real value is
# 90.03% (it was 89.79% before the checker unit tests landed, and the report
# printed "90%" in both cases -- which is the point). A floor of 90 would
# therefore FAIL while showing the reader "90%".
# An integer at least one point below the measured value cannot land in that
# gap. Rationale and rejected alternatives: docs/decisions/0016.
COVERAGE_FLOOR := 85

# The directories that hold catalog entry packages, in the form a CONSUMER
# uses them: catalog/<category>/ goes on sys.path and the entry is imported by
# its bare name (charter §31). Used by `make independence`, because outside
# pytest entry packages are not importable at all.
#
# Derived, not hard-coded: filtered to directories that actually CONTAIN an
# entry package (a subdirectory with __init__.py). Globbing every category
# would add 15 empty directories, and a hard-coded list would silently go
# stale the moment an entry is added.
ENTRY_DIRS := $(patsubst %/__init__.py,%,$(wildcard catalog/*/*/__init__.py))
ENTRY_PATHS := $(subst $(space),:,$(sort $(dir $(ENTRY_DIRS)))):integrations

# The gates `make ci` runs, in order. Single source of truth: the `ci` target
# depends on exactly these, and `print-gates` prints exactly these, so the two
# cannot drift from each other.
#
# Why the security gates are listed INDIVIDUALLY rather than as the `security`
# aggregate: CI runs them as separate steps so that a failure names the gate
# that failed (a collapsed step reports only "make security failed"), and
# branch protection and annotation limits both assume per-gate granularity.
# The `security` aggregate still exists for local use; the workflow is the
# reason this list is expanded.
#
# `diff-coverage` is deliberately NOT here: it needs a base branch and is
# meaningless on the default branch, so the workflow runs it in a separate
# pull-request-only step. tests/test_ci_parity.py asserts the two-way
# correspondence for the gates listed here.
CI_GATES := check-strict coverage secrets sast sca licenses workflows deferred status

export UV_CACHE_DIR := $(UV_CACHE)

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Create the virtualenv and install the pinned dev toolchain
	@test -d $(VENV) || uv venv --python 3.14
	uv pip install -r requirements-dev.txt
	@echo "Environment ready. Activate with: source $(VENV)/bin/activate"

.PHONY: clean
clean: ## Remove caches and build artifacts (keeps .venv)
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov .uv-cache
	find . -path ./.venv -prune -o -type d -name __pycache__ -print0 | xargs -0 rm -rf

.PHONY: install-hooks
install-hooks: ## Install the git hooks (pre-commit and commit-msg)
	@mkdir -p .git/hooks
	@cp scripts/hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@cp scripts/hooks/commit-msg .git/hooks/commit-msg
	@chmod +x .git/hooks/commit-msg
	@echo "Installed .git/hooks/pre-commit and .git/hooks/commit-msg."
	@echo "  pre-commit: quality gates."
	@echo "  commit-msg: Conventional Commits header check (ADR-0019)."

.PHONY: uninstall-hooks
uninstall-hooks: ## Remove the installed git hooks
	@rm -f .git/hooks/pre-commit .git/hooks/commit-msg
	@echo "Removed .git/hooks/pre-commit and .git/hooks/commit-msg."

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff (lint only — black owns formatting)
	$(RUFF) check .
	$(BLACK) --check .

.PHONY: format
format: ## Auto-format the codebase (ruff --fix + black)
	$(RUFF) check --fix .
	$(BLACK) .

.PHONY: typecheck
typecheck: ## Run mypy in strict mode
	@# Pass only existing targets: naming an empty directory makes mypy exit 2,
	@# and empty category directories are the normal state of a young category.
	@targets=$$(find catalog integrations scripts tests study_pipeline -name '*.py' \
		-not -path '*/.venv/*' 2>/dev/null); \
	if [ -z "$$targets" ]; then \
		echo "No Python sources to type-check yet."; \
	else \
		$(MYPY) $$targets; \
	fi

.PHONY: test
test: ## Run the test suite
	$(PYTEST)

.PHONY: coverage
coverage: ## Run tests with coverage, enforced at the recorded floor
	@# See the COVERAGE_FLOOR definition above for why this is an integer
	@# with margin rather than the measured value.
	$(PYTEST) --cov --cov-report=term-missing \
		--cov-fail-under=$(COVERAGE_FLOOR)

.PHONY: validate
validate: links phase-plan ## Check the catalog entry contract + doc links (charter §13)
	$(PY) scripts/validate_catalog.py

.PHONY: links
links: ## Verify relative Markdown links resolve
	$(PY) scripts/check_links.py

.PHONY: phase-plan
phase-plan: ## Verify documented stage transitions match charter §4
	$(PY) scripts/check_phase_plan.py

.PHONY: validate-strict
validate-strict: ## Catalog validation with examples/tests required
	$(PY) scripts/validate_catalog.py --strict

# ---------------------------------------------------------------------------
# Structural checks (charter §31 — catalog entries must be independent)
# ---------------------------------------------------------------------------

.PHONY: independence
independence: ## Verify catalog entries cannot import one another (charter §31)
	@# import-linter models the real import graph, so it catches TRANSITIVE
	@# leakage (entry A -> shared helper -> entry B) that a per-file AST walk
	@# misses, and it resolves relative imports and TYPE_CHECKING blocks.
	@# It is a DEV dependency, so "no runtime dependencies" still holds.
	@# Rationale + the custom-check alternative: docs/decisions/0017.
	@#
	@# PYTHONPATH is required and is not incidental. Entry packages live at
	@# catalog/<category>/<entry>/ and are imported by BARE NAME (charter §31:
	@# a consumer adds catalog/<category>/ to sys.path). Outside pytest they
	@# are not importable at all -- pytest inserts each test file's rootdir
	@# into sys.path, and nothing else does. So the linter is given exactly
	@# the path entries are documented to be consumed from.
	@#
	@# The contract file is the TOML block in pyproject.toml, NOT a
	@# .importlinter file: import-linter reads setup.cfg and .importlinter as
	@# INI and only pyproject.toml as TOML, so TOML syntax in .importlinter
	@# fails with the opaque error "section '' already exists".
	PYTHONPATH="$(ENTRY_PATHS)" $(VENV)/bin/lint-imports --no-logo

.PHONY: collectability
collectability: ## Verify every catalog entry's tests are actually collectable
	@# No off-the-shelf tool answers "is this entry's tests/ collectable?".
	@# The hole this closes is real: a suite that collects ZERO items in a
	@# subdirectory reports success, so an entry could ship tests that never
	@# ran while every gate stayed green (see docs/decisions/0004).
	$(PY) scripts/check_collectability.py

.PHONY: structural
structural: independence collectability ## All charter §31 structural checks

# ---------------------------------------------------------------------------
# Security gates
# ---------------------------------------------------------------------------

.PHONY: secrets
secrets: ## Scan the FULL git history for committed secrets (gitleaks)
	@# History, not just the working tree: a secret deleted from HEAD is still
	@# in every clone. A missing binary is reported, never silently skipped --
	@# an unrun check must not look like a passed one (charter §28).
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks git . --no-banner --redact --exit-code 1; \
	else \
		echo "secrets: gitleaks not installed -- SKIPPED (CI always runs it)."; \
		echo "secrets: install from https://github.com/gitleaks/gitleaks"; \
	fi

.PHONY: sast
sast: ## Static security analysis (bandit AND ruff S — they are not equivalent)
	@# BOTH, deliberately. ruff's S rules are NOT a superset of bandit:
	@# B614 (pytorch_load) and B615 (huggingface_unsafe_download) are not
	@# ported, S320 was REMOVED from ruff, S401-S403 are preview-only and so
	@# silently never fire, and bandit's ~32 plugin modules cover Django
	@# XSS/SQLi, wildcard injection and weak crypto with no ruff equivalent.
	@# ruff's maintainers call the gap deliberate (astral-sh/ruff#20129).
	@#
	@# The ruff half runs via the CONFIGURED selection (which already includes
	@# "S"), NOT via `ruff check --select S`. Passing --select on the command
	@# line OVERRIDES the per-file-ignores in pyproject.toml, which made S101
	@# fire on every `assert` in the test suite -- a gate that fails on correct
	@# code. Measured, not assumed.
	@#
	@# Bandit scans PRODUCTION code only, at MEDIUM severity and above.
	@# Measured on this repository: 558 raw findings, of which 550 were B101
	@# (assert) in tests and the remaining 8 were forged attack payloads and
	@# fake credentials inside tests/examples that ASSERT those inputs are
	@# rejected. A scanner reporting 558 findings is a scanner nobody reads, so
	@# the gate is scoped to the code that actually ships. Test-path
	@# exclusions are done by PATH, because bandit's per-plugin `skips` globs
	@# do not reliably apply. Rationale: docs/decisions/0018.
	$(RUFF) check .
	@prod=$$(find catalog integrations scripts -name '*.py' \
		-not -path '*/tests/*' -not -path '*/examples/*'); \
	if [ -z "$$prod" ]; then \
		echo "sast: no production sources yet; nothing to scan."; \
	else \
		$(PY) -m bandit -c pyproject.toml -q -ll $$prod; \
	fi

.PHONY: sca
sca: ## Audit dependencies for known vulnerabilities (both data sources)
	@# Run TWICE: -s pypi and -s osv. The ESEM'21 study of 9 SCA tools found
	@# reported vulnerability counts ranging 17-332 on identical projects and
	@# concluded practitioners "should not rely on any single tool". OSV and
	@# PyPI/NVD each carry advisories the other lacks, so a second lineage
	@# costs one step and closes a real recall gap.
	@# Also: pip-audit exits 1 identically for a real advisory, a service
	@# error and a crash, so the exit code alone cannot tell "vulnerable"
	@# from "the network failed" -- hence the explicit per-service run.
	@echo "sca: auditing against PyPI advisories"
	$(PY) -m pip_audit -s pypi --progress-spinner off
	@echo "sca: auditing against OSV.dev"
	$(PY) -m pip_audit -s osv --progress-spinner off

.PHONY: licenses
licenses: ## Verify dependency licences are on the allow-list
	@# ALLOW-list, not deny-list: a deny-list only rejects what someone
	@# remembered to enumerate, and GitHub deprecated deny-licenses upstream
	@# for exactly this reason. Unknown licences FAIL rather than warn --
	@# metadata tools read DECLARED metadata only, and "we could not tell"
	@# must not be indistinguishable from "we checked and it is fine".
	$(PY) scripts/check_licenses.py

.PHONY: workflows
workflows: ## Lint the GitHub Actions workflows (actionlint + zizmor)
	@# Complementary, not alternatives: actionlint catches workflow
	@# CORRECTNESS (expression types, invalid inputs, shellcheck on run:
	@# blocks), zizmor catches workflow SECURITY (template injection,
	@# credential persistence, unpinned uses, dangerous triggers).
	@# Rationale: docs/decisions/0018.
	@if command -v actionlint >/dev/null 2>&1; then \
		actionlint; \
	else \
		echo "workflows: actionlint not installed -- SKIPPED (CI always runs it)."; \
	fi
	@if command -v zizmor >/dev/null 2>&1; then \
		zizmor --persona=regular .github/workflows/; \
	else \
		echo "workflows: zizmor not installed -- SKIPPED (CI always runs it)."; \
	fi

.PHONY: risks
risks: ## Verify the accepted-risk register is current and honestly maintained
	@# Checks expiry, the 400-day ceiling, and -- the one that matters -- that
	@# review_by did not ADVANCE while the rationale stayed identical. Without
	@# that last check the cheapest way to pass is to edit the date. See
	@# docs/risks/ACCEPTED_RISKS.md and docs/decisions/0014.
	$(PY) scripts/check_risks.py

.PHONY: deferred
deferred: ## Verify the deferred-work register is well-formed and current
	@# Work that is correctly not done yet, recorded with the fact that makes
	@# it premature, the trigger that would change that, and the reversal step.
	@# Enforces schema/expiry, the same anti-gaming re-dating rule as the risk
	@# register, and reports observable triggers that may have fired.
	$(PY) scripts/check_deferred.py

.PHONY: commit-msg
commit-msg: ## Validate the Conventional Commits header format (ADR-0019)
	@# Validates the header only. The specification is genuinely ambiguous about
	@# body and footer structure, so enforcing more would encode an
	@# interpretation rather than the spec (recorded as AR-003).
	$(PY) scripts/check_commit_msg.py --range "$${COMMIT_RANGE:-HEAD~1..HEAD}"

# ---------------------------------------------------------------------------
# Aggregate gates
#
# These are the contract with CI. tests/test_ci_parity.py fails the build if
# the workflow and these aggregates ever disagree about which gates exist.
# ---------------------------------------------------------------------------

.PHONY: check
check: lint typecheck validate links test ## The full gate a session must pass before committing

.PHONY: check-strict
check-strict: lint typecheck validate-strict links phase-plan structural risks deferred test ## Full gate + strict catalog + structural + registers

.PHONY: security
security: secrets sast sca licenses ## All security gates (SAST, SCA, secrets, licences)

.PHONY: ci
ci: $(CI_GATES) ## What CI runs — executed verbatim by .github/workflows/ci.yml

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

.PHONY: status
status: ## Summarize repository state (capabilities, gaps, counts)
	$(PY) scripts/repo_status.py

.PHONY: diff-coverage
diff-coverage: ## On a branch: require full coverage of lines this change touched
	@# The real quality gate on a change. A global percentage can be held up
	@# by untouched code; "every line THIS change added is exercised" cannot.
	@# Google's guidance endorses gating on new code only, and SonarQube's
	@# default gate is entirely new-code. coverage.py's own CI does this.
	@# Not part of `make ci`: it needs a base branch to diff against and is
	@# meaningless on the default branch. CI runs it only on pull_request.
	@# Escape hatch: label the PR `missing-coverage-ok` (deliberate, visible).
	@# Rationale: docs/decisions/0016.
	@base="$${DIFF_COVER_BASE:-origin/main}"; \
	if ! git rev-parse --verify --quiet "$$base" >/dev/null; then \
		echo "diff-coverage: base '$$base' not found; skipping (not a PR context)."; \
		exit 0; \
	fi; \
	$(PYTEST) --cov --cov-report=xml --cov-report=term-missing -q; \
	$(PY) -m diff_cover.diff_cover_tool coverage.xml \
		--compare-branch="$$base" \
		--fail-under="$${DIFF_COVER_FAIL_UNDER:-100}"

# Machine-readable gate manifest, consumed by tests/test_ci_parity.py.
#
# This exists so the parity test never has to scrape `make help` or re-parse
# this file with a regex: it asks make itself what CI is supposed to run. The
# test additionally guards against this invocation's own output being polluted
# by an inherited MAKELEVEL (see tests/test_ci_parity.py).
.PHONY: print-gates
print-gates: ## Print the CI gate list, one per line (machine-readable)
	@for t in $(CI_GATES); do echo "$$t"; done

# The PYTHONPATH used by `make independence`, so callers other than this
# Makefile (the pre-commit hook) do not have to re-derive it and risk drifting
# from the definition above.
.PHONY: print-entry-paths
print-entry-paths: ## Print the PYTHONPATH for entry packages (machine-readable)
	@echo "$(ENTRY_PATHS)"

# ---------------------------------------------------------------------------
# Benchmarking (charter §19)
# ---------------------------------------------------------------------------

.PHONY: bench
bench: ## Run benchmarks (no-op until an implementation exists)
	@test -d benchmarks && find benchmarks -name 'bench_*.py' -print -quit | grep -q . \
		&& $(PY) -m pytest benchmarks -q \
		|| echo "No benchmarks defined yet (charter §19). Nothing to run."
