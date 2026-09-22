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
question 8 in .claude/TASKS_M0.md (item 5 of its "Raised" list). Fixing it means making the trigger "the
command is read-only" rather than "the command mentions a protected path",
which refuses `uv sync`, `pytest` and `git commit` and needs its own allowlist.
That is a decision for a human, not something to settle inside this file.

Since M4 one command already works the inverted way: `_staging_refusal`
decides on what a `git add` *is*, wherever it sits and whether or not a
protected path is named. It is the prototype that question now has, and the
single-character evasions it records (`s?c/…`, `sr[c]/…`) are the reason it
stays open.

That prototype has its own KNOWN LIMIT, found in review and recorded rather
than claimed closed: it identifies the subcommand by the token after `git`,
and git itself resolves names this file cannot see. `git ad -f .env` runs `add`
when `help.autocorrect` is set; `git a -f .env` runs it through a configured
alias; and `git -c alias.a=add a -f .env` defines the alias inline, where the
`add` sits inside another token and the option-before-subcommand check, which
looks for `add` exactly, passes it. None is auto-approved — `Bash(git add:*)`
matches none of them — so each reaches an approval dialog, and the commit
checkpoint shows what was staged whatever did the staging. Closing it here
would mean predicting git's own name resolution from shell text.
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
# `tests/golden` joined in M3 and is the only two-segment entry, deliberately.
# The question-id pin lives there as data rather than in Python, because AC-4
# requires a new archetype to cost no script change — and a pin editable without
# review is protection one step away from what it protects. Two segments because
# a bare `golden` would protect any directory of that name anywhere, and the
# over-match this file already carries for one-word names is not worth widening
# when the real path is known.
# `structure` joined in M4 on exactly the argument `surfaces` joined on, and in
# the change that created the directory rather than after it. The structural
# rules are tool input like the catalog and the kinds: the parameters in
# `_structure.yaml` decide which calls count as sinks and which functions count
# as validating, so an unreviewed edit there is a structural check that silently
# stops firing while every run still reports success. The owner placed the file
# in a directory of its own (BRIEF_M4.md §6 Q1) rather than under patterns/,
# which is what makes a separate entry here necessary at all.
PROTECTED = (
    "src",
    "patterns",
    "surfaces",
    "structure",
    "scripts",
    "threat-models",
    "tests/golden",
    r"\.claude",
)

# The set as a reader sees it, derived rather than restated. The refusal message
# below used to spell the list out and had already drifted — it omitted
# `threat-models/` from the moment that directory was protected, so the guard
# refused a path its own explanation said was not covered. H-7's argument, in
# the smallest possible form: one definition, and the prose reads from it.
PROTECTED_DISPLAY = ", ".join(name.replace("\\", "") + "/" for name in PROTECTED)
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

# Staging, admitted by owner decision on 2026-09-22 — its own category, not an
# entry in READ_ONLY_GIT, because it is not read-only and a list whose name is
# false is how a later reader widens it by analogy.
#
# **What `git add` stages is whatever the session wrote — which the Write/Edit
# guards saw only if it arrived through Write or Edit.** The first version of
# this comment said the guards had "already seen" staged content, and a review
# disproved it with a test file that wrote into `threat-models/` under the
# auto-approved gate: `pytest` is code execution, `tests/` is not protected, and
# nothing on that path touched a guard. The owner's hand on staging had been the
# one control that would have noticed a protected file changed without a Write.
# It moved to commit — `commit-review.sh` puts the staged set, protected paths
# flagged, in front of the owner at the approval that is still asked every time.
# That hook is the replacement for the checkpoint this category removed, not an
# optional improvement to it.
#
# `git add` writes the index and never the working tree, which is the true part
# of the original claim and the reason staging needs no guard of its own on
# *content*. Every operator remains banned beside a protected path, so `git add
# src/x.py; rm -rf src` is still refused — the category is one command, not a
# chain that begins with one.
#
# Only `add` in the second position. `git -C <dir> add` is refused, because an
# option before the subcommand is how a git invocation stops meaning what its
# second token says.
STAGE_GIT = frozenset({"add"})

# The flags staging may carry — an allowlist, for the reason `find` is absent
# above: admitting `git add` "minus the dangerous flags" would be a denylist over
# flags. Everything the ordinary flow needs, and nothing else. The review named
# three that were admitted and should not be: `-f` stages a gitignored file,
# which is how `.env` and `notes/` leave the machine; `--chmod` changes a mode
# no guard reads; `--pathspec-from-file` stages paths that never appear in the
# command, so no test over the command's text can see what it touched.
#
# **Checked on every `git add`, protected path named or not**, and that is the
# half that makes the list mean anything. Two of the review's three examples —
# `git add -f .env` and `--pathspec-from-file=list` — name no protected path, so
# `evaluate` permitted them at its first line and never reached `is_stage`.
# Narrowing only the protected-path branch would have fixed the demonstrated
# case and left the class open.
STAGE_FLAGS = frozenset({"-A", "--all", "-u", "--update"})

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

# `git` and its subcommand. Fewer tokens than this is a bare `git`.
COMMAND_AND_SUBCOMMAND = 2

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


def is_stage(tokens: list[str]) -> bool:
    """`git add`, and nothing that merely begins with `git`."""
    command = tokens[0].rsplit("/", 1)[-1]
    return command == "git" and len(tokens) > 1 and tokens[1] in STAGE_GIT


def segments(tokens: list[str]) -> list[list[str]]:
    """The commands in a line, split on operator tokens. Used to find a
    `git add` wherever it sits — `true && git add -f .env` names no protected
    path, so the operator ban never sees it — and by `commit_review.py` to find
    a `git commit` the same way, so the two cannot disagree about where a
    command begins."""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and all(char in OPERATOR_CHARS for char in token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def git_argv(segment: list[str]) -> list[str] | None:
    """`git` and what follows it, wherever `git` sits in the command, or None.

    Shared with `commit_review.py` so the staging check and the commit
    checkpoint cannot disagree about which command is a git command — the first
    version of each read only the first word, and a wrapper walked past both.
    """
    for index, token in enumerate(segment):
        if token.rsplit("/", 1)[-1] == "git":
            argv = segment[index:]
            return argv if len(argv) >= COMMAND_AND_SUBCOMMAND else None
    return None


def _staging_refusal(tokens: list[str]) -> str | None:
    """A `git add` anywhere in the line that carries a flag outside
    `STAGE_FLAGS`, or that hides `add` behind an option.

    `git` is found wherever it sits in a command, not only in first position.
    The first version checked `segment[0]`, so `env git add -f .env`,
    `VAR=1 git add -f .env` and `sudo git add -f .env` all walked past it.
    Listing the wrappers — `env`, `sudo`, `nice`, `nohup`, `command`, `time` —
    would be a denylist over prefixes, which is the polarity this file refuses;
    locating `git` itself needs no list. What still defeats it is the KNOWN
    LIMIT above: a `git` spelled through a variable is not a token anyone can
    read.
    """
    for segment in segments(tokens):
        argv = git_argv(segment)
        if argv is None:
            continue
        if argv[1].startswith("-") and "add" in argv:
            return "an option before `git add` — the second token must be the subcommand"
        if argv[1] not in STAGE_GIT:
            continue
        for argument in argv[2:]:
            if argument == "--":
                break
            if argument.startswith("-") and argument not in STAGE_FLAGS:
                allowed = ", ".join(sorted(STAGE_FLAGS))
                return f"`git add {argument}` — staging may carry only {allowed}"
    return None


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
    """A command that neither reads, stages, nor runs an existing script."""
    if is_read_only(tokens) or is_stage(tokens) or is_execute(tokens):
        return None
    return f"{tokens[0]!r} neither reads, stages, nor runs an existing script"


def evaluate(command: str) -> tuple[int, str]:
    if not command.strip():
        return PERMIT, ""

    tokens = tokenize(command)
    if tokens is None:
        # Cannot parse, so cannot answer. Refusing is the only honest outcome
        # (H-1); the raw string is not consulted, because a guard that falls
        # back to substring matching when its parser fails is guessing.
        return REFUSE, "the command could not be parsed, so it could not be checked"

    # Before the protected-path test, not after it: see STAGE_FLAGS.
    staging = _staging_refusal(tokens)
    if staging:
        return REFUSE, staging

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
        f"BLOCKED — {named} ({PROTECTED_DISPLAY}) and {reason}.\n\n"
        "If that token is a command word or a branch name rather than a path, this is a "
        "false positive of a test over spellings: have the user run it, or spell the "
        "path another way.\n\n"
        "Guards hook Write|Edit|MultiEdit, so a write through Bash is invisible "
        "to them (BRIEF_M0.md §1). Use the Write or Edit tool for this change so "
        "the self-application and scope guards can see it.\n"
        "Reading one of these paths is unaffected — cat, grep, head, tail, wc, ls, "
        "rg, git diff, git log — and so is staging it with git add, and running an "
        "existing script: sh <x.sh>, python3 <x.py>. One command at a time: no `;`, "
        "`&&`, `|`, redirect or "
        "substitution beside a protected path, because each of those carries a "
        "write past the command that was checked.\n"
    )
    return REFUSE


if __name__ == "__main__":
    sys.exit(main())
