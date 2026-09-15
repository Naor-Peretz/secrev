#!/bin/sh
# Stop — one question at the end of a turn: is the work verified?
#
# Silent by design. It speaks only when a source file has changed since the last
# green gate, which is the one state where stopping is premature. Anything
# noisier than that gets ignored within a day, and then it is not a check.

set -eu
ROOT="${CLAUDE_PROJECT_DIR:-.}"
cd "$ROOT" 2>/dev/null || exit 0

# The product gate's marker, in the product's own space. It used to be written
# into .claude/hooks/state/, which made scripts/check.sh reach into the harness
# — a dependency pointing from the thing being built into the thing building
# it. The harness reads it; nothing in the product writes here.
STAMP=".gate-passed"

changed=$(git status --porcelain -- src tests patterns scripts 2>/dev/null | wc -l | tr -d ' ')
[ "$changed" = "0" ] && exit 0

# Newest mtime among the paths the gate actually covers.
newest=$(find src tests patterns scripts -type f \
           \( -name '*.py' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sh' \) \
           -newer "$STAMP" 2>/dev/null | head -1 || true)

if [ ! -f "$STAMP" ]; then
    echo "The gate has not run in this session and ${changed} path(s) under src/tests/patterns/scripts have changed. Run /check before treating the work as done."
elif [ -n "$newest" ]; then
    echo "Changed since the last green gate: ${newest}$([ "$changed" -gt 1 ] && echo " (and others)"). Run /check — the pre-commit hook runs the same script and will find it anyway."
fi
exit 0
