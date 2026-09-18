#!/bin/sh
# PostToolUse (Write|Edit) — NFR-3 is the one invariant that cannot be fixed later.
#
# Patterns get revised many times; traversal, normalisation and id derivation do
# not, and getting them wrong invalidates everything built on top (D-4). When one
# of the files that owns those rules is touched, say so and re-run the check.

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"

# JSON is read by lib/hook_input.py, not jq (STACK.md §2). Every path that
# cannot complete the check exits 2, never 0 (H-1).
SYSPY=$(command -v python3 2>/dev/null) || {
    echo "determinism-guard: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
[ -f "$READER" ] || {
    echo "determinism-guard: $READER is missing — cannot check (H-1)." >&2
    exit 2
}

PATHS="$ROOT/.claude/hooks/lib/paths.sh"
[ -f "$PATHS" ] || {
    echo "determinism-guard: $PATHS is missing — cannot check (H-1)." >&2
    exit 2
}
. "$PATHS"

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" "$READER" "$1" || {
        echo "determinism-guard: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}
path=$(read_field file_path)

is_nfr3_path "$path" || exit 0

PY="$ROOT/.venv/bin/python"

echo "── $(basename "$path") owns an NFR-3 rule. Checklist before moving on:"
echo "   · paths collected then sorted() on the POSIX string — never os.walk order"
echo "   · every path NFC-normalised before use, comparison or hashing"
echo "   · CRLF→LF before hashing; line numbers reported against the original"
echo "   · window_sha256 covers window text only — no filename, line, or timestamp"
echo "   · id from (relative_path, rule_id, window_sha256, ordinal) — never a traversal"
echo "     counter, and never 'line': derive() rejects it rather than ignoring it (FR-4.5)"

if [ -d "$ROOT/src/secrev" ] && [ -d "$ROOT/tests/fixtures" ]; then
    if [ ! -x "$PY" ]; then
        # There is something to compare and no interpreter to compare it with.
        # Saying nothing here would read as "determinism holds" (H-1, H-9).
        echo "── NFR-3 NOT re-checked: no .venv. This is not a pass." >&2
        exit 2
    fi
    echo "── re-running the determinism check"
    # Captured, not piped: `cmd | head` makes $? the status of head, which
    # succeeds whatever the check did. NFR-3 is the invariant this project
    # calls unfixable later, and this hook would have announced
    # "byte-identical across runs" over a failing comparison.
    # `if out=$(...)` and not `out=$(...); status=$?`. Under `set -e` a failing
    # command substitution in an assignment exits the script on the spot, so
    # the status line below is never reached and the hook returns the tool's
    # exit code — 1, which the hook protocol gives no meaning (H-9). An `if`
    # condition is the one place `set -e` stands down.
    if out=$("$PY" "$ROOT/scripts/determinism_check.py" 2>&1); then
        status=0
    else
        status=$?
    fi
    printf '%s\n' "$out" | head -20
    if [ "$status" = 0 ]; then
        echo "── byte-identical across runs"
    else
        echo "── determinism check FAILED — see above" >&2
        exit 2
    fi
fi
exit 0
