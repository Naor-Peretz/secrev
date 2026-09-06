"""`notes/` never becomes history. CONTRIBUTING.md, "Never record a target's
specifics in this repository".

The working notes hold findings about third-party projects, at least one of
them unfixed. `.gitignore` keeps them out of commits, and that is the whole
protection — which is thin for what it is guarding. `git add -f` bypasses it
without complaint, and so does anyone editing the ignore rule for an unrelated
reason and not thinking about this one.

Publishing an unfixed finding is not a mistake with a tidy fix. Once it is in a
pushed commit it is disclosed, to the maintainer and to everyone else at once,
and rewriting history afterwards removes the text without unpublishing it. That
asymmetry is why this is a test and not a convention: the cost of the check is
a millisecond, and the cost of the failure is somebody else's exposure.

Two assertions, because either alone can be defeated without the other
noticing: that nothing under `notes/` is tracked, and that the ignore rule is
still there. The second is the one that catches the change *before* it lets a
file through.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Resolved, not looked up on PATH. `pyproject.toml` records why the harness
# takes the same care: an absolute binary cannot be shadowed by whatever
# happens to be earlier in PATH when the gate runs.
GIT = shutil.which("git")


def tracked(pathspec: str) -> list[str]:
    if GIT is None:  # pragma: no cover - git is present wherever this runs
        pytest.skip("git is not installed")
    proc = subprocess.run(  # noqa: S603 - absolute binary, fixed argv, no shell
        [GIT, "ls-files", "--", pathspec],
        capture_output=True,
        cwd=ROOT,
        check=True,
        text=True,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def test_notes_are_not_tracked() -> None:
    """`git add -f notes/x.md` is one keystroke from a disclosure."""
    committed = tracked("notes")
    assert not committed, f"working notes have been committed: {committed}"


def test_the_ignore_rule_is_still_there() -> None:
    """The rule above only holds while this line does. Removing it does not
    commit anything by itself, which is exactly why it would pass review."""
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "notes/" in [line.strip() for line in rules], (
        "the notes/ ignore rule is gone; it is the only thing keeping findings "
        "about third-party projects out of this repository's history"
    )
