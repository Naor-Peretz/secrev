#!/bin/sh
# UserPromptSubmit — route the prompt to the relevant project skills.
# Python, not TypeScript: no node, no npx, no node_modules in a repo whose
# STACK.md treats every dependency as a supply-chain surface.
set -eu
ROOT="${CLAUDE_PROJECT_DIR:-.}"
# H-1 scopes to quality gates ("no `|| true` on a quality gate"), and this is
# a router, not a gate. Exiting 2 from a UserPromptSubmit hook because .venv
# is missing would break every prompt in the session to report that a
# suggestion could not be made. The script it runs is stdlib-only, so system
# python3 is a real fallback here rather than a swallowed failure.
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3 2>/dev/null) || exit 0
# `-I -S`: this runs on every prompt, and it preferred the venv's interpreter —
# so without `-S` a `.pth` planted in .venv's site-packages would run on each
# one. It is stdlib-only and needs neither the script directory nor site.
exec "$PY" -I -S "$ROOT/.claude/hooks/skill_activation.py"
