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

PY=$(command -v python3 2>/dev/null) || {
    echo "bash-guard: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
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
command=$(printf '%s' "$INPUT" | "$PY" -I -S "$READER" command) || {
    echo "bash-guard: unreadable hook payload — refusing (H-1)." >&2
    exit 2
}

printf '%s' "$command" | "$PY" -I -S "$DECIDER"
