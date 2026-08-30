#!/usr/bin/env python3
"""Decide whether a Bash command may touch a protected path. Allowlist only.

BRIEF_M0.md §1: guards hook Write|Edit|MultiEdit, so a write performed through
Bash -- heredoc, `tee`, `sed -i`, `>` -- bypasses every one of them while the
harness still reports green. This closes that path.

STACK.md §8 H-2 fixes the polarity: permit a known-safe set and refuse
everything else. Do not enumerate write verbs. `tee`, heredocs, `sed -i`, `>`,
`>>`, `cp`, `mv`, `install`, `python3 -c` and `dd` are not a closeable list,
and adding another verb to a block list is the signal that the polarity is
wrong. This project's founding finding was a denylist bypass (P3); reproducing
that shape in the harness guarding the project would be hard to defend.

The same inversion is applied twice more, and both times it removes a special
case rather than adding one:

  Syntax.  Redirection is how an allowlisted command performs a write:
  `cat > src/secrev/cli.py <<'EOF'` runs `cat`, which is read-only, and writes
  the file anyway. Enumerating redirect operators repeats the mistake one level
  down -- miss `>|` and the write goes through. So the *separators* are
  allowlisted (`&&`, `||`, `;`, `|`) and every other punctuation token near a
  protected path is a refusal.

  Base directory.  `cd src/secrev && sed -i ...` moves the resolution base so a
  later relative path names a protected file without spelling it. There is no
  `cd` rule here: `cd` is not read-only, so the command allowlist already
  refuses it -- and so, for the same reason and with no further code, do
  `pushd`, `git -C`, `env -C`, `make -C` and `find -execdir`.

Exit: 0 permit - 2 refuse. A command that cannot be parsed is refused, because
a guard that could not read its input has not concluded the write is safe
(H-1).

KNOWN LIMIT, recorded rather than papered over. The trigger below asks whether
a command *mentions* a protected path, which is a test over path spellings, and
spellings do not close: `$HOME/secrev/src/secrev/cli.py`, `./sr*/secrev/*.py`,
`$P/cli.py` and `tar -x` all evade it. The verb polarity is right; the path
polarity is inherited from H-2's own wording and is the subject of open
question 8 in .claude/TASKS_M0.md. Fixing it means making the trigger "the
command is read-only" rather than "the command mentions a protected path",
which refuses `uv sync`, `pytest` and `git commit` and needs its own allowlist.
That is a decision for a human, not something to settle inside this file.
"""

from __future__ import annotations

import re
import shlex
import sys

# The only two values PreToolUse gives meaning to (STACK.md §8 H-9). Named
# because a guard that answers outside the protocol's vocabulary has not
# answered — this milestone found three doing exactly that.
PERMIT = 0
REFUSE = 2

# STACK.md §8 H-4. Note H-5 and every existing hook say `src/secrev/`; H-4 says
# `src/`. Taking the broader one -- STACK.md wins on mechanism -- and the
# divergence is open question 5.
PROTECTED = ("src", "patterns", "scripts")
# The boundary is "not a path-name character" rather than "/ or start", so a
# path inside a quoted argument still counts: shlex strips the quotes and
# leaves `open('scripts/check.sh'` as one token. This widens the trigger; it
# does not close it. See the KNOWN LIMIT above.
PROTECTED_RE = re.compile(r"(?:^|[^\w.-])(" + "|".join(PROTECTED) + r")(?:/|$)")

# Read-only commands. `find` is deliberately absent: it carries -delete and
# -exec, so admitting it re-creates the shape H-2 forbids, and permitting it
# "minus those flags" would be a denylist over flags. Open question 3.
READ_ONLY = frozenset({"cat", "grep", "egrep", "fgrep", "head", "tail", "wc", "ls", "rg"})

# `git` is not the unit of trust; these two subcommands are.
READ_ONLY_GIT = frozenset({"diff", "log", "show", "status", "blame"})

# The only shell syntax that may appear alongside a protected path. Anything
# else -- redirection, substitution, subshells -- is refused.
SAFE_SEPARATORS = frozenset({"&&", "||", ";", "|", "\n"})

SUBSTITUTION = ("$(", "`", "${")


def mentions_protected(token: str) -> bool:
    return bool(PROTECTED_RE.search(token))


def tokenize(command: str) -> list[str] | None:
    """Shell-ish tokens, or None when the command cannot be read."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def segments(tokens: list[str]) -> list[list[str]]:
    """Split a token list on the safe separators."""
    out: list[list[str]] = [[]]
    for token in tokens:
        if token in SAFE_SEPARATORS:
            out.append([])
        else:
            out[-1].append(token)
    return [seg for seg in out if seg]


def is_read_only(segment: list[str]) -> bool:
    command = segment[0].rsplit("/", 1)[-1]
    if command == "git":
        return len(segment) > 1 and segment[1] in READ_ONLY_GIT
    return command in READ_ONLY


def _syntax_refusal(command: str, tokens: list[str]) -> str | None:
    """Shell syntax that performs, or hides, a write."""
    if any(marker in command for marker in SUBSTITUTION):
        return "command substitution — the guard cannot establish what runs"
    for token in tokens:
        if token in SAFE_SEPARATORS or not token.strip():
            continue
        # A pure-punctuation token that is not an allowlisted separator is
        # redirection or grouping: the write primitive itself.
        if all(char in "();<>|&" for char in token):
            return f"shell operator {token!r} — redirection and grouping are writes"
    return None


def _command_refusal(tokens: list[str]) -> str | None:
    """A command outside the read-only set."""
    for segment in segments(tokens):
        if not is_read_only(segment):
            return f"{segment[0]!r} is not in the read-only set"
    return None


def evaluate(command: str) -> tuple[int, str]:
    if not command.strip():
        return PERMIT, ""

    tokens = tokenize(command)
    if tokens is None:
        # Cannot parse, so cannot answer. Refusing is the only honest outcome
        # (H-1); the raw string is not consulted, because a guard that falls
        # back to substring matching when its parser fails is guessing.
        return REFUSE, "the command could not be parsed, so it could not be checked"

    if not any(mentions_protected(token) for token in tokens):
        return PERMIT, ""

    refusal = _syntax_refusal(command, tokens) or _command_refusal(tokens)
    return (REFUSE, refusal) if refusal else (PERMIT, "")


def main() -> int:
    command = sys.stdin.read()
    code, reason = evaluate(command)
    if code == PERMIT:
        return PERMIT
    sys.stderr.write(
        "BLOCKED — this command touches src/, patterns/ or scripts/ and "
        f"{reason}.\n\n"
        "Guards hook Write|Edit|MultiEdit, so a write through Bash is invisible "
        "to them (BRIEF_M0.md §1). Use the Write or Edit tool for this change so "
        "the self-application and scope guards can see it.\n"
        "Reading these paths through Bash is unaffected: cat, grep, head, tail, "
        "wc, ls, rg, git diff and git log are permitted.\n"
    )
    return REFUSE


if __name__ == "__main__":
    sys.exit(main())
