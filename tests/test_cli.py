"""The CLI contracts. STACK.md §3, BRIEF_M1.md §7.

Two things are asserted here that nothing else can assert: the exit-code split,
and that stdout carries the artifact and nothing else. Both exist so a caller
can rely on them mechanically, which means a test that merely checks the tool
"works" would miss the whole point.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from secrev.cli import EXIT_INTERNAL, EXIT_OK, EXIT_USAGE, main

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

BROKEN_CATALOG = """\
version: "0000.00.0"
patterns:
  - id: ci.deliberately_broken
    layer: [code]
    regex: 'nothing'
    flags: [zzz]
    precision: high
"""


def run(args: list[str]) -> int:
    return main(args)


# --- exit codes ----------------------------------------------------------


def test_recon_succeeds(tmp_path: Path) -> None:
    assert run(["recon", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK


def test_sweep_succeeds(tmp_path: Path) -> None:
    assert run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK


def test_sweep_finding_candidates_is_not_a_gate_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 means "unresolved candidates remain" (`STACK.md` §3). In M1 every
    candidate is unresolved by definition (FR-3.2), so returning 1 on a normal
    sweep would make the code meaningless to the first hook that trusted it.
    The sweep below finds plenty and still exits 0."""
    code = run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    assert code == EXIT_OK
    assert capsys.readouterr().out.count("\n") > 10


def test_missing_target_is_a_usage_error(tmp_path: Path) -> None:
    code = run(["recon", str(tmp_path / "absent"), "--workspace", str(tmp_path)])
    assert code == EXIT_USAGE


def test_malformed_catalog_exits_2_and_names_the_pattern(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`BRIEF_M1.md` §7, and the assertion `.github/workflows/ci.yml` makes on
    every push. The id has to reach **stderr**, which is where that job reads
    it from."""
    catalog = tmp_path / "broken.yaml"
    catalog.write_text(BROKEN_CATALOG, encoding="utf-8")

    code = run(
        [
            "sweep",
            str(FIXTURES),
            "--catalog",
            str(catalog),
            "--workspace",
            str(tmp_path / "ws"),
        ]
    )
    assert code == EXIT_USAGE
    assert "ci.deliberately_broken" in capsys.readouterr().err


def test_a_missing_catalog_file_is_usage_not_internal(tmp_path: Path) -> None:
    """Exit 2, not 3. The tool did not break; the argument was wrong, and the
    0/1/2/3 split is only useful if those stay apart."""
    code = run(
        [
            "sweep",
            str(FIXTURES),
            "--catalog",
            str(tmp_path / "nope.yaml"),
            "--workspace",
            str(tmp_path / "ws"),
        ]
    )
    assert code == EXIT_USAGE
    assert code != EXIT_INTERNAL


# --- G-4 -----------------------------------------------------------------


def test_a_workspace_inside_the_target_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """G-4: a review never writes into the artifact it is reviewing.
    `--workspace .` from inside the target is an easy thing to type, so the
    containment is asserted rather than assumed."""
    target = tmp_path / "artifact"
    target.mkdir()
    (target / "a.py").write_text("x = 1\n", encoding="utf-8")

    code = run(["recon", str(target), "--workspace", str(target / "out")])
    assert code == EXIT_USAGE
    assert "G-4" in capsys.readouterr().err
    assert not (target / "out").exists()


# --- streams -------------------------------------------------------------


def test_stdout_is_parseable_jsonl_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`STACK.md` §3: `secrev sweep target > hits.jsonl` must produce a valid
    file. Every progress line therefore goes to stderr, including the one
    naming the workspace."""
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    captured = capsys.readouterr()

    records = [json.loads(line) for line in captured.out.splitlines()]
    assert records
    assert all(record["status"] == "unresolved" for record in records)
    assert "workspace:" in captured.err


def test_recon_stdout_is_parseable_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(["recon", str(FIXTURES), "--workspace", str(tmp_path)])
    document = json.loads(capsys.readouterr().out)
    assert document["inventory"]["files_total"] > 0


# --- workspace layout ----------------------------------------------------


def test_artifacts_land_in_the_versioned_workspace(tmp_path: Path) -> None:
    """`STACK.md` §6: `<base>/<slug>/<version>/`. Built now even though nothing
    reads across versions until M7, because the layout is what makes re-review
    (D-4) possible later."""
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    produced = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert {"hits.jsonl", "run.json"} <= produced
    assert (tmp_path / "fixtures" / "unversioned" / "hits.jsonl").is_file()


def test_run_json_is_the_only_artifact_carrying_time(tmp_path: Path) -> None:
    """`STACK.md` §5: no timestamps in deterministic outputs; `run.json` alone
    is exempt. This asserts both halves — that time is present where it belongs
    and absent everywhere else."""
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["recon", str(FIXTURES), "--workspace", str(tmp_path)])
    directory = tmp_path / "fixtures" / "unversioned"

    run_json = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert "started_at" in run_json
    assert run_json["window_spec"] == "lines-20"

    for name in ("hits.jsonl", "recon.json"):
        text = (directory / name).read_text(encoding="utf-8")
        assert not re.search(r"\d{4}-\d{2}-\d{2}T", text)


def test_the_file_and_stdout_agree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Both destinations carry the same bytes. §7's third checklist item wants
    the workspace file; §3 wants the redirect to work. If they diverged, one of
    the two contracts would be quietly false."""
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    written = (tmp_path / "fixtures" / "unversioned" / "hits.jsonl").read_text(encoding="utf-8")
    assert capsys.readouterr().out == written
