#!/bin/sh
# PreToolUse (Write|Edit) — STACK.md §2.1 and NFR-4, enforced at the keystroke.
#
# The gate in scripts/check.sh catches these too, but only after the fact. This
# stops the write, which matters because the constructs below are exactly what
# `secrev` exists to flag in other people's code. AC-10 is not a release-time
# checkbox; it is a property the codebase has to keep continuously.
#
# Blocks with exit 2 so the message reaches Claude rather than the user's log.

set -eu
INPUT=$(cat)

path=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""')
case "$path" in
  */src/secrev/*.py) ;;
  *) exit 0 ;;
esac

body=$(printf '%s' "$INPUT" | jq -r '
  [.tool_input.content?, .tool_input.new_string?, (.tool_input.edits? // [])[]?.new_string]
  | map(select(. != null)) | join("\n")
')
[ -n "$body" ] || exit 0

violation=""
flag() { violation="${violation}  - $1\n"; }

printf '%s' "$body" | grep -qE '(^|[^a-zA-Z_.])eval[[:space:]]*\('     && flag "eval( — STACK.md §2.1"
printf '%s' "$body" | grep -qE '(^|[^a-zA-Z_.])exec[[:space:]]*\('     && flag "exec( — STACK.md §2.1"
printf '%s' "$body" | grep -qE '\bpickle\.|\bimport pickle\b'          && flag "pickle — STACK.md §2.1"
printf '%s' "$body" | grep -qE '\bmarshal\.loads?\b'                   && flag "marshal — STACK.md §2.1"
printf '%s' "$body" | grep -qE 'yaml\.(load|unsafe_load|full_load)[[:space:]]*\(' \
  && flag "yaml.load — STACK.md §2.1 requires yaml.safe_load, and forbids Loader= entirely"
printf '%s' "$body" | grep -qE 'Loader[[:space:]]*='                   && flag "Loader= — STACK.md §2.1"
printf '%s' "$body" | grep -qE 'shell[[:space:]]*=[[:space:]]*True'    && flag "shell=True — STACK.md §2.1"
printf '%s' "$body" | grep -qE '\b(requests|httpx|aiohttp)\b|urllib\.request|http\.client' \
  && flag "network client — NFR-4 forbids runtime egress; everything works on a local copy"

[ -z "$violation" ] && exit 0

{
  echo "BLOCKED — this write would put into src/secrev/ a construct that secrev flags in others."
  echo
  printf '%b' "$violation"
  echo "A scanner that flags yaml.load and then calls it is not credible (STACK.md §2.1)."
  echo "If one of these is genuinely required, that is a STACK.md amendment, not a local exception."
} >&2
exit 2
