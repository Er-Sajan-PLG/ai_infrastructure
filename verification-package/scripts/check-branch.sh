#!/usr/bin/env bash
#
# Branch enforcement: config-driven branch protection.
#
# Usage: bash scripts/check-branch.sh
# Exit 0: on a valid feature branch
# Exit 1: on a protected branch or naming violation
#
# Reads config from verification-package/config/branch-guard.conf

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

GUARD_CONFIG="$REPO_ROOT/verification-package/config/branch-guard.conf"
if [ -f "$GUARD_CONFIG" ]; then
    source "$GUARD_CONFIG"
else
    PROTECTED_BRANCHES=("main" "master")
    BRANCH_PATTERN="^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)/[a-z0-9][a-z0-9-]*$"
fi

BRANCH=$(git branch --show-current)

# Check protected branches
for pattern in "${PROTECTED_BRANCHES[@]}"; do
    if [[ "$BRANCH" =~ ^$pattern$ ]]; then
        echo "" >&2
        echo "check-branch FAILED: '$BRANCH' is a protected branch." >&2
        echo "New work must start with a new branch:" >&2
        echo "  git checkout -b <type>/<description>" >&2
        exit 1
    fi
done

# Check naming convention
if ! [[ "$BRANCH" =~ $BRANCH_PATTERN ]]; then
    echo "" >&2
    echo "check-branch FAILED: branch '$BRANCH' does not match naming convention." >&2
    echo "Expected: <type>/<description>" >&2
    echo "Types: feat fix chore docs refactor test ci build perf revert" >&2
    exit 1
fi

echo "check-branch: on '$BRANCH' — OK"
exit 0
