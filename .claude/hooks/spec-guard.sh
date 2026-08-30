#!/bin/sh
# PreToolUse (Write|Edit) on the three binding documents.
#
# Precedence is PRD > STACK.md > brief, and a conflict between a brief and the
# PRD usually means the PRD needs a correction — resolving it quietly destroys
# that signal (BRIEF_M1.md §8). An edit to any of the three is therefore a
# decision, and decisions go to the human.

set -eu
INPUT=$(cat)
path=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')

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

jq -n --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $r
  }
}'
exit 0
