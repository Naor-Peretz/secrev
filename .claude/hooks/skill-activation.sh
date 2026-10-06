#!/bin/sh
# UserPromptSubmit — route the prompt to the relevant project skills.
# Python, not TypeScript: no node, no npx, no node_modules in a repo whose
# STACK.md treats every dependency as a supply-chain surface.
set -eu
ROOT="${CLAUDE_PROJECT_DIR:-.}"
# H-1 scopes to quality gates ("no `|| true` on a quality gate"), and this is
# a router, not a gate. Exiting 2 from a UserPromptSubmit hook because no
# interpreter was found would break every prompt in the session to report that a
# suggestion could not be made — so this is the one hook that declines instead,
# through `syspy_find` rather than `resolve_syspy`.
#
# **It used to prefer `.venv/bin/python`, which is the worst of the choices.**
# That file is writable by the test suite and was watched by nothing, so a test
# overwriting it owned this hook on every prompt. The script is stdlib-only and
# never needed the environment; it now takes the same unwritable interpreter
# every other hook does. `-I -S` stay, for the reason they were added: without
# `-S` a `.pth` planted in site-packages ran here on each prompt.
SYSPY_LIB="$ROOT/.claude/hooks/lib/syspy.sh"
[ -f "$SYSPY_LIB" ] || exit 0
. "$SYSPY_LIB"
SYSPY=$(syspy_find) || exit 0
exec "$SYSPY" -I -S "$ROOT/.claude/hooks/skill_activation.py"
