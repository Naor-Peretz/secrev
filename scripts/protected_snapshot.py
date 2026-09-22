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

**What it cannot see**, stated so nobody reads more into a green stage than it
holds: a test that writes and restores a file within the run, and a process a
test detaches that writes after the child returns. The commit checkpoint
(`.claude/hooks/commit-review.sh`) shows protected paths in the index whatever
put them there. The exit code is what gates: a test can print anything to the
shared terminal, including a copy of the success line, but it cannot set this
process's status.

**Which files: all of them, ignore rules included.** This listed files with
`git ls-files --others --exclude-standard`, so anything in `.gitignore` or
`.git/info/exclude` was never counted — and `.git/info/exclude` is not
protected, and a change to it shows in no `git status`. A third review planted
`.claude/hooks/shutil.py`, excluded it there, and the stage printed "no
protected path changed" while every later `git commit` ran that module inside
the commit checkpoint. So there is no exclusion by ignore rule. `__pycache__`
is counted too, and not blindly left out: a `.pyc` whose header matches a
source file's mtime and size is loaded *instead of* the source, which makes a
planted one a vector in its own right.

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
bit is a change.

The roots mirror `STACK.md` §8 H-4. They are a second copy of that list, which
H-7 would object to on its own; `tests/harness/attack.py` pins this tuple equal
to the guard's, so the two cannot drift without the harness gate going red.
"""

from __future__ import annotations

import hashlib
import os
import shutil
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


def _files() -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise CannotCheck("no git on PATH")
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        # No `--exclude-standard`: see the module docstring. `--others` alone
        # lists every untracked file, ignored ones included.
        [git, "ls-files", "-z", "--cached", "--others", "--", *PROTECTED_ROOTS],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CannotCheck(proc.stderr.decode("utf-8", errors="replace").strip())
    names = {name for name in proc.stdout.decode("utf-8").split("\0") if name}
    return sorted(name for name in names if not name.startswith(HOOK_STATE))


# What Python executes at *every* start, before any script: a `.pth` line that
# begins with `import`, and the two customize modules. Planted in the venv or
# the user site directory, any of them runs in every later interpreter from
# there — the gate's own later stages included — and neither location is a
# protected root. The suite has no reason to write one, so they are watched
# too, by name rather than by walking site-packages, which would hash
# thousands of files to watch three shapes.
_STARTUP = ("*.pth", "sitecustomize.py", "usercustomize.py")


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
    """Path -> digest of content and executable bit. A tracked file that no
    longer exists is recorded as absent rather than skipped, so a deletion is a
    change like any other. Startup files are keyed by absolute path, since
    they live outside the tree."""
    state: dict[str, str] = {}
    for startup in _startup_files():
        try:
            state[f"startup:{startup}"] = hashlib.sha256(startup.read_bytes()).hexdigest()
        except OSError as exc:
            raise CannotCheck(f"{startup}: {exc}") from exc
    for name in _files():
        path = ROOT / name
        try:
            data = path.read_bytes()
            executable = path.stat().st_mode & 0o111
        except FileNotFoundError:
            state[name] = "absent"
            continue
        except OSError as exc:
            raise CannotCheck(f"{name}: {exc}") from exc
        digest = hashlib.sha256(data).hexdigest()
        state[name] = f"{digest}{'+x' if executable else ''}"
    return state


def changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    found: list[str] = []
    for name in sorted(set(before) | set(after)):
        if name not in before:
            found.append(f"added     {name}")
        elif name not in after:
            found.append(f"removed   {name}")
        elif before[name] != after[name]:
            kind = "removed" if after[name] == "absent" else "changed"
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
    with tempfile.TemporaryDirectory(prefix="secrev-pycache-") as cache:
        environment = {**os.environ, "PYTHONPYCACHEPREFIX": cache}
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

    print("\n\033[1m── tests wrote no protected path\033[0m")
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
    return 0 if child.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
