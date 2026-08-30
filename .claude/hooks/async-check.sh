#!/bin/sh
# PostToolUse (Write|Edit) — run the fast half of the gate in the background.
#
# Ported from the async-build/tsc pattern: same debounce, same tracker file,
# different checker. ruff and pytest replace tsc, and nothing blocks — the
# result is read on the next turn or by `/check`.

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"

# JSON is read by lib/hook_input.py, not jq (STACK.md §2). Every path that
# cannot complete the check exits 2, never 0 (H-1).
SYSPY=$(command -v python3 2>/dev/null) || {
    echo "async-check: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
[ -f "$READER" ] || {
    echo "async-check: $READER is missing — cannot check (H-1)." >&2
    exit 2
}

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" "$READER" "$1" || {
        echo "async-check: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}
path=$(read_field file_path)
case "$path" in
  *.py) ;;
  *) exit 0 ;;
esac

# State lives in the checkout, not $TMPDIR: a global name collides between two
# clones of this repo on one machine, and the wrong clone's result then decides
# whether a hook speaks. Gitignored via .claude/.gitignore.
STATE="$ROOT/.claude/hooks/state"
mkdir -p "$STATE" 2>/dev/null || exit 0
STAMP="$STATE/async-check.stamp"
LOG="$STATE/async-check.log"

now=$(date +%s)
if [ -f "$STAMP" ]; then
    last=$(cat "$STAMP" 2>/dev/null || echo 0)
    [ $((now - last)) -lt 20 ] && exit 0
fi
echo "$now" > "$STAMP"

# The quality checks run from .venv and nowhere else. System python3 has no
# ruff or pytest, so falling back to it produced three "no module named …"
# lines that the `|| true` below then swallowed: the hook reported nothing and
# meant nothing. Reading the payload is different and deliberately still uses
# system python3 — lib/hook_input.py is stdlib, and a guard that stops working
# because .venv is missing is worse than one that works everywhere.
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
    {
        echo "=== environment ==="
        echo "No .venv, so ruff, pytest and the self-application check did NOT run."
        echo "This is \"I did not check\", not \"I checked and it is fine\" (STACK.md §8 H-1)."
        echo "Run: python3 -m venv .venv && .venv/bin/pip install ruff pytest mypy"
    } > "$LOG" 2>&1
    exit 0
fi

# Each check records its own outcome. No `|| true`: a tool that is absent and a
# tool that passed are different states, and collapsing them is the H-1 breach
# this hook used to commit three times per run.
(
    {
        for check in ruff pytest self-application; do
            echo "=== $check ==="
            # Output is captured first and trimmed second. Piping the tool
            # straight into head/tail makes $? the status of head or tail,
            # which succeeds whatever the tool did — the check would report
            # [ok] for every failure. POSIX sh has no PIPESTATUS, so the
            # pipeline is the thing to avoid rather than to work around.
            case "$check" in
              ruff)    out=$("$PY" -m ruff check "$ROOT" 2>&1) ;;
              pytest)  out=$("$PY" -m pytest -x -q "$ROOT" 2>&1) ;;
              *)       out=$("$PY" "$ROOT/scripts/self_check.py" 2>&1) ;;
            esac
            status=$?
            printf '%s\n' "$out" | head -30
            if [ "$status" = 0 ]; then
                echo "[ok] $check"
            else
                echo "[FAILED] $check — exit $status"
            fi
        done
    } > "$LOG" 2>&1
) &

exit 0
