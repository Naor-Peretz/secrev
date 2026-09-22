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

PY=$(command -v python3 2>/dev/null) || {
    echo "commit-review: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
for required in "$READER" "$ASKER" "$REVIEWER"; do
    [ -f "$required" ] || {
        echo "commit-review: $required is missing — cannot check (H-1)." >&2
        exit 2
    }
done

# `-I -S` for the reason bash-guard.sh records: a module planted beside a hook
# must not be what the hook imports.
command=$(printf '%s' "$INPUT" | "$PY" -I -S "$READER" command) || {
    echo "commit-review: unreadable hook payload — refusing (H-1)." >&2
    exit 2
}

# `if reason=$(...)` so a failure is caught here rather than by `set -e`, which
# would exit with the reviewer's status unexamined (the async-check lesson).
cd "$ROOT"
if reason=$(printf '%s' "$command" | "$PY" -I -S "$REVIEWER"); then
    :
else
    exit 2
fi

# Not a commit: no opinion, no output.
[ -n "$reason" ] || exit 0
printf '%s' "$reason" | "$PY" -I -S "$ASKER"
