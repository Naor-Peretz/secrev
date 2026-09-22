"""The gate's check that the test suite wrote no protected path.

Every case runs in a throwaway git repository with the script copied into it:
the script resolves its root from its own location, and a test proving that a
write to `threat-models/` is caught must not write to the real one. That would
be the defect under test, committed by the test for it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "protected_snapshot.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git = shutil.which("git")
    assert git, "git is required for these tests"
    (tmp_path / "scripts").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "scripts" / "protected_snapshot.py")
    (tmp_path / "threat-models").mkdir()
    (tmp_path / "threat-models" / "core.md").write_text("q\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    identity = ["-c", "user.name=t", "-c", "user.email=t@t.invalid"]
    for args in (["init", "-q"], ["add", "-A"], [*identity, "commit", "-qm", "base"]):
        subprocess.run([git, *args], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603 - absolute binary, fixed argv, no shell
    return tmp_path


def snapshot(repo: Path, mode: str, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(repo / "scripts" / "protected_snapshot.py"), mode, str(target)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_reviewers_demonstration_is_caught(repo: Path, tmp_path: Path) -> None:
    """A test file writing into `threat-models/` under the auto-approved gate
    reached the index with no guard in the path. Now the gate fails first."""
    state = tmp_path / "state.json"
    assert snapshot(repo, "take", state).returncode == 0
    (repo / "threat-models" / "core.md").write_text("q\nplanted\n", encoding="utf-8")
    result = snapshot(repo, "compare", state)
    assert result.returncode == 1
    assert "changed   threat-models/core.md" in result.stderr


def test_a_new_file_under_a_protected_root_is_caught(repo: Path, tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    snapshot(repo, "take", state)
    (repo / "src" / "evil.py").write_text("x = 2\n", encoding="utf-8")
    result = snapshot(repo, "compare", state)
    assert result.returncode == 1 and "added     src/evil.py" in result.stderr


def test_a_deleted_file_is_caught(repo: Path, tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    snapshot(repo, "take", state)
    (repo / "src" / "x.py").unlink()
    result = snapshot(repo, "compare", state)
    assert result.returncode == 1 and "removed   src/x.py" in result.stderr


def test_an_executable_bit_alone_is_a_change(repo: Path, tmp_path: Path) -> None:
    """No guard reads modes, so a bit set by a test is exactly the change that
    would otherwise pass unseen."""
    state = tmp_path / "state.json"
    snapshot(repo, "take", state)
    (repo / "src" / "x.py").chmod(0o755)
    result = snapshot(repo, "compare", state)
    assert result.returncode == 1 and "changed   src/x.py" in result.stderr


def test_bytecode_and_ignored_files_are_not_changes(repo: Path, tmp_path: Path) -> None:
    """The control that keeps this from firing on every run: importing the
    package writes `__pycache__/`, which is ordinary and gitignored."""
    state = tmp_path / "state.json"
    snapshot(repo, "take", state)
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\0")
    result = snapshot(repo, "compare", state)
    assert result.returncode == 0, result.stderr


def test_no_change_is_exit_zero_and_says_what_it_checked(repo: Path, tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    snapshot(repo, "take", state)
    result = snapshot(repo, "compare", state)
    assert result.returncode == 0
    assert "checked" in result.stdout


def test_an_unreadable_snapshot_is_exit_two_not_clean(repo: Path, tmp_path: Path) -> None:
    """H-1: "could not compare" must not print as "nothing changed"."""
    result = snapshot(repo, "compare", tmp_path / "missing.json")
    assert result.returncode == 2


def test_a_bad_invocation_is_exit_two(repo: Path) -> None:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(repo / "scripts" / "protected_snapshot.py"), "look"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
