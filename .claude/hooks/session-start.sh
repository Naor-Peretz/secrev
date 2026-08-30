#!/bin/sh
# SessionStart — state the session needs in its first turn, not its fifth.
#
# .claude/MILESTONE drove the scope guard from the beginning, but only at write
# time: an agent discovered which milestone it was in by being interrupted while
# violating it. This states it up front. Cheap facts only — nothing here runs
# the gate, which is slow and belongs to /check.

set -eu
ROOT="${CLAUDE_PROJECT_DIR:-.}"
cd "$ROOT" 2>/dev/null || exit 0

MILESTONE=$(cat .claude/MILESTONE 2>/dev/null || echo "unset")
BRIEF="BRIEF_${MILESTONE}.md"
BRANCH=$(git branch --show-current 2>/dev/null || echo "?")
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
COMMITS=$(git rev-list --count HEAD 2>/dev/null || echo 0)

echo "<session-context>"
echo "Milestone: ${MILESTONE}  ·  branch: ${BRANCH}  ·  uncommitted paths: ${DIRTY}"

if [ -f "$BRIEF" ]; then
    echo "Scope for this milestone is ${BRIEF} — §1 (what must not be built yet,"
    echo "with the reason each would be got wrong early), §2 (deliverables), §7 (DoD)."
else
    echo "No ${BRIEF} in the repo. Confirm .claude/MILESTONE is current before planning."
fi

[ -d src/secrev ] || echo "src/secrev/ does not exist yet — the gate's later stages skip."
[ -x .venv/bin/python ] || echo "No .venv — hooks fall back to system python3, which lacks ruff/pytest. Run: uv sync"

if [ "$COMMITS" = "0" ]; then
    echo "The repository has no commits. Everything, including this harness, is"
    echo "untracked: a deleted file is unrecoverable and the gate cannot diff."
fi

echo "Precedence when documents disagree: PRD > STACK.md > brief. Raise a conflict; do not resolve it."
echo "</session-context>"
exit 0
