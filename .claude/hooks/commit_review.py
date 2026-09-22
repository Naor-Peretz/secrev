"""What a commit is about to record, put in front of the owner at approval.

The replacement for the checkpoint removed on 2026-09-22 — not an improvement
beside it. Until then the owner staged every protected path by hand, and that
was the one place a protected file changed *without* a Write or Edit would have
been noticed: a review showed a test file writing into `threat-models/` under
the auto-approved gate, reaching the index with no guard in the path. Staging
moved to the session; the owner's attention moved to commit. But the commit
approval showed only `git commit -m "…"`, which says nothing about what is in
the index — so the checkpoint had moved to a place that could not see.

This makes it see. On any `git commit` it prints the staged set, marks every
protected path and every mode change, and lists tracked files that are modified
but not staged (they enter the commit under `-a` or a pathspec, which this does
not try to predict). The answer goes out as an `ask`, through `hook_ask.py`, so
the owner approves the commit with the list in front of them.

Silent — no output — when the command contains no `git commit`. Exit 2 when the
index cannot be read (H-9): a checkpoint that cannot show what it gates must
refuse rather than wave the commit through with an empty list.

The same KNOWN LIMIT as `bash_guard.py`: this reads shell text, so a commit
spelled through a variable or a script is not recognised. It is the owner's
view of an ordinary commit, not a control against a determined one.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bash_guard import mentions_protected, segments, tokenize

GIT_AND_SUBCOMMAND = 2


def is_commit(command: str) -> bool:
    tokens = tokenize(command)
    if tokens is None:
        # Unparseable: say so by treating it as a commit, so the owner sees the
        # index rather than nothing. Asking is the conservative direction.
        return True
    for segment in segments(tokens):
        if segment[0].rsplit("/", 1)[-1] != "git" or len(segment) < GIT_AND_SUBCOMMAND:
            continue
        if segment[1] == "commit" or (segment[1].startswith("-") and "commit" in segment):
            return True
    return False


def _git(git: str, root: Path, *args: str) -> str:
    """One `git diff` call, argument list only. Raises on failure so the caller
    can refuse — an unreadable index is not an empty one."""
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [git, "diff", *args],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git diff {' '.join(args)} failed")
    return proc.stdout


def _entries(raw: str) -> list[tuple[str, str]]:
    """`--name-status -z` as (status, path). A rename or copy carries two
    paths; the destination is the one being recorded, and both are shown."""
    fields = [field for field in raw.split("\0") if field]
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(fields):
        status = fields[index]
        if status[:1] in {"R", "C"} and index + 2 < len(fields):
            entries.append((status[:1], f"{fields[index + 1]} -> {fields[index + 2]}"))
            index += 3
        else:
            entries.append((status[:1], fields[index + 1] if index + 1 < len(fields) else ""))
            index += 2
    return entries


def _line(status: str, path: str) -> str:
    marker = "   <- PROTECTED" if mentions_protected(path) else ""
    return f"  {status}  {path}{marker}"


def review(root: Path) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("no git on PATH")

    staged = _entries(_git(git, root, "--cached", "--name-status", "-z"))
    # A changed mode on an existing file, and a new file created executable.
    # The first draft looked only for "mode change", and its own test showed
    # that a new file staged with the executable bit reports as
    # `create mode 100755` instead — just as invisible to every guard, which
    # read content and never modes.
    modes = [
        line.strip()
        for line in _git(git, root, "--cached", "--summary").splitlines()
        if "mode change" in line or ("create mode" in line and "100755" in line)
    ]
    unstaged = _entries(_git(git, root, "--name-status", "-z"))

    lines = [
        "Commit checkpoint. Staging no longer needs your hand (owner decision,",
        "2026-09-22), so this is where you see what the commit records.",
        "",
    ]
    if staged:
        lines.append(f"Staged — recorded by this commit ({len(staged)}):")
        lines.extend(_line(status, path) for status, path in staged)
    else:
        lines.append("Nothing is staged.")

    protected = [path for _, path in staged if mentions_protected(path)]
    if protected:
        lines += ["", f"{len(protected)} protected path(s) staged: {', '.join(protected)}"]
    if modes:
        lines += ["", "Executable bits staged (no guard reads modes):"]
        lines.extend(f"  {mode}" for mode in modes)
    if unstaged:
        lines += ["", "Modified but not staged — recorded only with -a or a pathspec:"]
        lines.extend(_line(status, path) for status, path in unstaged)
    return "\n".join(lines) + "\n"


def main() -> int:
    command = sys.stdin.read()
    if not is_commit(command):
        return 0
    root = Path.cwd()
    try:
        sys.stdout.write(review(root))
    except (OSError, RuntimeError) as exc:
        sys.stderr.write(
            f"commit-review: cannot read the index ({exc}) — refusing rather than "
            "approving a commit whose contents cannot be shown (H-9).\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
