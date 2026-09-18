#!/bin/sh
# Strategic Compact Suggester
#
# `sh`, not `bash`: STACK.md §1 binds POSIX sh and §8 holds .claude/ to the
# tool's own standards. This was the only `#!/bin/bash` in fourteen shell
# scripts here, and it is the only one this project did not write — the rule
# held wherever someone typed it and broke where code arrived from outside.
# Nothing in the body was bash-specific, so this is a one-line correction.
#
# KNOWN BROKEN, and deliberately not repaired here: the counter below cannot
# work. `$$` is this script's own pid and a hook is a fresh process every time,
# so COUNTER_FILE has a new name on every invocation, the `-f` test is never
# true, the file is rewritten as 1, and neither threshold is ever reached. It
# is vendored third-party content and rewriting its logic is not this
# milestone's business; it is recorded here, in SKILL.md and in BRIEF_M4.md §6
# rather than left to be discovered by someone who wires it up and waits.
# Runs on PreToolUse or periodically to suggest manual compaction at logical intervals
#
# Why manual over auto-compact:
# - Auto-compact happens at arbitrary points, often mid-task
# - Strategic compacting preserves context through logical phases
# - Compact after exploration, before execution
# - Compact after completing a milestone, before starting next
#
# Hook config (in ~/.claude/settings.json):
# {
#   "hooks": {
#     "PreToolUse": [{
#       "matcher": "Edit|Write",
#       "hooks": [{
#         "type": "command",
#         "command": "~/.claude/skills/strategic-compact/suggest-compact.sh"
#       }]
#     }]
#   }
# }
#
# Criteria for suggesting compact:
# - Session has been running for extended period
# - Large number of tool calls made
# - Transitioning from research/exploration to implementation
# - Plan has been finalized

# Track tool call count (increment in a temp file)
COUNTER_FILE="/tmp/claude-tool-count-$$"
THRESHOLD=${COMPACT_THRESHOLD:-50}

# Initialize or increment counter
if [ -f "$COUNTER_FILE" ]; then
  count=$(cat "$COUNTER_FILE")
  count=$((count + 1))
  echo "$count" > "$COUNTER_FILE"
else
  echo "1" > "$COUNTER_FILE"
  count=1
fi

# Suggest compact after threshold tool calls
if [ "$count" -eq "$THRESHOLD" ]; then
  echo "[StrategicCompact] $THRESHOLD tool calls reached - consider /compact if transitioning phases" >&2
fi

# Suggest at regular intervals after threshold
if [ "$count" -gt "$THRESHOLD" ] && [ $((count % 25)) -eq 0 ]; then
  echo "[StrategicCompact] $count tool calls - good checkpoint for /compact if context is stale" >&2
fi
