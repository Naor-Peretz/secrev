#!/bin/sh
# PostToolUse (Write|Edit) — run the fast half of the gate in the background.
#
# Ported from the async-build/tsc pattern: same debounce, same tracker file,
# different checker. ruff and pytest replace tsc, and nothing blocks — the
# result is read on the next turn or by `/check`.

set -eu
INPUT=$(cat)
path=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')
case "$path" in
  *.py) ;;
  *) exit 0 ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-.}"
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

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3 || true)
[ -n "$PY" ] || exit 0

(
    {
        echo "=== ruff ==="
        "$PY" -m ruff check "$ROOT" 2>&1 | head -30 || true
        echo "=== pytest ==="
        "$PY" -m pytest -x -q "$ROOT" 2>&1 | tail -20 || true
        echo "=== self-application ==="
        "$PY" "$ROOT/scripts/self_check.py" 2>&1 | head -20 || true
    } > "$LOG" 2>&1
) &

exit 0
