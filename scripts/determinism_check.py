"""NFR-3 enforced rather than trusted.

Two checks, both from BRIEF_M1.md §7 and, since TASK-M2-009, over every block
of the ledger (BRIEF_M2.md §4, BRIEF_M4.md C3):

  1. Two runs over the same fixture tree produce byte-identical recon.json
     and hits.jsonl — the pattern, surface and structural blocks alike. A ledger
     missing any block fails: a block that was never produced was never
     compared, and saying "identical" about it would be H-1.
  2. Adding an unrelated file to the tree renumbers no existing candidate id,
     whichever source produced it.

The required blocks are derived from `cli.SOURCES` rather than listed here.
They were listed until M4, so the structural block would have been absent from
this check while the summary line said "both blocks" — a check that is complete
by construction only until someone adds a third of something.

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

# Read from the tool rather than restated (H-7). A fourth source has to appear
# here for the check to cover it, and the one place to add it is `cli.py`.
sys.path.insert(0, str(ROOT / "src"))
from secrev.cli import COMMANDS, SOURCES  # noqa: E402


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


def _records(blob: bytes) -> list[dict[str, str]]:
    """Ledger records, split on newline alone — never `splitlines`, which
    also breaks on U+0085, U+2028 and U+2029 that the ledger writes unescaped
    inside a record (the TASK-M2-007 review)."""
    text = blob.decode("utf-8", errors="replace")
    return [json.loads(line) for line in text.split("\n") if line.strip()]


def _ids(blob: bytes) -> set[str]:
    return {record["id"] for record in _records(blob)}


def check_byte_identical(tmp: Path) -> bool:
    runs = []
    for index in (1, 2):
        workspace = tmp / f"run{index}"
        for subcommand in COMMANDS:
            if not _run(subcommand, FIXTURES, workspace):
                return False
        runs.append(_collect(workspace))

    if not runs[0]:
        sys.stderr.write("  no recon.json or hits.jsonl produced — nothing compared\n")
        return False

    missing = set(SOURCES) - {
        record["source"] for record in _records(runs[0].get("hits.jsonl", b""))
    }
    if missing:
        sys.stderr.write(
            f"  hits.jsonl has no {' or '.join(sorted(missing))} records — that block "
            "was never compared (H-1)\n"
        )
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


def check_inventory_is_stable() -> bool:
    """The inventory-level check, which needs no CLI.

    This is the one that must run from the moment inventory.py exists. The
    artifact checks below compare recon.json and hits.jsonl, which do not
    exist until recon.py and sweep.py do — and waiting for them would mean
    traversal order and NFC normalisation went unchecked for exactly as long
    as they were being written.
    """
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from secrev import inventory  # noqa: PLC0415 - the module may not exist yet
    except ImportError as exc:
        sys.stderr.write(f"  inventory.py exists but does not import: {exc}\n")
        return False

    first = inventory.walk(FIXTURES)
    second = inventory.walk(FIXTURES)
    if first != second:
        sys.stderr.write("  two walks of the same tree disagree (STACK.md §5)\n")
        return False

    paths = [entry.path for entry in first]
    if paths != sorted(paths):
        sys.stderr.write(
            "  inventory is not sorted on the POSIX path string — emitted in\n"
            "  traversal order, which differs between filesystems (STACK.md §5)\n"
        )
        return False
    return True


def check_stable_ids(tmp: Path) -> bool:
    """A file appearing elsewhere in the tree must not renumber anything."""
    tree = tmp / "tree"
    shutil.copytree(FIXTURES, tree, symlinks=True)

    # Every ledger-producing command, derived rather than listed: `recon`
    # writes no block, so it is the one COMMANDS entry this check skips.
    producing = tuple(name for name in COMMANDS if name != "recon")

    before_ws = tmp / "before"
    for subcommand in producing:
        if not _run(subcommand, tree, before_ws):
            return False
    before = _collect(before_ws).get("hits.jsonl")
    if before is None:
        return True

    (tree / "zz_unrelated_addition.txt").write_text("nothing to match here\n", encoding="utf-8")
    after_ws = tmp / "after"
    for subcommand in producing:
        if not _run(subcommand, tree, after_ws):
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
    # The trigger is inventory.py, not the src/secrev directory.
    #
    # "no src/secrev yet — nothing to compare" is a sentence that stays true
    # long after it should stop being printed: the directory appears with the
    # first file, and if that file is cli.py the message keeps skipping while
    # traversal, normalisation and id derivation are being written. Those are
    # the rules NFR-3 is made of, they live in inventory.py, and they are the
    # ones that cannot be corrected afterwards — a determinism check written
    # after recon.py and sweep.py is a retrofit onto code composed without it.
    #
    # Same shape as .claude/MILESTONE reading M1 through the whole of M0: a
    # condition that was accurate when written and is not re-examined. Bound
    # to the exact file so it cannot outlive its own truth.
    inventory = ROOT / "src" / "secrev" / "inventory.py"
    if not inventory.exists():
        print("no src/secrev/inventory.py yet — the file that owns the NFR-3 rules")
        return 0
    if not FIXTURES.is_dir():
        sys.stderr.write(
            "inventory.py exists and tests/fixtures/ does not — cannot check (H-1).\n"
            "The fixture tree is how NFR-3 stops being aspirational (STACK.md §9).\n"
        )
        return 2

    if not check_inventory_is_stable():
        return 1
    print("inventory: two walks byte-identical, sorted on the POSIX path")

    # The artifact comparison needs the CLI. Its absence is a real "nothing to
    # check yet" and is named as such — but it is named, and it names the two
    # files it is waiting for, so it cannot quietly outlive its own truth the
    # way the src/secrev condition did.
    pending = [
        name
        for name in ("recon.py", "sweep.py", "surfaces.py", "structure.py")
        if not (ROOT / "src" / "secrev" / name).exists()
    ]
    if pending:
        print(f"artifacts: not yet — waiting on {', '.join(pending)}")
        return 0

    with tempfile.TemporaryDirectory(prefix="secrev-determinism-") as raw:
        tmp = Path(raw)
        if not (check_byte_identical(tmp) and check_stable_ids(tmp)):
            return 1
    blocks = ", ".join(SOURCES)
    print(f"artifacts: recon.json and every hits.jsonl block ({blocks}) byte-identical, ids stable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
