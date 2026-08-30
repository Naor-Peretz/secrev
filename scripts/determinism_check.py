"""NFR-3 enforced rather than trusted.

Two checks, both from BRIEF_M1.md §7:

  1. Two runs over the same fixture tree produce byte-identical recon.json
     and hits.jsonl.
  2. Adding an unrelated file to the tree renumbers no existing candidate id.

Both write to a throwaway workspace outside the tree (STACK.md §6, G-4) and
never touch the fixtures. Exits 0 when there is nothing to check yet, so it is
safe to wire into the gate before M1 lands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
ARTIFACTS = ("recon.json", "hits.jsonl")


def _python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def _run(subcommand: str, target: Path, workspace: Path) -> bool:
    """Invoke the CLI as a module. Argument list only — never a shell string."""
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [_python(), "-m", "secrev", subcommand, str(target), "--workspace", str(workspace)],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"  `secrev {subcommand}` exited {proc.returncode}\n")
        sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        return False
    return True


def _collect(workspace: Path) -> dict[str, bytes]:
    found = {}
    for name in ARTIFACTS:
        for path in workspace.rglob(name):
            found[name] = path.read_bytes()
            break
    return found


def _ids(blob: bytes) -> set[str]:
    ids = set()
    for line in blob.decode("utf-8", errors="replace").splitlines():
        if line.strip():
            ids.add(json.loads(line)["id"])
    return ids


def check_byte_identical(tmp: Path) -> bool:
    runs = []
    for index in (1, 2):
        workspace = tmp / f"run{index}"
        for subcommand in ("recon", "sweep"):
            if not _run(subcommand, FIXTURES, workspace):
                return False
        runs.append(_collect(workspace))

    if not runs[0]:
        sys.stderr.write("  no recon.json or hits.jsonl produced — nothing compared\n")
        return False

    ok = True
    for name in ARTIFACTS:
        first, second = runs[0].get(name), runs[1].get(name)
        if first is None:
            continue
        if first != second:
            sys.stderr.write(f"  {name} differs between two runs of the same input (NFR-3)\n")
            ok = False
    return ok


def check_stable_ids(tmp: Path) -> bool:
    """A file appearing elsewhere in the tree must not renumber anything."""
    tree = tmp / "tree"
    shutil.copytree(FIXTURES, tree, symlinks=True)

    before_ws = tmp / "before"
    if not _run("sweep", tree, before_ws):
        return False
    before = _collect(before_ws).get("hits.jsonl")
    if before is None:
        return True

    (tree / "zz_unrelated_addition.txt").write_text("nothing to match here\n", encoding="utf-8")
    after_ws = tmp / "after"
    if not _run("sweep", tree, after_ws):
        return False
    after = _collect(after_ws).get("hits.jsonl", b"")

    lost = _ids(before) - _ids(after)
    if lost:
        sys.stderr.write(
            f"  {len(lost)} candidate id(s) changed when an unrelated file was added "
            f"(STACK.md §5): {sorted(lost)[:5]}\n"
        )
        return False
    return True


def main() -> int:
    if not FIXTURES.is_dir() or not (ROOT / "src" / "secrev").is_dir():
        print("no src/secrev + tests/fixtures yet — nothing to compare")
        return 0

    with tempfile.TemporaryDirectory(prefix="secrev-determinism-") as raw:
        tmp = Path(raw)
        return 0 if check_byte_identical(tmp) and check_stable_ids(tmp) else 1


if __name__ == "__main__":
    sys.exit(main())
