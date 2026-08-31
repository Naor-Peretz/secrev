"""CodeQL over the Python source, for `check.sh --sast`.

STACK.md §2.2. ruff's bandit rules (`S…`) and scripts/self_check.py answer the
presence-and-structure questions this project can afford to ask on every run.
CodeQL answers the dataflow ones — does untrusted input reach this sink — which
neither of the other two can, and which take minutes rather than milliseconds.
Hence opt-in locally and unconditional in CI (.github/workflows/codeql.yml).

The CodeQL CLI is not a dependency of this repository: nothing installs it,
`pyproject.toml` does not mention it, and the gate does not need it. Absent, and
with --sast typed, this exits 2 — a check that was explicitly asked for and
could not run is the H-1 case at its sharpest.

Everything is written to a temporary directory outside the tree. A CodeQL
database inside the repository would be inventoried and swept as though it were
source (G-4, and the same reason `.security-review/` is gitignored).

Exit: 0 no alerts · 1 at least one alert · 2 CodeQL could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CannotRun(Exception):
    """CodeQL did not produce an answer. Distinct from producing an unwelcome one."""


def _codeql(binary: Path, args: list[str]) -> None:
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [str(binary), *args],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0:
        raise CannotRun(
            f"codeql {args[0]} {args[1]} exited {proc.returncode}\n"
            + proc.stderr.decode("utf-8", errors="replace")
        )


def _alerts(sarif: Path) -> list[str]:
    try:
        parsed = json.loads(sarif.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CannotRun(f"the SARIF report could not be read — {exc}") from exc

    found: list[str] = []
    for run in parsed.get("runs", []):
        for result in run.get("results", []):
            rule = result.get("ruleId", "?")
            locations = result.get("locations") or [{}]
            physical = locations[0].get("physicalLocation", {})
            uri = physical.get("artifactLocation", {}).get("uri", "?")
            line = physical.get("region", {}).get("startLine", "?")
            message = result.get("message", {}).get("text", "").split("\n")[0]
            found.append(f"{uri}:{line}  {rule}\n      {message}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codeql", required=True, type=Path, help="path to the CodeQL CLI")
    args = parser.parse_args()

    if not args.codeql.is_file():
        sys.stderr.write(f"CodeQL CLI not found at {args.codeql} — cannot check.\n")
        return 2

    with tempfile.TemporaryDirectory(prefix="secrev-codeql-") as tmp:
        database = Path(tmp) / "db"
        sarif = Path(tmp) / "results.sarif"
        try:
            print("  building the database (this is the slow part)", flush=True)
            _codeql(
                args.codeql,
                [
                    "database",
                    "create",
                    str(database),
                    "--language=python",
                    f"--source-root={ROOT}",
                    "--overwrite",
                ],
            )
            print("  analysing", flush=True)
            _codeql(
                args.codeql,
                [
                    "database",
                    "analyze",
                    str(database),
                    "--format=sarifv2.1.0",
                    f"--output={sarif}",
                ],
            )
            alerts = _alerts(sarif)
        except CannotRun as exc:
            sys.stderr.write(f"{exc}\n")
            sys.stderr.write(
                "\nThis is 'could not run', not 'no alerts'. The usual cause is a missing\n"
                "query pack: `codeql pack download codeql/python-queries`. If that command\n"
                "itself fails on an unrecognised manifest field, the CLI predates the\n"
                "registry format and the fix is a newer CodeQL CLI — 2.24.2 fails this way.\n"
            )
            return 2

    if alerts:
        sys.stderr.write(f"CodeQL: {len(alerts)} alert(s)\n")
        for alert in sorted(alerts):
            sys.stderr.write(f"  {alert}\n")
        return 1

    print("no alerts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
