"""`scripts/codeql_check.py --sarif`, the verdict CI applies to CodeQL's report.

CI analyses with the CodeQL action and does not upload, because code scanning
on a private repository is a paid feature. The job's exit status is therefore
the only verdict there is, and it comes from this mode. Running CodeQL itself
takes minutes and a CLI nothing here installs, so the `--codeql` mode is not
exercised here; what is exercised is the rule both modes share.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "codeql_check.py"


def judge(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def sarif(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "python.sarif"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_a_clean_report_passes(tmp_path: Path) -> None:
    proc = judge("--sarif", str(sarif(tmp_path, {"runs": [{"results": []}]})))
    assert proc.returncode == 0, proc.stderr
    assert "no alerts" in proc.stdout


def test_an_alert_fails_and_is_named(tmp_path: Path) -> None:
    result = {
        "ruleId": "py/example",
        "message": {"text": "something reaches a sink"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "src/secrev/cli.py"},
                    "region": {"startLine": 7},
                }
            }
        ],
    }
    proc = judge("--sarif", str(sarif(tmp_path, {"runs": [{"results": [result]}]})))
    assert proc.returncode == 1
    assert "src/secrev/cli.py:7  py/example" in proc.stderr


def test_a_missing_report_is_could_not_run(tmp_path: Path) -> None:
    """The analyze step wrote somewhere else, or not at all. That is not clean."""
    proc = judge("--sarif", str(tmp_path / "absent.sarif"))
    assert proc.returncode == 2
    assert "could not run" in proc.stderr


def test_a_report_with_no_runs_is_could_not_run(tmp_path: Path) -> None:
    """Before this mode existed, `{}` read as "no alerts": the loop over runs
    simply had nothing to iterate. A report in which nothing was analysed is
    the H-1 case, not a pass."""
    for document in ({}, {"runs": []}, []):
        proc = judge("--sarif", str(sarif(tmp_path, document)))
        assert proc.returncode == 2, f"{document!r} was read as a verdict"


def test_both_modes_at_once_is_a_usage_error(tmp_path: Path) -> None:
    report = sarif(tmp_path, {"runs": [{"results": []}]})
    proc = judge("--sarif", str(report), "--codeql", "/nonexistent/codeql")
    assert proc.returncode == 2
