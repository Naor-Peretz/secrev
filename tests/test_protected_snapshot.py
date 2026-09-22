"""The gate's check that the test suite wrote no protected path.

Every case runs in a throwaway git repository with the script copied into it:
the script resolves its root from its own location, and a test proving that a
write to `threat-models/` is caught must not write to the real one. That would
be the defect under test, committed by the test for it.

The "suite" in each case is a child command — `python -c` doing one thing — run
the way `check.sh` runs pytest: `protected_snapshot.py run -- <command>`.
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
        subprocess.run(  # noqa: S603 - absolute binary, fixed argv, no shell
            [git, *args], cwd=tmp_path, check=True, capture_output=True
        )
    return tmp_path


def guarded(repo: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(repo / "scripts" / "protected_snapshot.py"), *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def suite(repo: Path, code: str) -> subprocess.CompletedProcess[str]:
    """Run `code` as the child, the way check.sh runs pytest."""
    return guarded(repo, "run", "--", sys.executable, "-c", code)


def test_the_first_reviews_demonstration_is_caught(repo: Path) -> None:
    """A test writing into `threat-models/` under the auto-approved gate reached
    the index with no guard in the path."""
    result = suite(repo, "open('threat-models/core.md', 'a').write('planted\\n')")
    assert result.returncode == 1
    assert "changed   threat-models/core.md" in result.stderr


def test_the_second_reviews_attack_has_no_baseline_to_rewrite(repo: Path) -> None:
    """The second review's finding, replayed. The baseline lived in a `mktemp`
    file, so a test that wrote to a protected path could re-take it and the gate
    printed "no protected path changed" over the change. Now the child writes,
    then tries every way the script ever offered to record a baseline — and
    none exists, because the baseline is in the parent's memory and was taken
    before the child started."""
    code = (
        "import subprocess, sys\n"
        "open('threat-models/core.md', 'a').write('planted\\n')\n"
        "for mode in ('take', 'compare'):\n"
        "    subprocess.run([sys.executable, 'scripts/protected_snapshot.py', mode, 'x'])\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "changed   threat-models/core.md" in result.stderr


def test_the_old_modes_no_longer_exist(repo: Path) -> None:
    """Their existence was the thing exploited, so they are gone rather than
    kept beside `run`."""
    assert guarded(repo, "take", "x").returncode == 2
    assert guarded(repo, "compare", "x").returncode == 2


def test_a_test_that_rewrites_the_checker_is_caught(repo: Path) -> None:
    """`scripts/` is a protected root, and the comparison is already loaded."""
    result = suite(repo, "open('scripts/protected_snapshot.py', 'a').write('# gone\\n')")
    assert result.returncode == 1
    assert "changed   scripts/protected_snapshot.py" in result.stderr


def test_a_new_file_under_a_protected_root_is_caught(repo: Path) -> None:
    result = suite(repo, "open('src/evil.py', 'w').write('x = 2\\n')")
    assert result.returncode == 1 and "added     src/evil.py" in result.stderr


def test_a_deleted_file_is_caught(repo: Path) -> None:
    result = suite(repo, "import os; os.remove('src/x.py')")
    assert result.returncode == 1 and "removed   src/x.py" in result.stderr


def test_an_executable_bit_alone_is_a_change(repo: Path) -> None:
    """No guard reads modes, so a bit set by a test is exactly the change that
    would otherwise pass unseen."""
    result = suite(repo, "import os; os.chmod('src/x.py', 0o755)")
    assert result.returncode == 1 and "changed   src/x.py" in result.stderr


def test_bytecode_and_ignored_files_are_not_changes(repo: Path) -> None:
    """The control that keeps this from firing on every run: importing the
    package writes `__pycache__/`, which is ordinary and gitignored."""
    code = (
        "import os\n"
        "os.makedirs('src/__pycache__')\n"
        "open('src/__pycache__/x.cpython-311.pyc', 'wb').write(b'\\0')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 0, result.stderr


def test_a_clean_passing_suite_is_exit_zero_and_says_what_it_checked(repo: Path) -> None:
    result = suite(repo, "pass")
    assert result.returncode == 0
    assert "checked" in result.stdout


def test_a_failing_suite_is_exit_one_even_with_nothing_changed(repo: Path) -> None:
    """The child's own status still gates: this replaces `run "pytest"` in
    check.sh, and a failing test must not become a pass because it wrote
    nothing protected."""
    result = suite(repo, "raise SystemExit(1)")
    assert result.returncode == 1


def test_a_command_that_cannot_start_is_exit_two(repo: Path) -> None:
    """H-1: "the tests never ran" must not print as a clean run."""
    result = guarded(repo, "run", "--", str(repo / "no-such-binary"))
    assert result.returncode == 2


def test_a_bad_invocation_is_exit_two(repo: Path) -> None:
    assert guarded(repo, "run").returncode == 2
    assert guarded(repo, "look").returncode == 2
