#!/bin/sh
# PostToolUse (Write|Edit) — NFR-3 is the one invariant that cannot be fixed later.
#
# Patterns get revised many times; traversal, normalisation and id derivation do
# not, and getting them wrong invalidates everything built on top (D-4). When one
# of the files that owns those rules is touched, say so and re-run the check.

set -eu
INPUT=$(cat)
path=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')

case "$path" in
  */src/secrev/ids.py|*/src/secrev/inventory.py|*/src/secrev/sweep.py|*/src/secrev/recon.py) ;;
  *) exit 0 ;;
esac

ROOT="${CLAUDE_PROJECT_DIR:-.}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3 || true)

echo "── $(basename "$path") owns an NFR-3 rule. Checklist before moving on:"
echo "   · paths collected then sorted() on the POSIX string — never os.walk order"
echo "   · every path NFC-normalised before use, comparison or hashing"
echo "   · CRLF→LF before hashing; line numbers reported against the original"
echo "   · window_sha256 covers window text only — no filename, line, or timestamp"
echo "   · id from (relative_path, line, rule_id, ordinal), never a traversal counter"

if [ -n "$PY" ] && [ -d "$ROOT/src/secrev" ] && [ -d "$ROOT/tests/fixtures" ]; then
    echo "── re-running the determinism check"
    "$PY" "$ROOT/scripts/determinism_check.py" 2>&1 | head -20 || true
fi
exit 0
