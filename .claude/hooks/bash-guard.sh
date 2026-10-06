#!/bin/sh
# PreToolUse (Bash) — BRIEF_M0.md §1, the highest-severity item.
#
# STACK.md §8 H-3: guards cover every tool that can write, not every tool that
# usually writes. Under P7 a write is an execution primitive regardless of
# which tool performed it, and Write|Edit|MultiEdit alone leaves Bash open.
#
# The decision lives in bash_guard.py. This wrapper only moves bytes, and every
# path that cannot complete the check exits 2, never 0 (H-1).

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"
DECIDER="$ROOT/.claude/hooks/bash_guard.py"

SYSPY_LIB="$ROOT/.claude/hooks/lib/syspy.sh"
[ -f "$SYSPY_LIB" ] || {
    echo "bash-guard: $SYSPY_LIB is missing — cannot check (H-1)." >&2
    exit 2
}
. "$SYSPY_LIB"
resolve_syspy bash-guard

for required in "$READER" "$DECIDER"; do
    [ -f "$required" ] || {
        echo "bash-guard: $required is missing — cannot check (H-1)." >&2
        exit 2
    }
done

# `-I -S` on every interpreter a hook starts. Found in review: Python puts a
# script's own directory first on sys.path, so a `re.py` or `json.py` planted
# beside a hook replaced the stdlib inside the guard — and one in lib/ owned
# every guard, since each reads its payload through lib/hook_input.py. `-I`
# drops the script directory, user site-packages and PYTHON* variables; `-S`
# drops site-packages altogether, so a `.pth` or `sitecustomize` in whatever
# virtualenv `python3` resolves to cannot run here either. The hooks are
# stdlib-only, so neither costs anything they use.
#
# The flags are given to the interpreter, so which interpreter it is comes first:
# `lib/syspy.sh` picks one the reviewed code cannot rewrite, because
# `command -v python3` searched a PATH whose first entries the user owns.
command=$(printf '%s' "$INPUT" | "$SYSPY" -I -S "$READER" command) || {
    echo "bash-guard: unreadable hook payload — refusing (H-1)." >&2
    exit 2
}

# The decision, with its status mapped: 0 permits, 2 refuses, and anything else
# is "the guard did not run" rather than "the guard found nothing". It used to be
# this line alone, so a crash — or an interpreter too old to parse the decider —
# exited 1, which PreToolUse treats as a non-blocking error, and the write went
# through unexamined.
status=0
printf '%s' "$command" | "$SYSPY" -I -S "$DECIDER" || status=$?
syspy_status "$status" bash-guard
