"""The gate's check that the test suite wrote no protected path.

Every case runs in a throwaway git repository with the script copied into it:
the script resolves its root from its own location, and a test proving that a
write to `threat-models/` is caught must not write to the real one. That would
be the defect under test, committed by the test for it.

The "suite" in each case is a child command — `python -c` doing one thing — run
the way `check.sh` runs pytest: `protected_snapshot.py run -- <command>`.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "protected_snapshot.py"


def _checker_rooted_at(root: Path) -> Any:
    """The checker loaded as a module, with its `ROOT` pointed at `root`.

    Most cases here run it as a child process in a throwaway repository, which
    is how the gate runs it. These two are about how it resolves `.git` before
    any file is read, so they call the functions directly — a child process
    would report the same exit code for "watched nothing" and "watched
    everything and found no change", which is the defect, not the test."""
    spec = importlib.util.spec_from_file_location(f"protected_snapshot_{id(root)}", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    return module


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


def test_a_planted_pyc_is_a_change(repo: Path) -> None:
    """Inverted by the third review. This test asserted the opposite — that a
    `.pyc` written into `__pycache__/` was ordinary and not a change — which was
    the finding written down as a control. A `.pyc` whose header matches a
    source's mtime and size is loaded instead of the source, so a planted one is
    a vector, not noise."""
    code = (
        "import os\n"
        "os.makedirs('src/__pycache__')\n"
        "open('src/__pycache__/x.cpython-311.pyc', 'wb').write(b'\\0')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "added     src/__pycache__/x.cpython-311.pyc" in result.stderr


def test_bytecode_from_an_ordinary_import_is_not_written_into_the_tree(repo: Path) -> None:
    """The control that keeps the rule above from firing on every run. The
    child runs with `PYTHONPYCACHEPREFIX` outside the tree, so importing a
    protected module writes its bytecode there and not into `__pycache__/`."""
    result = suite(repo, "import sys; sys.path.insert(0, 'src'); import x")
    assert result.returncode == 0, result.stderr
    assert not (repo / "src" / "__pycache__").exists()


def test_a_gitignored_plant_is_a_change(repo: Path) -> None:
    """The third review's attack: plant a module beside a hook and hide it with
    an ignore rule. `.git/info/exclude` is not protected and a change to it is
    in no `git status`, so the listing may not honour ignore rules at all."""
    code = (
        "import os\n"
        "os.makedirs('.claude/hooks', exist_ok=True)\n"
        "open('.claude/hooks/shutil.py', 'w').write('import os\\n')\n"
        "open('.git/info/exclude', 'a').write('.claude/hooks/shutil.py\\n')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "added     .claude/hooks/shutil.py" in result.stderr


def test_a_permission_written_into_the_local_settings_is_a_change(repo: Path) -> None:
    """Gitignored, and where an allow rule that auto-approves everything would
    go — so invisible to the listing until ignore rules stopped applying."""
    code = (
        "import os\n"
        "os.makedirs('.claude', exist_ok=True)\n"
        "open('.claude/settings.local.json', 'w').write('{\"permissions\": {}}')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "added     .claude/settings.local.json" in result.stderr


def test_a_startup_file_planted_in_the_venv_is_a_change(repo: Path) -> None:
    """A `.pth` in site-packages runs in every later interpreter from that
    venv — the gate's later stages included — and `.venv` is not a protected
    root, so the listing alone would never see it."""
    site_packages = repo / ".venv" / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True)
    code = f"open({str(site_packages / 'evil.pth')!r}, 'w').write('import os\\n')\n"
    result = suite(repo, code)
    assert result.returncode == 1
    assert "evil.pth" in result.stderr


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        (".git/config", "[core]\n\tfsmonitor = touch /tmp/x\n"),
        (".git/info/attributes", "*.py filter=x\n"),
        (".git/hooks/pre-commit", "#!/bin/sh\ntouch /tmp/x\n"),
    ],
)
def test_git_configuration_that_runs_code_is_watched(
    repo: Path, relative: str, content: str
) -> None:
    """The fourth review's vectors. `git ls-files` lists worktree files, so the
    old listing could not see anything under `.git/` at all — these were not
    merely unwatched, they were unreachable by that mechanism."""
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    code = f"open({str(path)!r}, 'w').write({content!r})\n"
    result = suite(repo, code)
    assert result.returncode == 1
    assert relative.rsplit("/", 1)[-1] in result.stderr


def test_repointing_a_symlink_under_a_protected_root_is_a_change(repo: Path) -> None:
    """A symlink is recorded by its *target path*, not by the target's content.

    The first version hashed `read_bytes()`, which follows the link — so the
    digest described a file outside the watched tree rather than the link. The
    link here already exists when the baseline is taken, which makes this a
    test of the digest rather than of the walk: the entry is in both snapshots
    and only its meaning differs.

    **The two targets hold identical content, and that is the whole test.** The
    first draft gave them different content and passed against the unfixed
    code, because hashing the target still saw *that* difference — it proved
    nothing about which of the two things was being recorded. Equal content is
    the case that separates them: the link now points somewhere else and no
    byte anywhere has changed.
    """
    decoy = repo / "outside"
    decoy.mkdir()
    (decoy / "one.py").write_text("same = 1\n", encoding="utf-8")
    (decoy / "two.py").write_text("same = 1\n", encoding="utf-8")
    (repo / "src" / "link.py").symlink_to(decoy / "one.py")

    code = (
        "import os\n"
        "os.unlink('src/link.py')\n"
        f"os.symlink({str(decoy / 'two.py')!r}, 'src/link.py')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "changed   src/link.py" in result.stderr


def test_a_symlink_to_a_fifo_does_not_hang_the_gate(repo: Path) -> None:
    """The same defect's other half, and the one with no error message: reading
    *through* the link opens whatever it points at, and opening a FIFO with no
    writer blocks forever — no exception, no timeout, the gate simply never
    returns. M3.5 removed this from the tool (`inventory.py`, C1) and it was
    still here. The timeout is the assertion; there is nothing else to see.
    """
    os.mkfifo(repo / "pipe")
    (repo / "src" / "link.py").symlink_to(repo / "pipe")
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(repo / "scripts" / "protected_snapshot.py"), "run", "--", "true"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_overwriting_the_interpreter_the_gate_runs_is_a_change(repo: Path) -> None:
    """The fifth review's worst finding, and the only one that replaced the
    control rather than running inside a hook.

    The gate ran this checker with `.venv/bin/python`. `.venv/` is not a
    protected root and only three name shapes in site-packages were watched, so
    one test overwriting that file made the plant *the checker* from the next
    run on — including the line reporting that nothing changed. Two things
    answer it, and this asserts the second: the gate runs the checker with the
    system interpreter (`attack.py` holds that), and the interpreter is watched,
    so the overwrite is a finding in the run that does it.
    """
    venv_bin = repo / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/sh\nexec /usr/bin/true\n", encoding="utf-8")
    (repo / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")

    code = (
        "open('.venv/bin/python', 'w').write('#!/bin/sh\\nexec /bin/echo planted\\n')\n"
        "open('.venv/pyvenv.cfg', 'w').write('home = /tmp/planted\\n')\n"
    )
    result = suite(repo, code)
    assert result.returncode == 1
    assert "python" in result.stderr
    assert "pyvenv.cfg" in result.stderr


def test_a_python_planted_earlier_on_path_is_a_change(repo: Path) -> None:
    """The same vector one step out, and the owner's follow-up finding.

    `command -v python3` searches PATH in order, and a developer PATH begins
    with directories the user owns — three sat ahead of `/usr/bin` on the
    machine where this was measured. A test creating `python3` in one of them
    owns every later run, and redirecting HOME does not help because PATH holds
    absolute paths.

    No list of plant locations is needed: only existing files are keyed, so a
    `python3` that was not there before is an *added* entry. The planted
    directory is on PATH when the baseline is taken and empty of interpreters,
    which is the real shape — the attacker does not get to add a PATH entry,
    only to write into one that is already there.
    """
    bin_dir = repo / "writable-bin"
    bin_dir.mkdir()
    environment = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    code = f"open({str(bin_dir / 'python3')!r}, 'w').write('#!/bin/sh\\nexec /bin/echo plant\\n')\n"
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(repo / "scripts" / "protected_snapshot.py"),
            "run",
            "--",
            sys.executable,
            "-c",
            code,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "python3" in result.stderr


def test_a_fifo_outside_the_walk_does_not_hang_the_gate(repo: Path) -> None:
    """The same hang, by the route the walk does not control.

    `_walk` admits only links and regular files, so the symlink test above
    passes on a fix that covers nothing else. `_startup_files` globs `*.pth`
    in site-packages and `_git_files` tests `~/.gitconfig` with `exists()` —
    neither asks whether the entry is a regular file, and a review measured
    the gate hanging on a FIFO at either. That is worse than the `chmod 000`
    case recorded as open: no exit code at all.

    A test can reach site-packages, which `test_a_startup_file_planted_in_the
    _venv_is_a_change` already demonstrates. The timeout is the assertion.
    """
    site_packages = repo / ".venv" / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True)
    code = f"import os\nos.mkfifo({str(site_packages / 'evil.pth')!r})\n"
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(repo / "scripts" / "protected_snapshot.py"),
            "run",
            "--",
            sys.executable,
            "-c",
            code,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    # And it is a *change*, not merely survivable: a named pipe appearing
    # where Python reads startup files is exactly what this watches for.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "evil.pth" in result.stderr


def test_a_linked_worktree_does_not_silently_watch_nothing(tmp_path: Path) -> None:
    """In a linked worktree `.git` is a one-line *file* naming the real gitdir,
    and walking a non-directory returns nothing — so the entire `.git` half of
    this checker watched zero files while the stage printed its success line. A
    false green, which is worse than a missing check (H-1).

    This asserts on the checker's own view rather than through a child run,
    because what failed was the resolution, and the resolution is what a
    reviewer needs named.
    """
    git = shutil.which("git")
    assert git
    identity = ["-c", "user.name=t", "-c", "user.email=t@t.invalid"]
    main = tmp_path / "main"
    main.mkdir()
    (main / "a.txt").write_text("x\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"], [*identity, "commit", "-qm", "base"]):
        subprocess.run(  # noqa: S603 - absolute binary, fixed argv, no shell
            [git, *args], cwd=main, check=True, capture_output=True
        )
    linked = tmp_path / "linked"
    subprocess.run(  # noqa: S603 - absolute binary, fixed argv, no shell
        [git, "worktree", "add", "-q", str(linked)], cwd=main, check=True, capture_output=True
    )
    assert (linked / ".git").is_file(), "a linked worktree's .git is a file, not a directory"

    module = _checker_rooted_at(linked)
    # **On the resolution, and on paths inside this tree only.** `_git_files`
    # also returns the machine's global configs, so `assert watched` passes
    # with the resolution mutated away on any machine that has a
    # `~/.gitconfig` — and `any(name == "config")` passes on any machine using
    # the XDG location, where the global config is itself named `config`. Both
    # were true of the first version of this test: the regression test for
    # this round's headline fix was green without the fix. Twice in one round
    # is a pattern, and the pattern is asserting on whatever the function
    # happened to return.
    assert module._git_directories(), "the .git file resolved to no directory"
    inside = [path for path in module._git_files() if path.is_relative_to(tmp_path)]
    assert inside, "the .git watch resolved to nothing in a linked worktree"
    # The shared configuration — where a clean filter is planted — lives in the
    # common directory, not in the worktree's own gitdir.
    assert any(path.name == "config" for path in inside)


def test_a_dot_git_file_naming_nothing_refuses(tmp_path: Path) -> None:
    """H-1 for the resolution itself: unreadable state is a refusal, never an
    empty watch that reads as clean."""
    (tmp_path / ".git").write_text("this names no gitdir\n", encoding="utf-8")
    module = _checker_rooted_at(tmp_path)
    with pytest.raises(module.CannotCheck):
        module._git_files()


def test_gits_own_bookkeeping_is_not_a_change(repo: Path) -> None:
    """The control for the rule above. `.git/` is watched whole *minus* the
    churn git makes of its own accord; without this the gate would fail on
    every run that touches the index."""
    code = "open('.git/index', 'ab').write(b'\\0')\nopen('.git/COMMIT_EDITMSG', 'w').write('x')\n"
    result = suite(repo, code)
    assert result.returncode == 0, result.stderr


def test_the_suite_cannot_reach_the_real_home_or_global_git_config(repo: Path) -> None:
    """Prevention rather than detection, for the one vector where it is free.

    A global `~/.gitconfig` written by a test reaches every other repository on
    the machine — confirmed in review. The child runs with HOME in a scratch
    directory and with `GIT_CONFIG_GLOBAL` pointed at the null device, so a
    test that writes "the global config" writes nowhere that anything later
    reads. This asserts on the *real* paths: they must be untouched.
    """
    real_home = Path.home()
    config = real_home / ".gitconfig"
    before = config.read_bytes() if config.exists() else None

    code = (
        "import os, pathlib, subprocess\n"
        "home = pathlib.Path(os.environ['HOME'])\n"
        f"assert home != pathlib.Path({str(real_home)!r}), 'HOME was not redirected'\n"
        "assert os.environ['GIT_CONFIG_GLOBAL'] == os.devnull\n"
        "(home / '.gitconfig').write_text('[core]\\n\\tfsmonitor = touch /tmp/x\\n')\n"
        "subprocess.run(['git', 'config', '--global', 'core.pager', 'touch /tmp/x'])\n"
    )
    result = suite(repo, code)

    assert result.returncode == 0, result.stderr
    after = config.read_bytes() if config.exists() else None
    assert after == before, "the suite reached the real global git config"


def test_hook_state_is_the_one_exclusion(repo: Path) -> None:
    """The hooks write logs there while a gate may be running, so counting it
    would fail the gate on the harness's own bookkeeping. Nothing in it is
    imported or executed; the module docstring records what it leaves open."""
    code = (
        "import os\n"
        "os.makedirs('.claude/hooks/state', exist_ok=True)\n"
        "open('.claude/hooks/state/async-check.log', 'w').write('ok\\n')\n"
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


def test_the_childs_own_status_reaches_the_caller(repo: Path) -> None:
    """A suite saying no and a suite that could not run are different facts.

    This returned `1` for every non-zero child, so pytest's 3 (internal error),
    4 (usage error) and 5 (nothing collected) all arrived as "tests failed".
    The number passes through now, and `check.sh` maps it — a wrapper that runs
    an arbitrary command has no business reinterpreting another program's exit
    codes, which is exactly why it must not overwrite them.
    """
    for status in (1, 3, 4, 5):
        result = suite(repo, f"raise SystemExit({status})")
        assert result.returncode == status, (
            f"child exited {status}, wrapper said {result.returncode}"
        )


def test_a_test_that_locks_a_watched_file_cannot_stop_the_gate(repo: Path) -> None:
    """Denial of the gate, closed. `chmod 000` on a watched file raised
    `CannotCheck` — exit 2, the right direction and still a way for any test to
    stop the gate running, leaving the operator looking at a broken harness
    rather than at a hostile test.

    The mode is observable when the content is not, so this is not a check that
    could not run: the file *changed*, and it is reported as `locked` rather
    than folded into `changed`, because the remedy is a file mode and not an
    edit.
    """
    result = suite(repo, "import os\nos.chmod('src/x.py', 0o000)\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "locked    src/x.py" in result.stderr


def test_a_file_already_unreadable_is_not_a_change(repo: Path) -> None:
    """The control for the rule above, and the reason it is safe: a file nobody
    can read reads the same way in both snapshots. Without this, locking a file
    before the run would fail every later gate."""
    locked = repo / "src" / "locked.py"
    locked.write_text("x = 1\n", encoding="utf-8")
    locked.chmod(0o000)
    result = suite(repo, "pass")
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_command_that_cannot_start_is_exit_two(repo: Path) -> None:
    """H-1: "the tests never ran" must not print as a clean run."""
    result = guarded(repo, "run", "--", str(repo / "no-such-binary"))
    assert result.returncode == 2


def test_a_bad_invocation_is_exit_two(repo: Path) -> None:
    assert guarded(repo, "run").returncode == 2
    assert guarded(repo, "look").returncode == 2
