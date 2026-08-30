#!/bin/sh
# PreToolUse (Write|Edit) — milestone scope discipline (BRIEF_M1.md §1, §8).
#
# The realistic failure mode when building M1 is not a bug. It is an agent
# adding something that looks like an obvious improvement and is explicitly a
# later milestone: a severity decision, a dedup by location, a `multiline`
# field "for later". Each of those is forbidden by name in the brief, and each
# looks reasonable to anyone who has not read it.
#
# This does not block. It returns `ask`, which puts the call in front of the
# human — BRIEF_M1.md §8: raise a conflict, do not resolve it silently.

set -eu
INPUT=$(cat)

MILESTONE=$(cat "${CLAUDE_PROJECT_DIR:-.}/.claude/MILESTONE" 2>/dev/null || echo M1)
[ "$MILESTONE" = "M1" ] || exit 0

path=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')
case "$path" in
  */src/secrev/*|*/patterns/*) ;;
  *) exit 0 ;;
esac

body=$(printf '%s' "$INPUT" | jq -r '
  [.tool_input.content?, .tool_input.new_string?, (.tool_input.edits? // [])[]?.new_string]
  | map(select(. != null)) | join("\n")
')
[ -n "$body" ] || exit 0

concerns=""
note() { concerns="${concerns}• $1 "; }

# severity_hint is a legitimate M1 catalog field; deciding a severity is not.
printf '%s' "$body" \
  | grep -vE 'severity_hint' \
  | grep -qE '\bseverity\b[[:space:]]*[:=]|def .*(severity|triage|classify)' \
  && note "assigns or computes a severity — Phase 6 / M6. In M1 patterns are questions, not verdicts (FR-3.2)."

printf '%s' "$body" | grep -qE 'dedup|deduplicat|seen_locations|\(file,[[:space:]]*line\)[[:space:]]*in ' \
  && note "deduplicates by location — D-6 says two patterns on one line stay two hits, always."

printf '%s' "$body" | grep -qE '\bmultiline\b|re\.MULTILINE|re\.DOTALL' \
  && note "introduces multi-line matching — BRIEF §4 forbids it in M1; cross-line reasoning is a structural rule (M4) by definition."

printf '%s' "$body" | grep -qE '^import ast|^from ast |ast\.parse' \
  && note "uses the AST — that is structure.py, M4. The ledger format has to settle first."

printf '%s' "$body" | grep -qE '\bsurfaces?\b.*entry.?point|def .*surface' \
  && note "enumerates surfaces — M2, a separate candidate source with separate semantics."

printf '%s' "$body" | grep -qE '\bunresolved\b.*(count|gate|block)|def verify_ledger' \
  && note "gates on the ledger — M7. Nothing to gate until three sources exist."

[ -z "$concerns" ] && exit 0

reason="Milestone scope check (BRIEF_M1.md §1). This write appears to reach past M1: ${concerns}
Building it now is not merely early — the brief says each of these gets designed wrong before its
prerequisite lands. If it is genuinely needed, that is a conflict with the brief and should be
raised (BRIEF_M1.md §8), not resolved here."

jq -n --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $r
  }
}'
exit 0
