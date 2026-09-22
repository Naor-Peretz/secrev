"""Did the test suite write to a protected path? Owner decision, 2026-09-22.

    python3 scripts/protected_snapshot.py take    <file>
    python3 scripts/protected_snapshot.py compare <file>

`check.sh` takes a snapshot before pytest and compares after. Exit 0: nothing
protected changed. Exit 1: something did, and every path is named. Exit 2: the
snapshot could not be taken or read, which is "did not check", not "clean"
(STACK.md §8 H-1).

**Why this exists.** Test code is a write path around every guard. `check.sh`
is auto-approved and runs pytest; pytest is code execution; `tests/` is not
protected. A review demonstrated a test file writing into `threat-models/` and
the change reaching the index with nothing in the path noticing — the
residual of M3.5's E3, where `pytest:*` left the allowlist but the gate that
runs pytest did not. Protecting `tests/` or taking the gate off the allowlist
would both have prevented it and both would have put an approval into daily
work. This *detects* it, from inside the gate, and adds no approval: a
legitimate test writes to `tmp_path`, never to `src/` or `threat-models/`, so
in ordinary use the check never fires.

**What it cannot see**, stated so nobody reads more into a green stage: a test
that writes and then restores the file before pytest ends, and a process a test
detaches that writes after pytest returns. The commit checkpoint
(`.claude/hooks/commit-review.sh`) is the layer for those — it shows protected
paths in the index whatever put them there. Neither layer alone covers what the
two cover together, and neither adds an approval to ordinary work.

**Which files.** Everything git would consider under the protected roots —
tracked, plus untracked-but-not-ignored — so a new `src/secrev/evil.py` counts
and `__pycache__/` does not. Content and the executable bit both, because no
guard reads modes and a changed bit is a change.

The roots mirror `STACK.md` §8 H-4. They are a second copy of that list, which
H-7 would object to on its own; `tests/harness/attack.py` pins this tuple equal
to the guard's, so the two cannot drift without the harness gate going red.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
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

USAGE = "usage: protected_snapshot.py take|compare <file>"
ARGUMENTS = 2
SHOWN = 10


class CannotCheck(Exception):
    """The snapshot could not be taken or read — exit 2, never 0."""


def _files() -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise CannotCheck("no git on PATH")
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            git,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *PROTECTED_ROOTS,
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CannotCheck(proc.stderr.decode("utf-8", errors="replace").strip())
    return sorted({name for name in proc.stdout.decode("utf-8").split("\0") if name})


def snapshot() -> dict[str, str]:
    """Path -> digest of content and executable bit. A tracked file that no
    longer exists is recorded as absent rather than skipped, so a deletion is a
    change like any other."""
    state: dict[str, str] = {}
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
    if len(argv) != ARGUMENTS or argv[0] not in {"take", "compare"}:
        print(USAGE, file=sys.stderr)
        return 2
    mode, target = argv[0], Path(argv[1])
    try:
        current = snapshot()
        if mode == "take":
            target.write_text(json.dumps(current, sort_keys=True), encoding="utf-8")
            return 0
        try:
            before = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CannotCheck(f"snapshot unreadable: {exc}") from exc
    except CannotCheck as exc:
        print(f"protected_snapshot: cannot check — {exc} (H-1)", file=sys.stderr)
        return 2

    found = changes(before, current)
    if not found:
        print(f"no protected path changed during the test run ({len(current)} checked)")
        return 0
    print(
        "the test run changed protected paths — a test wrote where no guard looks:",
        file=sys.stderr,
    )
    for line in found[:SHOWN]:
        print(f"  {line}", file=sys.stderr)
    if len(found) > SHOWN:
        print(f"  … and {len(found) - SHOWN} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
