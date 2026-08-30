#!/usr/bin/env python3
"""Read a hook payload on stdin and print one field. Parsing only, no policy.

STACK.md §2 removed `jq`: a non-Python external dependency, undeclared, in a
repository that requires a written reason for every dependency -- and precisely
what §1's prefer-Python rule exists to avoid. This is the replacement.

It knows nothing about which paths are protected or which constructs are
forbidden. That belongs to the guards, so a change in policy never means
editing the parser and a parser bug never quietly changes policy.

Deliberately stdlib-only and run with the system interpreter: it must work
before `.venv` exists, since the guards it feeds are what stand between an
agent and this repository.

Exit: 0 with the field on stdout - 2 when the payload cannot be read. There is
no third outcome. A guard that cannot read its own input has not concluded the
write is safe (STACK.md §8 H-1).
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _file_path(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    value = tool_input.get("file_path")
    return value if isinstance(value, str) else ""


def _command(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    value = tool_input.get("command")
    return value if isinstance(value, str) else ""


def _tool_name(payload: dict[str, Any]) -> str:
    for key in ("tool_name", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _body(payload: dict[str, Any]) -> str:
    """Every piece of text the write would introduce, newline-joined.

    Write sends `content`; Edit sends `new_string`; MultiEdit sends a list of
    edits. A guard that inspects only the first sees an edit as empty and
    permits it.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    parts: list[str] = []
    for key in ("content", "new_string"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                value = edit.get("new_string")
                if isinstance(value, str):
                    parts.append(value)
    return "\n".join(parts)


FIELDS = {
    "file_path": _file_path,
    "command": _command,
    "tool_name": _tool_name,
    "body": _body,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in FIELDS:
        sys.stderr.write(f"usage: hook_input.py {{{'|'.join(sorted(FIELDS))}}}\n")
        return 2
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"hook_input.py: unreadable payload: {exc}\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write("hook_input.py: payload is not an object\n")
        return 2
    sys.stdout.write(FIELDS[argv[1]](payload))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
