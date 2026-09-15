#!/usr/bin/env python3
"""Emit a PreToolUse `ask` decision. The reason arrives on stdin.

The counterpart to hook_input.py, and the other half of removing jq: two
guards used `jq -n` to build this payload rather than to read one, so a reader
alone would not have finished the job (STACK.md §2).

`ask` rather than `deny` is the point. Both guards that use this cover
decisions the specification says must be raised and not resolved -- milestone
scope (BRIEF §1) and edits to a binding document (BRIEF §8) -- so the decision
goes in front of a human instead of being guessed at.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    reason = sys.stdin.read()
    if not reason.strip():
        sys.stderr.write("hook_ask.py: empty reason — refusing to emit\n")
        return 2
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
