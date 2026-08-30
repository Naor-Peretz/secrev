"""Route a user prompt to the project skills that apply to it.

Reads .claude/skills/skill-rules.json — same format as the TypeScript router it
replaces, so the rules file is portable between the two. Reimplemented in Python
because this repo's whole argument is that dependencies are surface, and a
`npx tsx` in a UserPromptSubmit hook is a package manager on the critical path
of every prompt.

Emits a short advisory to stdout, which Claude Code adds to the turn's context.
Silent when nothing matches. Never blocks: exits 0 on any error.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

MAX_SUGGESTIONS = 3


def main() -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    rules_path = root / ".claude" / "skills" / "skill-rules.json"
    if not rules_path.is_file():
        return 0

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}
    prompt = str(payload.get("prompt", "")).lower()
    if not prompt:
        return 0

    try:
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    matched: list[tuple[int, str, str]] = []
    for name, rule in (rules.get("skills") or {}).items():
        triggers = rule.get("promptTriggers") or {}
        score = 0

        for keyword in triggers.get("keywords") or []:
            if keyword.lower() in prompt:
                score += 2

        for pattern in triggers.get("intentPatterns") or []:
            try:
                if re.search(pattern, prompt, re.IGNORECASE):
                    score += 3
            except re.error:
                continue  # a broken pattern is a rules bug, not a reason to fail the turn

        if score:
            priority = {"high": 2, "medium": 1}.get(rule.get("priority", ""), 0)
            matched.append((score + priority, name, rule.get("description", "")))

    if not matched:
        return 0

    matched.sort(key=lambda item: (-item[0], item[1]))
    print("<project-skills>")
    print("Skills that apply to this request — read before acting:")
    for _, name, description in matched[:MAX_SUGGESTIONS]:
        print(f"  · {name} — {description}")
    print("</project-skills>")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a hook must never break the turn
        sys.exit(0)
