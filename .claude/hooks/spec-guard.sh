#!/bin/sh
# PreToolUse (Write|Edit) on the three binding documents.
#
# Precedence is PRD > STACK.md > brief, and a conflict between a brief and the
# PRD usually means the PRD needs a correction — resolving it quietly destroys
# that signal (BRIEF_M1.md §8). An edit to any of the three is therefore a
# decision, and decisions go to the human.

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"

# JSON is read by lib/hook_input.py, not jq (STACK.md §2). Every path that
# cannot complete the check exits 2, never 0 (H-1).
SYSPY=$(command -v python3 2>/dev/null) || {
    echo "spec-guard: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
[ -f "$READER" ] || {
    echo "spec-guard: $READER is missing — cannot check (H-1)." >&2
    exit 2
}

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" -I -S "$READER" "$1" || {
        echo "spec-guard: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}
path=$(read_field file_path)

case "$path" in
  *REQUIREMENTS_security-review-skill.md) doc="the PRD — authoritative on intent (P1–P11, FRs, guardrails, decisions)" ;;
  *STACK.md)   doc="STACK.md — binding on mechanism for every milestone" ;;
  *BRIEF_M1.md|*BRIEF_M*.md) doc="a milestone brief — the narrowest of the three, and it loses to both" ;;
  *) exit 0 ;;
esac

reason="About to edit ${doc}.

Precedence: a brief loses to STACK.md; STACK.md loses to the PRD on intent and wins on mechanism.
Before writing, confirm which of these this is:
  · recording a decision already taken elsewhere  → fine
  · resolving a conflict between two documents    → raise it instead; the conflict is the signal
  · relaxing an invariant to make code compile    → the code is wrong, not the document

Adding a runtime dependency, changing an exit code, or weakening a determinism rule are all
STACK.md amendments with a written reason, never local exceptions."

printf '%s' "$reason" | "$SYSPY" -I -S "$ROOT/.claude/hooks/lib/hook_ask.py"
exit 0
