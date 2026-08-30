#!/bin/sh
# UserPromptSubmit — surface the background gate result exactly once.
#
# async-check.sh runs ruff, pytest and the self-application check in the
# background and writes the output to a log. Until this hook existed, nothing
# read that log: the checks ran and the result was discarded. A check whose
# result no one sees is not a check.
#
# Prints only when the log is newer than the last time it was shown, so a quiet
# session stays quiet. Never blocks: exits 0 on every path.

set -eu
STATE="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/state"
LOG="$STATE/async-check.log"
SEEN="$STATE/async-check.seen"

[ -f "$LOG" ] || exit 0
[ -s "$LOG" ] || exit 0

# Newer than the marker? -nt is POSIX test, and true when SEEN is absent.
if [ -f "$SEEN" ] && [ ! "$LOG" -nt "$SEEN" ]; then
    exit 0
fi

echo "<background-gate>"
echo "Result of the background check that ran after the last edit."
echo "This is the fast half only — ruff, pytest, self-application. It is not"
echo "the gate: mypy and the determinism check run in \`sh scripts/check.sh\`."
echo
sed -n '1,60p' "$LOG"
echo "</background-gate>"

: > "$SEEN"
exit 0
