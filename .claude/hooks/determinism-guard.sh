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

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" "$READER" "$1" || {
        echo "determinism-guard: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}
path=$(read_field file_path)

case "$path" in
  *src/secrev/ids.py|*src/secrev/inventory.py|*src/secrev/sweep.py|*src/secrev/recon.py) ;;
  *) exit 0 ;;
esac

PY="$ROOT/.venv/bin/python"

echo "── $(basename "$path") owns an NFR-3 rule. Checklist before moving on:"
echo "   · paths collected then sorted() on the POSIX string — never os.walk order"
echo "   · every path NFC-normalised before use, comparison or hashing"
echo "   · CRLF→LF before hashing; line numbers reported against the original"
echo "   · window_sha256 covers window text only — no filename, line, or timestamp"
echo "   · id from (relative_path, line, rule_id, ordinal), never a traversal counter"

if [ -d "$ROOT/src/secrev" ] && [ -d "$ROOT/tests/fixtures" ]; then
    if [ ! -x "$PY" ]; then
        # There is something to compare and no interpreter to compare it with.
        # Saying nothing here would read as "determinism holds" (H-1, H-9).
        echo "── NFR-3 NOT re-checked: no .venv. This is not a pass." >&2
        exit 2
    fi
    echo "── re-running the determinism check"
    if "$PY" "$ROOT/scripts/determinism_check.py" 2>&1 | head -20; then
        echo "── byte-identical across runs"
    else
        echo "── determinism check FAILED — see above" >&2
        exit 2
    fi
fi
exit 0
