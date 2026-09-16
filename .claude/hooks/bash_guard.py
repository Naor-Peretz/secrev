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
#
# `.claude` is here and deliberately NOT in lib/paths.sh. The harness is
# protected against Bash and not against Write/Edit, and the asymmetry is the
# whole answer to the bootstrap objection: a `sed -i` on this file removed the
# control with nothing objecting, while a Write to it passes in front of every
# hook that watches writes. Repair stays possible and stays visible; the
# silent-disable path closes.
#
# Nothing guarded the harness until now, and no component was defective on its
# own -- the guards covered the tool, and the tool's guards were not covered.
# That is composition risk in the sense of FR-0.8, found in the reviewer
# rather than in something reviewed.
# `surfaces` joined in M2 (TASKS_M2.md C-1): the surface kinds are tool input
# exactly as the catalog is, and they decide which entry points enter the
# ledger at all. Protected in the change that created the directory.
PROTECTED = ("src", "patterns", "surfaces", "scripts", r"\.claude")
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

# Interpreters permitted to *run* an existing script under a protected path,
# mapped to the extension they may run. Executing a script is not writing it,
# and the brief's allowlist has two categories where three are needed.
#
# `bash` is absent on purpose: STACK.md §1 is POSIX sh, and the execute
# category is not a place to quietly readmit it. The extension has to match,
# so `sh scripts/thing.py` is refused rather than guessed at. And no token
# after the interpreter may begin with `-`, which is the whole reason this is
# a shape and not a list of names: `python3 -c "open(…,'w')"` and `sh -c 'echo
# x > …'` are writes wearing an interpreter's name.
EXECUTE = {"sh": ".sh", "python3": ".py", "python": ".py"}

# An interpreter and the script it runs. Fewer tokens than this is an
# interactive interpreter, which is not "running an existing script".
INTERPRETER_AND_SCRIPT = 2

# No shell operator may appear beside a protected path. Not `;`, `&&`, `||`,
# `|`, a redirect, a subshell or a substitution.
#
# An earlier design allowed `&& || ; |` as "safe separators" and checked each
# segment on its own. That is sound only while every command is classified by
# what it *is*; the execute category classifies by what it *runs*, and then
# `sh scripts/check.sh; cat > src/secrev/x.py` has an allowlisted first
# command and a chain that carries the write. Segment-checking does catch that
# one — because the second segment holds a redirect — but not
# `sh scripts/check.sh; rm -rf src/`, where nothing after the separator is
# punctuation at all. Banning the operators refuses both without depending on
# which of them happens to look dangerous.
#
# The cost is real and is asserted, not hidden: `cat src/x.py | grep foo` is a
# read-only pipeline and is now refused. Reading a protected file takes one
# command, or the Read tool.
SUBSTITUTION = ("$(", "`", "${")

# shlex's default punctuation set. Any token made only of these is an operator.
OPERATOR_CHARS = "();<>|&"


def mentions_protected(token: str) -> bool:
    return bool(PROTECTED_RE.search(token))


def first_protected(tokens: list[str]) -> str | None:
    """The token that tripped the trigger, for the refusal message.

    Named in the message because the trigger is a test over spellings: a bare
    word equal to a protected name matches as surely as a path does, and two
    such words exist in this project's own vocabulary — the subcommand
    `secrev surfaces` and a branch called `m2/surfaces`. A reader who is told
    which token matched can tell that case from a real write without opening
    this file. Narrowing the rule to require a trailing `/` would end the false
    positives and admit `rm -rf src`, so the message is what improves.
    """
    for token in tokens:
        if PROTECTED_RE.search(token):
            return token
    return None


def tokenize(command: str) -> list[str] | None:
    """Shell-ish tokens, or None when the command cannot be read."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def is_read_only(tokens: list[str]) -> bool:
    command = tokens[0].rsplit("/", 1)[-1]
    if command == "git":
        return len(tokens) > 1 and tokens[1] in READ_ONLY_GIT
    return command in READ_ONLY


def is_execute(tokens: list[str]) -> bool:
    """Running an existing script, as opposed to writing one.

    The script must be the *first* argument, and only that position is checked
    for a leading dash. Everything after it is an argument to the script.

    This was `any(token.startswith("-") for token in tokens[1:])`, which
    refused a flag anywhere — and so refused `sh scripts/check.sh --fast` and
    `--sast`, the two invocations CLAUDE.md documents and the git hooks use.
    A guard that forbids the project's own documented workflow does not make
    the workflow stop; it moves it somewhere the guard cannot see, and every
    other refusal in this file loses credibility with it.

    The security property is unchanged, because it never depended on the
    trailing positions. `python3 -c '…'` and `sh -c '…'` are writes wearing an
    interpreter's name, and both put the flag *before* the script — there is no
    argument in a later position that makes an interpreter evaluate a string.
    Passing `--anything` to an existing script grants no reach the script did
    not already have, and running it at all is what this category permits.
    """
    suffix = EXECUTE.get(tokens[0].rsplit("/", 1)[-1])
    if suffix is None or len(tokens) < INTERPRETER_AND_SCRIPT:
        return False
    if tokens[1].startswith("-"):
        return False
    return tokens[1].endswith(suffix)


def _syntax_refusal(command: str, tokens: list[str]) -> str | None:
    """Shell syntax that performs a write, or carries one past the first
    command."""
    if "\n" in command:
        return "a newline separates commands — this guard answers about one command"
    if any(marker in command for marker in SUBSTITUTION):
        return "command substitution — the guard cannot establish what runs"
    for token in tokens:
        if not token.strip():
            continue
        if all(char in OPERATOR_CHARS for char in token):
            return (
                f"shell operator {token!r} — chaining, grouping and redirection "
                "all carry a write past the command the guard checked"
            )
    return None


def _command_refusal(tokens: list[str]) -> str | None:
    """A command that neither reads nor runs an existing script."""
    if is_read_only(tokens) or is_execute(tokens):
        return None
    return f"{tokens[0]!r} neither reads nor runs an existing script"


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

    # With operators banned above, what remains is a single command.
    refusal = _syntax_refusal(command, tokens) or _command_refusal(tokens)
    return (REFUSE, refusal) if refusal else (PERMIT, "")


def main() -> int:
    command = sys.stdin.read()
    code, reason = evaluate(command)
    if code == PERMIT:
        return PERMIT
    token = first_protected(tokenize(command) or [])
    named = (
        f"`{token}` matches a protected name" if token else "this command touches a protected path"
    )
    sys.stderr.write(
        f"BLOCKED — {named} (src/, patterns/, surfaces/, scripts/, .claude/) and "
        f"{reason}.\n\n"
        "If that token is a command word or a branch name rather than a path, this is a "
        "false positive of a test over spellings: have the user run it, or spell the "
        "path another way.\n\n"
        "Guards hook Write|Edit|MultiEdit, so a write through Bash is invisible "
        "to them (BRIEF_M0.md §1). Use the Write or Edit tool for this change so "
        "the self-application and scope guards can see it.\n"
        "Reading one of these paths is unaffected — cat, grep, head, tail, wc, ls, "
        "rg, git diff, git log — and so is running an existing script: sh <x.sh>, "
        "python3 <x.py>. One command at a time: no `;`, `&&`, `|`, redirect or "
        "substitution beside a protected path, because each of those carries a "
        "write past the command that was checked.\n"
    )
    return REFUSE


if __name__ == "__main__":
    sys.exit(main())
