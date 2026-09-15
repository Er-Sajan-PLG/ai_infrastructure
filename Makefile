# ai_infrastructure — developer entry points.
#
# Every check the repository claims to satisfy is runnable from this file.
# If a rule is not enforced here, it is a preference, not a standard.
#
# Charter references: §13 (standards), §18 (testing), §19 (benchmarking),
# §21 (definition of done), §29 (pipeline is infrastructure too).

SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV      := .venv
PY        := $(VENV)/bin/python
RUFF      := $(VENV)/bin/ruff
BLACK     := $(VENV)/bin/black
MYPY      := $(VENV)/bin/mypy
PYTEST    := $(VENV)/bin/pytest
UV_CACHE  := $(CURDIR)/.uv-cache

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
install-hooks: ## Install the git pre-commit hook (enforces gates locally)
	@mkdir -p .git/hooks
	@cp scripts/hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Installed .git/hooks/pre-commit — gates now run on every commit."

.PHONY: uninstall-hooks
uninstall-hooks: ## Remove the git pre-commit hook
	@rm -f .git/hooks/pre-commit
	@echo "Removed .git/hooks/pre-commit."

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff over the codebase
	$(RUFF) check .
	$(RUFF) format --check .

.PHONY: format
format: ## Auto-format the codebase (ruff + black)
	$(RUFF) check --fix .
	$(BLACK) .

.PHONY: typecheck
typecheck: ## Run mypy in strict mode
	@# Pass only existing targets: naming an empty directory makes mypy exit 2,
	@# and empty category directories are the normal state of a young category.
	@targets=$$(find catalog scripts tests study_pipeline -name '*.py' \
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
coverage: ## Run tests with branch coverage
	$(PYTEST) --cov --cov-report=term-missing

.PHONY: validate
validate: ## Check the catalog entry contract (charter §13)
	$(PY) scripts/validate_catalog.py

.PHONY: validate-strict
validate-strict: ## Catalog validation with examples/tests required
	$(PY) scripts/validate_catalog.py --strict

# ---------------------------------------------------------------------------
# Aggregate gates
# ---------------------------------------------------------------------------

.PHONY: check
check: lint typecheck validate test ## The full gate a session must pass before committing

.PHONY: check-strict
check-strict: lint typecheck validate-strict test ## Full gate + strict catalog contract

.PHONY: ci
ci: check-strict coverage ## What CI runs

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

.PHONY: status
status: ## Summarize repository state (capabilities, gaps, counts)
	$(PY) scripts/repo_status.py

# ---------------------------------------------------------------------------
# Benchmarking (charter §19)
# ---------------------------------------------------------------------------

.PHONY: bench
bench: ## Run benchmarks (no-op until an implementation exists)
	@test -d benchmarks && find benchmarks -name 'bench_*.py' -print -quit | grep -q . \
		&& $(PY) -m pytest benchmarks -q \
		|| echo "No benchmarks defined yet (charter §19). Nothing to run."