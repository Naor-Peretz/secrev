#!/bin/sh
# PostToolUse (ExitPlanMode) — every plan gets an independent read before code.
#
# Ported from the plan→review→gate loop. Two deliberate changes: milestone
# branch names instead of plan/*, and no automatic commit or push — that is the
# user's call, so the workflow stops at "offer".

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"

# JSON is read by lib/hook_input.py, not jq (STACK.md §2). Every path that
# cannot complete the check exits 2, never 0 (H-1).
SYSPY=$(command -v python3 2>/dev/null) || {
    echo "plan-review: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
[ -f "$READER" ] || {
    echo "plan-review: $READER is missing — cannot check (H-1)." >&2
    exit 2
}

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" "$READER" "$1" || {
        echo "plan-review: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}
tool=$(read_field tool_name)
[ "$tool" = "ExitPlanMode" ] || exit 0

MILESTONE=$(cat "$ROOT/.claude/MILESTONE" 2>/dev/null || echo M1)
BRANCH=$(git -C "$ROOT" branch --show-current 2>/dev/null || echo "?")

cat <<EOF
<plan-review-workflow>
A plan was just produced for ${MILESTONE}. Current branch: ${BRANCH}

1. Review it. Use the Task tool with subagent_type="plan-reviewer". Wait for the result.
   The reviewer's first job is not "is this a good plan" but "does this plan match the
   brief" — the specification is the authority here, not the plan's internal coherence.

2. Check it against the brief before writing code:
   · Does anything in the plan belong to a later milestone? (BRIEF §1 lists what must not
     be built yet, with the reason each would be got wrong early.)
   · Does anything conflict with STACK.md or the PRD? If so, raise it — do not resolve it.
     A conflict usually means a document needs a correction, and quietly picking a side
     loses that signal (BRIEF §8).
   · Is every item in the Definition of Done covered?

3. Branch, if not already on one: git checkout -b $(printf '%s' "${MILESTONE}" | tr 'A-Z' 'a-z')/<short-topic>

4. Report the review outcome and ASK before committing or pushing anything.
</plan-review-workflow>
EOF
exit 0
