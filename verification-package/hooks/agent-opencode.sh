#!/usr/bin/env bash
#
# OpenCode PreToolUse hook: branch enforcement for AI agents.
#
# Place in .opencode.json or .opencode/settings.json:
# {
#   "hooks": {
#     "preToolUse": [
#       {
#         "matcher": "bash",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "bash verification-package/hooks/agent-opencode.sh"
#           }
#         ]
#       }
#     ]
#   }
# }
#
# This fires BEFORE any tool use (including git commit), not just at commit time.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$REPO_ROOT"

GUARD_CONFIG="$REPO_ROOT/verification-package/config/branch-guard.conf"
if [ -f "$GUARD_CONFIG" ]; then
    source "$GUARD_CONFIG"
else
    PROTECTED_BRANCHES=("main" "master")
    BRANCH_PATTERN="^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)/[a-z0-9][a-z0-9-]*$"
    AGENT_PREFIX="agent"
fi

BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

# Check protected branches
for pattern in "${PROTECTED_BRANCHES[@]}"; do
    if [[ "$BRANCH" =~ ^$pattern$ ]]; then
        echo "BLOCKED: '$BRANCH' is a protected branch. Use: git checkout -b <type>/<description>"
        exit 2
    fi
done

# Check naming convention
if ! [[ "$BRANCH" =~ $BRANCH_PATTERN ]]; then
    echo "BLOCKED: branch '$BRANCH' does not match naming convention. Use: <type>/<description>"
    exit 2
fi

# Agent prefix check
if [[ ! "$BRANCH" == $AGENT_PREFIX/* ]]; then
    echo "BLOCKED: agent must use $AGENT_PREFIX/ prefix. Use: $AGENT_PREFIX/<type>/<description>"
    exit 2
fi

exit 0
