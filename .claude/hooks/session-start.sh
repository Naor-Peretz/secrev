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
    # Sections named, not numbered. This said "§1 … §2 … §7 (DoD)", which is
    # BRIEF_M1.md's layout; BRIEF_M2.md puts its Definition of done at §4, so
    # the line sent readers to a section that does not exist. A pointer that is
    # wrong about where to look is worse than one that describes what to find.
    echo "Scope for this milestone is ${BRIEF} — read its Scope section (what must not be"
    echo "built yet, with the reason each would be got wrong early), its deliverables,"
    echo "and its Definition of done."
else
    echo "No ${BRIEF} in the repo. Confirm .claude/MILESTONE is current before planning."
fi

[ -d src/secrev ] || echo "src/secrev/ does not exist yet — the gate's later stages skip."
[ -x .venv/bin/python ] || echo "No .venv — hooks fall back to system python3, which lacks ruff/pytest. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"

if [ "$COMMITS" = "0" ]; then
    echo "The repository has no commits. Everything, including this harness, is"
    echo "untracked: a deleted file is unrecoverable and the gate cannot diff."
fi

echo "Precedence when documents disagree: PRD > STACK.md > brief. Raise a conflict; do not resolve it."
echo "</session-context>"
exit 0
