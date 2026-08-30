#!/bin/sh
# UserPromptSubmit — route the prompt to the relevant project skills.
# Python, not TypeScript: no node, no npx, no node_modules in a repo whose
# STACK.md treats every dependency as a supply-chain surface.
set -eu
ROOT="${CLAUDE_PROJECT_DIR:-.}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3 || true)
[ -n "$PY" ] || exit 0
exec "$PY" "$ROOT/.claude/hooks/skill_activation.py"
