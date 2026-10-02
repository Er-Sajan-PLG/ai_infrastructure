#!/usr/bin/env bash
#
# Background watcher: monitor branch and alert on protected branch.
#
# Usage:
#   bash verification-package/scripts/branch-watcher.sh start   # start watcher
#   bash verification-package/scripts/branch-watcher.sh stop    # stop watcher
#   bash verification-package/scripts/branch-watcher.sh status  # check status
#
# The watcher runs a background loop that checks the current branch
# every 30 seconds. If on a protected branch, it prints a warning.
# If BLOCK_ON_PROTECTED=1, it also kills the shell session.
#
# Installed by scripts/install-verification.sh.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

GUARD_CONFIG="$REPO_ROOT/verification-package/config/branch-guard.conf"
if [ -f "$GUARD_CONFIG" ]; then
    source "$GUARD_CONFIG"
else
    PROTECTED_BRANCHES=("main" "master")
    BRANCH_PATTERN="^(feat|fix|chore|docs|refactor|test|ci|build|perf|revert)/[a-z0-9][a-z0-9-]*$"
    BLOCK_ON_PROTECTED=0
fi

PID_FILE="$REPO_ROOT/.git/branch-watcher.pid"
LOG_FILE="$REPO_ROOT/.git/branch-watcher.log"

start_watcher() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Watcher already running (PID $(cat "$PID_FILE"))"
        return 0
    fi

    echo "Starting branch watcher..."

    (
        while true; do
            BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

            for pattern in "${PROTECTED_BRANCHES[@]}"; do
                if [[ "$BRANCH" =~ ^$pattern$ ]]; then
                    echo "[$(date)] WARNING: on protected branch '$BRANCH'" >> "$LOG_FILE"
                    if [ "${BLOCK_ON_PROTECTED:-0}" = "1" ]; then
                        echo "[$(date)] BLOCK_ON_PROTECTED=1 — killing session" >> "$LOG_FILE"
                        kill -TERM $$ 2>/dev/null || true
                    fi
                    break
                fi
            done

            if ! [[ "$BRANCH" =~ $BRANCH_PATTERN ]]; then
                echo "[$(date)] WARNING: branch '$BRANCH' does not match naming convention" >> "$LOG_FILE"
            fi

            sleep 30
        done
    ) &

    echo $! > "$PID_FILE"
    echo "Watcher started (PID $(cat "$PID_FILE")). Log: $LOG_FILE"
}

stop_watcher() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            echo "Watcher stopped (PID $PID)"
        else
            echo "Watcher not running (stale PID file)"
        fi
        rm -f "$PID_FILE"
    else
        echo "Watcher not running (no PID file)"
    fi
}

status_watcher() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Watcher running (PID $(cat "$PID_FILE"))"
        echo "Log: $LOG_FILE"
        [ -f "$LOG_FILE" ] && tail -5 "$LOG_FILE"
    else
        echo "Watcher not running"
    fi
}

case "${1:-}" in
    start)  start_watcher ;;
    stop)   stop_watcher ;;
    status) status_watcher ;;
    *)
        echo "Usage: bash scripts/branch-watcher.sh {start|stop|status}"
        exit 2
        ;;
esac
