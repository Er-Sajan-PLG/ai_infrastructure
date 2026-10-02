#!/usr/bin/env bash
#
# Install the verification package into this repository.
#
# Usage: ./verification-package/scripts/install-verification.sh
#
# This will:
#   1. Install git hooks (pre-commit, pre-push, commit-msg)
#   2. Copy the verify-full script to scripts/
#   3. Copy the CI workflow to .github/workflows/
#   4. Create a Makefile with verify targets (if no Makefile exists)
#
# Idempotent: safe to run multiple times.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PACKAGE_DIR="$REPO_ROOT/verification-package"

echo "=== Installing verification package ==="

# --- 1. Git hooks ----------------------------------------------------------
echo "Installing git hooks..."

mkdir -p .git/hooks

cp "$PACKAGE_DIR/hooks/pre-commit" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

cp "$PACKAGE_DIR/hooks/pre-push" .git/hooks/pre-push
chmod +x .git/hooks/pre-push

cp "$PACKAGE_DIR/hooks/commit-msg" .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg

echo "  pre-commit, pre-push, commit-msg installed."

# --- 2. verify-full script --------------------------------------------------
echo "Installing verify-full script..."

cp "$PACKAGE_DIR/scripts/verify-full.sh" scripts/verify-full.sh
chmod +x scripts/verify-full.sh

echo "  scripts/verify-full.sh installed."

# --- 3. CI workflow ----------------------------------------------------------
echo "Installing CI workflow..."

mkdir -p .github/workflows
cp "$PACKAGE_DIR/.github/workflows/ci.yml" .github/workflows/verification.yml

echo "  .github/workflows/verification.yml installed."

# --- 4. Makefile targets (append if Makefile exists) ------------------------
if [ -f "Makefile" ]; then
    echo "Appending verification targets to existing Makefile..."
    cat >> Makefile << 'MAKEFILE_EOF'

# --- Verification package targets ------------------------------------------
.PHONY: verify-commit
verify-commit: ## Run pre-commit checks (staged files only)
	@bash scripts/verify-full.sh

.PHONY: verify-push
verify-push: ## Run pre-push checks (typecheck + fast tests)
	@bash scripts/verify-full.sh type
	@bash scripts/verify-full.sh unit

.PHONY: verify-full
verify-full: ## Run full verification suite
	@bash scripts/verify-full.sh

.PHONY: verify-ci
verify-ci: ## Run what CI runs
	@bash scripts/verify-full.sh

.PHONY: install-verification
install-verification: ## Install verification package
	@bash verification-package/scripts/install-verification.sh

MAKEFILE_EOF
    echo "  Makefile targets appended."
else
    echo "No Makefile found. Creating one..."
    cat > Makefile << 'MAKEFILE_EOF'
SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: verify-commit
verify-commit: ## Run pre-commit checks (staged files only)
	@bash scripts/verify-full.sh

.PHONY: verify-push
verify-push: ## Run pre-push checks (typecheck + fast tests)
	@bash scripts/verify-full.sh type
	@bash scripts/verify-full.sh unit

.PHONY: verify-full
verify-full: ## Run full verification suite
	@bash scripts/verify-full.sh

.PHONY: verify-ci
verify-ci: ## Run what CI runs
	@bash scripts/verify-full.sh

.PHONY: install-verification
install-verification: ## Install verification package
	@bash verification-package/scripts/install-verification.sh

MAKEFILE_EOF
    echo "  Makefile created."
fi

echo ""
echo "=== Verification package installed ==="
echo ""
echo "Available commands:"
echo "  make verify-commit   # pre-commit checks (staged files)"
echo "  make verify-push     # pre-push checks (type + unit tests)"
echo "  make verify-full     # full suite (what CI runs)"
echo "  make verify-ci       # alias for verify-full"
echo ""
echo "Git hooks installed: pre-commit, pre-push, commit-msg"
echo "CI workflow: .github/workflows/verification.yml"
echo ""
echo "To uninstall: rm .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/commit-msg"
