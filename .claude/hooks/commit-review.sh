#!/bin/sh
# PreToolUse (Bash) — the commit checkpoint that replaced hand-staging.
#
# Owner decision, 2026-09-22: `git add` no longer needs the owner, so the owner's
# look at what is going in moved to commit. This hook is what lets commit carry
# it: on any `git commit` it asks, with the staged set in the reason and every
# protected path and mode change marked. The logic lives in commit_review.py;
# this wrapper moves bytes, and every path that cannot complete exits 2 (H-1).

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"
ASKER="$ROOT/.claude/hooks/lib/hook_ask.py"
REVIEWER="$ROOT/.claude/hooks/commit_review.py"

SYSPY_LIB="$ROOT/.claude/hooks/lib/syspy.sh"
[ -f "$SYSPY_LIB" ] || {
    echo "commit-review: $SYSPY_LIB is missing — cannot check (H-1)." >&2
    exit 2
}
. "$SYSPY_LIB"
resolve_syspy commit-review

for required in "$READER" "$ASKER" "$REVIEWER"; do
    [ -f "$required" ] || {
        echo "commit-review: $required is missing — cannot check (H-1)." >&2
        exit 2
    }
done

# `-I -S` for the reason bash-guard.sh records: a module planted beside a hook
# must not be what the hook imports.
command=$(printf '%s' "$INPUT" | "$SYSPY" -I -S "$READER" command) || {
    echo "commit-review: unreadable hook payload — refusing (H-1)." >&2
    exit 2
}

# `if reason=$(...)` so a failure is caught here rather than by `set -e`, which
# would exit with the reviewer's status unexamined (the async-check lesson).
# Every failure is exit 2 here, whatever the status was: this checkpoint cannot
# show what a commit records, so it refuses rather than waving it through.
cd "$ROOT"
if reason=$(printf '%s' "$command" | "$SYSPY" -I -S "$REVIEWER"); then
    :
else
    exit 2
fi

# Not a commit: no opinion, no output.
[ -n "$reason" ] || exit 0
printf '%s' "$reason" | "$SYSPY" -I -S "$ASKER"
