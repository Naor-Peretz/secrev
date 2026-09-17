"""`scripts/self_check.py`, the stage that enforces STACK.md §2.1.

**This file did not exist until M3.5, and that is the finding.** The script has
been in the gate since M0, referenced by `check.sh`, `attack.py` and the CodeQL
config, and nothing ever tested it. A check nobody has tried to defeat is an
assumption rather than a control (H-8), and this one is the project's own gate.

P3 says a denylist is a finding until proven otherwise, and `self_check.py` is
a denylist three times over: banned call names, banned `(head, attr)` pairs,
and banned import module strings. Each list is exact, so each is bypassed by
spelling the same thing differently. The founding finding of this project was a
denylist bypass.

Run as a subprocess rather than imported, following `test_codeql_check.py`: the
Definition of done asks for a fixture "asserted to exit 1", and an exit code is
what a subprocess gives.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "self_check.py"


def check(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(SCRIPT), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def write(tmp_path: Path, body: str) -> Path:
    (tmp_path / "sample.py").write_text(body, encoding="utf-8")
    return tmp_path


# Each entry is a spelling of something STACK.md §2.1 forbids, written the way
# it actually gets written rather than the way the denylist expects. Every one
# of these passed the M3.5 checker cleanly.
BYPASSES: list[tuple[str, str]] = [
    # The head is the alias, so ("yaml", "load") never matches.
    ("aliased-yaml", "import yaml as y\n\ndef f(t):\n    return y.load(t)\n"),
    # Module "yaml" is not a banned *import*, and the call is a bare Name.
    ("from-import-yaml", "from yaml import load\n\ndef f(t):\n    return load(t)\n"),
    # Same route, and os.system is not in any list to begin with.
    ("from-import-os-system", "from os import system\n\ndef f(c):\n    return system(c)\n"),
    ("os-system", "import os\n\ndef f(c):\n    return os.system(c)\n"),
    # A Name call the banned-call list does not name.
    ("dunder-import", 'def f():\n    return __import__("socket")\n'),
    (
        "importlib",
        'import importlib\n\ndef f():\n    return importlib.import_module("socket")\n',
    ),
    # The head is "sp", so the subprocess branch never runs.
    (
        "aliased-subprocess",
        "import subprocess as sp\n\ndef f(c):\n    return sp.run(c, shell=True)\n",
    ),
    # args[0] is a JoinedStr, and the check tests for ast.Constant.
    (
        "fstring-argv",
        'import subprocess\n\ndef f(x):\n    return subprocess.run(f"rm {x}")\n',
    ),
    # The module key is "urllib", not "urllib.request".
    ("from-import-urllib", "from urllib import request\n\ndef f():\n    return request\n"),
]


@pytest.mark.parametrize(("name", "body"), BYPASSES, ids=[name for name, _ in BYPASSES])
def test_a_known_bypass_is_caught(name: str, body: str, tmp_path: Path) -> None:
    """E1. Every one of these exited 0 against the pre-M3.5 checker.

    That is the assertion the Definition of done asks to be recorded: the
    fixture is not hypothetical, it is nine spellings that were measured
    passing a gate whose entire purpose is to refuse them.
    """
    result = check(write(tmp_path, body))
    assert result.returncode == 1, f"{name} was not caught:\n{result.stdout}{result.stderr}"


def test_the_whole_fixture_exits_one(tmp_path: Path) -> None:
    """All nine in one file, which is the Definition of done's literal wording."""
    result = check(write(tmp_path, "".join(body for _, body in BYPASSES)))
    assert result.returncode == 1


def test_clean_source_still_passes(tmp_path: Path) -> None:
    """The control. A checker that refuses everything is not a checker, and
    with a denylist widening into a prefix test it is genuinely possible to
    start flagging `yaml.safe_load` or `subprocess.run([...])`."""
    body = (
        "import subprocess\n"
        "import yaml\n"
        "\n"
        "def build_argv(name):\n"
        "    return ['ls', name]\n"
        "\n"
        "def f(path, argv):\n"
        "    data = yaml.safe_load(path.read_text(encoding='utf-8'))\n"
        "    subprocess.run(['ls', '-l'], check=False)\n"
        "    subprocess.run(build_argv('x'), check=False)\n"
        "    return subprocess.run(argv, check=False), data\n"
    )
    result = check(write(tmp_path, body))
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"


def test_the_originally_covered_spellings_are_still_caught(tmp_path: Path) -> None:
    """Widening the checker must not lose what it already had. These are the
    forms the pre-M3.5 denylist did catch."""
    for body in (
        "def f(x):\n    return eval(x)\n",
        "import pickle\n\ndef f(b):\n    return pickle.loads(b)\n",
        "import yaml\n\ndef f(t):\n    return yaml.load(t)\n",
        'import subprocess\n\ndef f():\n    return subprocess.run("ls", shell=True)\n',
    ):
        result = check(write(tmp_path, body))
        assert result.returncode == 1, f"regressed on:\n{body}"
