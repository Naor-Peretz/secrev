"""Did the test suite write to a protected path? Owner decision, 2026-09-22.

    python3 scripts/protected_snapshot.py run -- <command> [args...]

`check.sh` runs pytest through this: snapshot every protected path, run the
command as a child process, snapshot again, compare. Exit 0: the command passed
and nothing protected changed. Exit 1: the command failed, or it passed and
something protected changed — every path is named. Exit 2: the check could not
be made, which is "did not check", never "clean" (STACK.md §8 H-1).

**Why this exists.** Test code is a write path around every guard. `check.sh`
is auto-approved and runs pytest; pytest is code execution; `tests/` is not
protected. A review demonstrated a test file writing into `threat-models/` and
the change reaching the index with nothing in the path noticing — the residual
of M3.5's E3, where `pytest:*` left the allowlist but the gate that runs pytest
did not. Protecting `tests/` or taking the gate off the allowlist would each
have prevented it and each would have put an approval into daily work. This
*detects* it from inside the gate and adds no approval: a legitimate test
writes to `tmp_path`, never to `src/` or `threat-models/`.

**The baseline never touches disk, and that is the fix for the second
review.** The first version was two commands — `take <file>` before pytest,
`compare <file>` after — with the baseline in `$(mktemp)`: a file in /tmp,
owned by the same user, created seconds before the tests ran. A test that wrote
to a protected path could find that file and re-take it, and the gate then
printed "no protected path changed" over a change still sitting in the tree —
H-1 in the control built to close E3, and a false green is worse than a missing
line. Hardening where the file lived would have left the class open, since any
file the parent can read the child can find. So there is no file: the baseline
is taken in this process's memory, the command runs as a child, and the
comparison happens here. The `take` and `compare` modes are gone rather than
kept beside this, because their existence is the thing that was exploited.

A test that rewrites this script is caught too: `scripts/` is a protected root,
and the code doing the comparison was loaded before the child started.

**This closes the vectors that have been found, not the class**, and the
difference is the point rather than a caveat. Four rounds each widened what is
watched, and each time a reviewer found another file that runs code — git alone
offers several configuration-driven mechanisms and new versions add more. What
closes the class is confinement: a test run that cannot write outside a scratch
directory, which is `HARNESS-FS` in `.claude/TASKS_M2.md` and is open. The one
piece of confinement that costs nothing is done here — `HOME` and the global
git config are redirected for the child — and the rest is not claimed.

**What it cannot see**, stated so nobody reads more into a green stage than it
holds: a test that writes and restores a file within the run, and a process a
test detaches that writes after the child returns. The commit checkpoint
(`.claude/hooks/commit-review.sh`) shows protected paths in the index whatever
put them there. The exit code is what gates: a test can print anything to the
shared terminal, including a copy of the success line, but it cannot set this
process's status.

**Which files: everything under the protected roots, plus `.git/`, plus the
files Python and git execute at startup.** Two reviews moved this line, and
each time the previous wording was too confident. It listed files with
`git ls-files --others --exclude-standard`, so anything in `.gitignore` or
`.git/info/exclude` went uncounted — and `.git/info/exclude` is not protected,
and a change to it shows in no `git status`. A third review planted
`.claude/hooks/shutil.py`, hid it there, and the stage printed "no protected
path changed" while every later `git commit` ran that module inside the commit
checkpoint. The answer then said "all of them, ignore rules included", which a
fourth review showed was still false in the direction that mattered:
`git ls-files` lists *worktree* files, so nothing under `.git/` was reachable
by that mechanism at all — and `.git/config` plus `.git/info/attributes` are
where a clean filter and `core.fsmonitor` execute code.

So: a Python walk, no ignore rules anywhere, `.git/` watched whole minus the
churn git makes of its own accord, and no git subprocess in this file at all —
the listing was the one child process a planted `.git/config` could steer.
`__pycache__` is counted and not blindly left out: a `.pyc` whose header
matches a source file's mtime and size is loaded *instead of* the source, which
makes a planted one a vector in its own right.

That would fire on every run, since importing the package writes bytecode —
so the child runs with `PYTHONPYCACHEPREFIX` pointed at a directory outside the
tree, made fresh for the run and removed after. The suite then writes no
`__pycache__` in the tree and reads none from it, so an in-tree `.pyc` that
changes during the run was put there by something other than the interpreter.

**One exclusion, by exact path, with its reason:** `.claude/hooks/state/`.
The hooks write their logs and markers there while a gate may be running — an
edit sets off `async-check.sh` in the background — so counting it would fail
the gate on the harness's own bookkeeping. Nothing in it is imported or
executed. What it *is* is text: the background log is printed into the
session, so a test can forge that advisory report. That is recorded, not
closed, and it is not the gate's own result.

**The interpreter the gate runs is watched, and it was the worst gap of the
five rounds.** `check.sh` and `async-check.sh` ran this checker with
`.venv/bin/python`. `.venv/` is not a protected root, and what was watched
inside it was three name shapes in site-packages — not the interpreter. So one
test overwriting `.venv/bin/python` replaced *the program that reports*: the run
in which it landed finished green, and from the next run on the plant was the
checker, printing the line that says nothing changed. `-I -S` are no answer,
being flags to the interpreter that was replaced, and `pyvenv.cfg` reaches the
same place by naming the base interpreter. Every other vector in this file put
planted code inside a hook; this one put it in place of the control.

Both halves are needed and neither is sufficient. The gate now runs this file
with the system interpreter, which every hook already used and which the suite
has no ordinary way to write — that makes the *comparison* honest. And
`bin/` and `pyvenv.cfg` of both virtual environments are watched, which makes
the plant a finding in the run that lands it rather than a resident that only an
honest checker declines to be.

**`command -v python3` is itself a PATH lookup, which is the same vector one step
out.** A developer PATH begins with directories the user owns — three of them sat
ahead of `/usr/bin` where this was measured — so a test creating
`~/.cargo/bin/python3` would own every later run, and redirecting HOME does
nothing about it, because PATH carries absolute paths. `check.sh` now takes its
interpreter from fixed absolute paths and requires the one it picks to be
unreplaceable by the user whose tests are about to run — not merely unwritable,
since a `python3` symlink in a directory that user owns is repointed with one
command while `[ -w ]` calls it safe — saying so plainly when no such interpreter
exists rather than implying the property. Here, every `python*`
on PATH is watched — and since only existing files are keyed, one *appearing* is
an added entry. That half also covers the hooks, which resolve their interpreter
the same way and which `check.sh` cannot answer for.

**What it still cannot see on that vector:** a PATH directory it cannot list is
skipped, so a plant there is invisible; a plant already in place before the first
snapshot is the baseline rather than a change; and for the hooks this is
detection, not prevention, since their own resolution is unchanged.

**Python's startup files are watched too, outside the tree.** A `.pth` or a
`sitecustomize.py` planted in the venv or the user site directory runs in every
later interpreter started from there. The checker itself runs `-I -S`, so it
cannot be reached that way; the planting is what this catches. What remains
open, recorded: a pytest plugin registered through a planted `*.dist-info`
entry point loads in later pytest runs without being a startup file, and a
plant made *outside* a watched run is not seen by this at all.

**`.claude/settings.local.json` is counted, and that is deliberate.** It is
gitignored, so it was invisible here until ignore rules stopped applying — and
it is where an allow rule that auto-approves everything would be written. The
cost is honest: granting a permission *while* a gate runs makes the gate name
that file. It says which file, so the reason is never a mystery.

Content and the executable bit both, because no guard reads modes and a changed
bit is a change. **A symlink is recorded by its target path, not by what the
target contains** — recording the content was following the link at the one
moment the link is the thing being watched, so repointing it read as unchanged,
and a link to a FIFO hung the gate instead of failing it.

`.git` is resolved rather than assumed to be a directory: in a linked worktree
it is a one-line file naming the real gitdir, and a walk of it returns nothing
at all — watched-whole becomes watched-not-at-all with no change in what the
stage prints.

The roots mirror `STACK.md` §8 H-4. They are a second copy of that list, which
H-7 would object to on its own; `tests/harness/attack.py` pins this tuple equal
to the guard's, so the two cannot drift without the harness gate going red.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# H-4's protected paths. Pinned equal to `bash_guard.PROTECTED` by the harness.
PROTECTED_ROOTS = (
    "src",
    "patterns",
    "surfaces",
    "structure",
    "scripts",
    "threat-models",
    "tests/golden",
    ".claude",
)

# The one exclusion; see the module docstring for why it is safe and what it
# leaves open.
HOOK_STATE = ".claude/hooks/state/"

USAGE = "usage: protected_snapshot.py run -- <command> [args...]"
SHOWN = 10
# `run`, `--`, and at least the command itself.
MINIMUM_ARGUMENTS = 3


class CannotCheck(Exception):
    """The snapshot could not be taken — exit 2, never 0."""


def _digest(path: Path) -> str:
    """What this path *is*, as one string: a symlink's target, or a file's
    bytes and executable bit.

    **The symlink branch is not a refinement — without it the entry is worse
    than useless.** `_walk` records a symlink and never follows it, and the
    first version of this then called `read_bytes()` on that entry, which
    follows it at the one moment it matters: the digest was of the *target's*
    content. A link planted under a watched root and later repointed at a
    different file reads as unchanged, because the digest never described the
    link. A review measured it: the recorded value was the outside target's
    hash. Reading through also hands the checker whatever the target is — a
    FIFO blocks the gate forever, which is the hang M3.5 removed from the tool
    and had left in the harness.
    """
    if path.is_symlink():
        return f"link:{path.readlink()}"
    if not path.is_file():
        # **Not a refinement either.** `_walk` admits only links and regular
        # files, so the first version's symlink branch was enough for
        # everything it collected — and a review then measured the gate
        # *hanging*, with no exit code and no message, on a FIFO named
        # `evil.pth` in the venv and on a FIFO at the watched `~/.gitconfig`.
        # `_git_files` and `_startup_files` do not go through `_walk`: one
        # tests `exists()`, the other globs. Reading a FIFO with no writer
        # blocks forever, which is worse than exit 2 — "never finished" is not
        # even "did not check" (H-1).
        #
        # The branch is here rather than in the two collectors because a third
        # collector would have to remember, and the fix that covers only the
        # collector a review demonstrated is this milestone's whole pattern.
        # A non-regular file has no content to hash and is recorded as what it
        # is: appearing, vanishing or changing kind is a change.
        return "not-regular"
    data = path.read_bytes()
    executable = path.stat().st_mode & 0o111
    return f"{hashlib.sha256(data).hexdigest()}{'+x' if executable else ''}"


def _walk(base: Path, skip: frozenset[str] = frozenset()) -> list[Path]:
    """Every file under `base`, skipping any path component in `skip`.

    Symlinks are recorded as entries and never followed, so a link planted
    under a watched root cannot make this read — or hash — a file outside it.
    """
    found: list[Path] = []
    if not base.is_dir():
        return found
    for entry in sorted(base.rglob("*")):
        if skip.intersection(entry.relative_to(base).parts):
            continue
        if entry.is_symlink() or entry.is_file():
            found.append(entry)
    return found


def _files() -> list[str]:
    """The watched paths under the protected roots, relative to the repository.

    **A Python walk, not `git ls-files`** — and dropping git here is the point
    rather than a tidy-up. The listing was the checker's one child process, and
    a fourth review showed that repo-local git configuration executes code:
    `core.fsmonitor` and a clean filter both ran from `.git/config`. A checker
    that asks git for its file list can be steered by the very files it exists
    to watch. It also could not see them: `git ls-files` lists worktree files,
    so nothing under `.git/` was reachable by that mechanism at all — the
    docstring's "all of them, ignore rules included" was false for the
    directory that matters most.

    The walk is also simpler: no ignore rules to opt out of, no `--cached` half
    that only ever bought a file deleted before the run, and no
    "git is not installed" failure mode.
    """
    names: list[str] = []
    for root in PROTECTED_ROOTS:
        for path in _walk(ROOT / root):
            relative = path.relative_to(ROOT).as_posix()
            if not relative.startswith(HOOK_STATE):
                names.append(relative)
    return sorted(names)


# What Python executes at *every* start, before any script: a `.pth` line that
# begins with `import`, and the two customize modules. Planted in the venv or
# the user site directory, any of them runs in every later interpreter from
# there — the gate's own later stages included — and neither location is a
# protected root. The suite has no reason to write one, so they are watched
# too, by name rather than by walking site-packages, which would hash
# thousands of files to watch three shapes.
_STARTUP = ("*.pth", "sitecustomize.py", "usercustomize.py")

# `.git/` is watched whole, minus the churn git makes of its own accord. A
# fourth review confirmed three executions from files in here: a clean filter
# (`.git/config` plus `.git/info/attributes`) firing on `git add`,
# `core.fsmonitor` firing on `git status`, and a global config reaching other
# repositories. `.git/hooks/` joins them: it only fires on a real commit, after
# the checkpoint, which makes it the weakest of the four and still one to see.
#
# Whole-minus-churn rather than a list of the four, for the reason the same
# review gave: every round of this so far extended a list of names and the
# class stayed open, because git keeps adding configuration that runs code. A
# key added by a future git lands in `.git/config`, which is already watched.
# What is skipped is git's own bookkeeping, which changes constantly and
# executes nothing.
GIT_CHURN = frozenset(
    {
        "objects",
        "refs",
        "logs",
        # `modules` was here, and it was the one entry in this set that does
        # **not** execute nothing: `.git/modules/<name>/` is a submodule's real
        # gitdir, holding its own `config` and `hooks/`. Skipping it dropped a
        # clean filter and a `core.fsmonitor` from the watch while the comment
        # above claimed the set executes nothing. Its churn is skipped anyway,
        # because the names below match on *any* path component — a submodule's
        # `objects`, `refs` and `index` are covered exactly as the superproject's
        # are. This repository has no submodules, which made it cheap to get
        # wrong and cheap to fix.
        "rebase-merge",
        "rebase-apply",
        "sequencer",
        "index",
        "HEAD",
        "ORIG_HEAD",
        "FETCH_HEAD",
        "MERGE_HEAD",
        "MERGE_MSG",
        "AUTO_MERGE",
        "REBASE_HEAD",
        "CHERRY_PICK_HEAD",
        "COMMIT_EDITMSG",
        "packed-refs",
        "shallow",
        # Held for the length of a `git add`, and gone by the time anything
        # reads the snapshot. Counting it makes a concurrent git command the
        # gate's verdict.
        "index.lock",
    }
)


def _git_directories() -> tuple[Path, ...]:
    """Where this checkout's git administrative files actually live.

    `ROOT/.git` is a directory in an ordinary clone and a **file** in a linked
    worktree (`git worktree add`) or a submodule — one line, `gitdir: <path>`.
    `_walk` returns nothing for a path that is not a directory, so the whole
    `.git` half of this checker went silently empty there: zero files watched,
    the stage still printing its success line. A review measured both halves of
    that. It is the shape this file has been corrected for four times — a check
    that cannot run must say so (H-1), and a watch that resolves to nothing is
    a check that did not run.

    A worktree's own gitdir holds `HEAD`, `index` and `config.worktree`; the
    shared `config` and `hooks/` live in the common directory it names. Both
    are watched, because a clean filter planted in either one executes here.
    """
    marker = ROOT / ".git"
    if marker.is_dir():
        return (marker,)
    if not marker.exists():
        # No repository at all — an exported tree. Nothing to watch, and no
        # git-configuration vector to watch it for.
        return ()
    try:
        text = marker.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CannotCheck(f"{marker}: {exc}") from exc
    line = next((row for row in text.splitlines() if row.startswith("gitdir:")), None)
    if line is None:
        raise CannotCheck(f"{marker} is a file but names no gitdir")
    gitdir = Path(line.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = (ROOT / gitdir).resolve()
    if not gitdir.is_dir():
        raise CannotCheck(f"{marker} names {gitdir}, which is not a directory")
    directories = [gitdir]
    common = gitdir / "commondir"
    if common.is_file():
        try:
            shared = Path(common.read_text(encoding="utf-8", errors="replace").strip())
        except OSError as exc:
            raise CannotCheck(f"{common}: {exc}") from exc
        if not shared.is_absolute():
            shared = (gitdir / shared).resolve()
        if not shared.is_dir():
            # The sibling branch four lines up refuses when `gitdir` names a
            # non-directory; this one used to drop it and carry on. The
            # directory it drops is the one holding the shared `config` and
            # `hooks/` — the worktree's own gitdir has `config.worktree` and
            # little else — so continuing means watching the half that cannot
            # execute anything and printing the same success line. That is the
            # defect this function was written to fix, one branch over.
            raise CannotCheck(f"{common} names {shared}, which is not a directory")
        directories.append(shared)
    return tuple(directories)


def _git_files() -> list[Path]:
    """`.git/` minus its churn, and the global git configs.

    The global ones are outside the repository and are the vector a review
    confirmed reaches *other* repositories on the machine: `HOME` is writable
    by the test suite, so `~/.gitconfig` is as plantable as `.git/config`.
    `XDG_CONFIG_HOME` is read ahead of `~/.config` when it is set, so watching
    only the latter watches the wrong file on a machine that sets it.
    """
    found = [path for directory in _git_directories() for path in _walk(directory, GIT_CHURN)]
    home = Path.home()
    candidates = [home / ".gitconfig", home / ".config" / "git" / "config"]
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(Path(xdg) / "git" / "config")
    seen: set[Path] = set()
    for path in candidates:
        # `exists()` follows a link and so answers about the target; a dangling
        # link at `~/.gitconfig` is still a file git will read once something
        # creates its target.
        if (path.exists() or path.is_symlink()) and path not in seen:
            seen.add(path)
            found.append(path)
    return found


# The interpreters and tools the gate *executes*. Not another name on the
# watch list — a different question from the ones above, and the one that was
# missing: those ask "what runs when Python starts", this asks "what does the
# gate run at all".
#
# `.venv/` is not a protected path, and only three name shapes inside
# site-packages were watched, so `.venv/bin/python` was writable by the suite
# and watched by nothing. A test that overwrote it replaced the program the gate
# runs for every later stage — ruff, mypy, pytest and the self-application check
# — and the run in which that landed finished green. `pyvenv.cfg` is the same
# vector one level out: it names the base interpreter.
#
# `bin/` whole rather than `python` alone, for the reason `.git/` is watched
# whole: `pytest`, `ruff` and `mypy` are executables the gate runs too, and a
# list of the three that matter today is a list someone extends after the next
# review. `.venv-audit/` joins it because the licence and audit stages run its
# tools. Both directories are stable during a run — nothing installs mid-gate —
# and hashing 23 MB twice costs a fraction of a second.
_VENVS = (".venv", ".venv-audit")

# The names a lookup for an interpreter can actually resolve: `python`,
# `python3`, `python3.12`. A bare `python*` glob also matched `python-dotenv`
# and four bpfcc tools — nothing a shebang or `command -v python3` will ever
# pick, and tens of megabytes to hash for the privilege. Narrow because the
# claim is narrow: this watches what could *be* the interpreter.
_PYTHON_NAME = re.compile(r"^python(\d+(\.\d+)?)?$")


def _interpreter_files() -> list[Path]:
    found: list[Path] = []
    for venv in _VENVS:
        found.extend(_walk(ROOT / venv / "bin"))
        config = ROOT / venv / "pyvenv.cfg"
        if config.exists() or config.is_symlink():
            found.append(config)

    # **Every `python*` on PATH, and the owner's follow-up finding is why.**
    # `command -v python3` searches PATH in order, and a developer PATH starts
    # with directories the user owns: on the machine where this was measured,
    # three writable ones sit ahead of `/usr/bin`. None holds a `python3`, so
    # the gate resolves root-owned today — and a test creating one changes that
    # for every later run. Redirecting HOME does not help: PATH carries
    # absolute paths.
    #
    # Appearance is what this catches, and it needs no list of plant locations:
    # only existing files are keyed, so a `python3` that was not there before is
    # an *added* entry. That covers the hooks too, which resolve their
    # interpreter the same way — the half of this vector that `check.sh`'s own
    # resolution cannot answer for them.
    #
    # `sys.executable` first, because the program doing the comparison should be
    # in what it compares.
    running = Path(sys.executable)
    for path in (running, running.resolve()):
        if path.exists() and path not in found:
            found.append(path)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        directory = Path(entry)
        try:
            candidates = (
                sorted(path for path in directory.glob("python*") if _PYTHON_NAME.match(path.name))
                if directory.is_dir()
                else []
            )
        except OSError:
            # A PATH directory we cannot list. Recorded in the docstring rather
            # than swallowed silently: a plant there would be invisible to this,
            # and exiting 2 over somebody's unusual PATH would make the gate
            # unrunnable for a case that is not the one being defended against.
            continue
        found.extend(path for path in candidates if path not in found)
    return found


def _startup_files() -> list[Path]:
    import site  # noqa: PLC0415 - imported here because the checker runs with -S

    directories = [*sorted((ROOT / ".venv").glob("lib/python*/site-packages"))]
    user = Path(site.getusersitepackages())
    if user.is_dir():
        directories.append(user)
    found: list[Path] = []
    for directory in directories:
        for pattern in _STARTUP:
            found.extend(sorted(directory.glob(pattern)))
    return found


def snapshot() -> dict[str, str]:
    """Path -> what the path is: a digest of content and executable bit, or a
    symlink's target. A file listed and then found missing is recorded as
    absent rather than skipped, so a deletion mid-run is a change like any
    other. Files outside the tree are keyed by absolute path under a label
    saying why they are watched."""
    state: dict[str, str] = {}
    # Outside the tree, keyed by absolute path. The label is carried from the
    # collector rather than guessed from the path: it used to be "does this
    # start with ROOT/.git", which called `~/.gitconfig` a startup file and
    # would call a linked worktree's gitdir one too.
    #
    # **Absent is a value, not a failure**: `_git_files` lists `~/.gitconfig`
    # only when it exists, so this branch is the file vanishing between
    # listing and reading — a race, not a machine without one. A CannotCheck
    # for the ordinary missing case would be an exit 2 on a clean checkout,
    # and H-1 codes are expensive precisely because they mean something.
    outside_files = [("git", path) for path in _git_files()]
    outside_files += [("startup", path) for path in _startup_files()]
    outside_files += [("interpreter", path) for path in _interpreter_files()]
    for label, outside in outside_files:
        state[f"{label}:{outside}"] = _state_of(outside)
    for name in _files():
        state[name] = _state_of(ROOT / name)
    return state


def _state_of(path: Path) -> str:
    """`_digest`, with the two unreadable cases recorded as values.

    **Unreadable is a value, and that closes a denial of the gate.** A
    `PermissionError` used to raise `CannotCheck`, which is exit 2 — the right
    direction, since refusing beats passing, but it handed any test the power to
    *stop the gate* with one `chmod 000`, and the operator saw a broken harness
    rather than a hostile test. The mode is observable even when the content is
    not, so this is not a check that could not run: a file that becomes
    unreadable during the run has *changed*, and saying so is both true and more
    useful. A file already unreadable when the baseline was taken reads the same
    way in both snapshots and raises nothing, which is what keeps the honest
    case quiet. Recorded as open in `BRIEF_M4.md` §6 and closed here.

    Any other `OSError` still raises: an I/O error or a path that cannot be
    stat'd at all is genuinely "did not check" (H-1).
    """
    try:
        return _digest(path)
    except FileNotFoundError:
        return "absent"
    except PermissionError:
        return "unreadable"
    except OSError as exc:
        raise CannotCheck(f"{path}: {exc}") from exc


def changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    found: list[str] = []
    for name in sorted(set(before) | set(after)):
        if name not in before:
            found.append(f"added     {name}")
        elif name not in after:
            found.append(f"removed   {name}")
        elif before[name] != after[name]:
            if after[name] == "absent":
                kind = "removed"
            elif after[name] == "unreadable":
                # Named for what it is rather than folded into "changed": the
                # remedy is a file mode, and sending a reader to look for edited
                # content would be the same conflation `recon.json` keeps apart
                # between `unreadable` and `too_large`.
                kind = "locked"
            else:
                kind = "changed"
            found.append(f"{kind:<9} {name}")
    return found


def main(argv: list[str]) -> int:
    if len(argv) < MINIMUM_ARGUMENTS or argv[:2] != ["run", "--"]:
        print(USAGE, file=sys.stderr)
        return 2
    command = argv[2:]

    try:
        before = snapshot()
    except CannotCheck as exc:
        print(f"protected_snapshot: cannot check — {exc} (H-1)", file=sys.stderr)
        return 2

    # Bytecode for the run goes outside the tree, so the in-tree __pycache__
    # is neither written nor read by the suite (module docstring).
    with (
        tempfile.TemporaryDirectory(prefix="secrev-pycache-") as cache,
        tempfile.TemporaryDirectory(prefix="secrev-home-") as home,
    ):
        environment = {
            **os.environ,
            "PYTHONPYCACHEPREFIX": cache,
            # **Prevention, not detection, for the one vector where it is
            # free.** A review confirmed that a global `~/.gitconfig` written
            # by a test reaches every other repository on the machine. The
            # suite has no business in the real HOME, so it does not get one:
            # HOME points at a scratch directory, and git is told explicitly
            # which config files exist, since it reads `GIT_CONFIG_GLOBAL`
            # ahead of HOME. Watching these files catches a plant; this stops
            # the plant from landing where anything later reads it.
            #
            # It is *not* confinement: a test can still write to the real
            # HOME by absolute path. Making that impossible needs an OS
            # sandbox and is HARNESS-FS's, which stays open.
            "HOME": home,
            # Read ahead of `~/.config` when it is set, so redirecting HOME
            # alone leaves the real one in play for every tool that honours it.
            "XDG_CONFIG_HOME": str(Path(home) / ".config"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            # **The system config is left alone, and that is a correction.**
            # `GIT_CONFIG_NOSYSTEM=1` was here, turning it off as well. It
            # bought nothing: the vector is a test writing the *global* config,
            # which the line above redirects, and `/etc/gitconfig` is not
            # writable by the user whose tests these are — if it were, the test
            # could do anything regardless. What it cost was real: a
            # system-level `safe.directory`, which is how a container with a
            # checkout owned by another uid makes git usable at all, so every
            # test that shells out to git would fail there for a reason nobody
            # would connect to this line. Recorded as open in `BRIEF_M4.md` §6
            # and closed by removing the thing that was not earning its cost.
        }
        try:
            child = subprocess.run(  # noqa: S603 - argv from check.sh
                command, cwd=ROOT, env=environment, check=False
            )
        except OSError as exc:
            print(
                f"protected_snapshot: could not start {command[0]!r}: {exc} (H-1)",
                file=sys.stderr,
            )
            return 2

    # The header states what the stage *is*, and is printed before the answer
    # is known — it used to read "tests wrote no protected path" here, a
    # conclusion on screen above the check that reaches it. CLAUDE.md puts a
    # printed string first in the reading order for exactly this reason.
    print("\n\033[1m── did the tests write a protected path?\033[0m")
    try:
        after = snapshot()
    except CannotCheck as exc:
        print(f"protected_snapshot: cannot check — {exc} (H-1)", file=sys.stderr)
        return 2

    found = changes(before, after)
    if found:
        print(
            "the test run changed protected paths — a test wrote where no guard looks:",
            file=sys.stderr,
        )
        for line in found[:SHOWN]:
            print(f"  {line}", file=sys.stderr)
        if len(found) > SHOWN:
            print(f"  … and {len(found) - SHOWN} more", file=sys.stderr)
        return 1
    print(f"no protected path changed during the test run ({len(after)} checked)")
    # **The child's own status, not `1`.** This read `0 if returncode == 0 else
    # 1`, which flattened every way a command can fail into "it failed" —
    # pytest's 1 (tests failed) arrived indistinguishable from its 3 (internal
    # error), 4 (usage error) and 5 (nothing collected), and "the suite says no"
    # is not "the suite could not run". That is H-1's distinction, mild here
    # because both are non-zero, and still the one this project exists to keep.
    # Recorded as open in `BRIEF_M4.md` §6 and closed by passing the number
    # through: this wrapper runs an arbitrary command and has no business
    # interpreting another program's exit codes, which is exactly why it must
    # not overwrite them. `check.sh` maps them, where pytest is known to be the
    # command.
    return child.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
