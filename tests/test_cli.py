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

from secrev.cli import EXIT_INTERNAL, EXIT_OK, EXIT_USAGE, main, merge_ledger

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PATTERN_GOLDEN = ROOT / "tests" / "golden" / "hits.jsonl"
SURFACE_GOLDEN = ROOT / "tests" / "golden" / "surfaces.jsonl"

BROKEN_KINDS = """\
version: "0000.00.0"
kinds:
  - id: surface.deliberately_broken
    layer: [code]
    precision: high
    files: ["*.py"]
    declaration: 'x'
    question: 'Reachable?'
    flags: [zzz]
"""

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
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["recon", str(FIXTURES), "--workspace", str(tmp_path)])
    directory = tmp_path / "fixtures" / "unversioned"

    run_json = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert all("started_at" in entry for entry in run_json.values())
    assert run_json["sweep"]["window_spec"] == "lines-20"

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


# --- `secrev surfaces` and the two-block ledger (TASKS_M2.md TASK-M2-007) --


def ledger(workspace: Path) -> str:
    return (workspace / "fixtures" / "unversioned" / "hits.jsonl").read_text(encoding="utf-8")


def block(text: str, source: str) -> str:
    return "".join(
        line for line in text.splitlines(keepends=True) if json.loads(line)["source"] == source
    )


def test_surfaces_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK
    assert "surface candidates" in capsys.readouterr().err


def test_surfaces_never_loads_the_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A peer of the pattern source, not a stage after it: a broken or missing
    catalog must not stop the surface source (P11 — detection must not decide
    scope, and neither may the detector's configuration)."""

    def refuse(_argument: str | None) -> None:
        raise AssertionError("surfaces loaded the pattern catalog")

    monkeypatch.setattr("secrev.cli.resolve_catalog", refuse)
    assert run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK


def test_malformed_kinds_exit_2_and_name_the_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    kinds = tmp_path / "broken.yaml"
    kinds.write_text(BROKEN_KINDS, encoding="utf-8")
    code = run(
        ["surfaces", str(FIXTURES), "--kinds", str(kinds), "--workspace", str(tmp_path / "ws")]
    )
    assert code == EXIT_USAGE
    assert "surface.deliberately_broken" in capsys.readouterr().err


def test_both_blocks_are_kept_pattern_block_first(tmp_path: Path) -> None:
    """Q1: one ledger, each source replacing only its own block, pattern block
    first. `surfaces` runs first on purpose: in the other order a merge that
    merely appended the new block would put the pattern block first by luck,
    and this test passed against exactly that defect until it was reordered
    (H-8)."""
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    sources = [json.loads(line)["source"] for line in ledger(tmp_path).splitlines()]
    assert set(sources) == {"pattern", "surface"}
    assert sources == sorted(sources, key=["pattern", "surface"].index)


def test_the_order_the_commands_ran_in_does_not_change_the_ledger(tmp_path: Path) -> None:
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path / "a")])
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path / "a")])
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path / "b")])
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path / "b")])
    assert ledger(tmp_path / "a") == ledger(tmp_path / "b")


def test_each_block_is_its_sources_golden(tmp_path: Path) -> None:
    """The pattern block is byte-identical to the M1 ledger, and the surface
    block to the surface golden: joining them re-serialises nothing."""
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    text = ledger(tmp_path)
    assert block(text, "pattern") == PATTERN_GOLDEN.read_text(encoding="utf-8")
    assert block(text, "surface") == SURFACE_GOLDEN.read_text(encoding="utf-8")
    assert text == block(text, "pattern") + block(text, "surface")


def test_a_rerun_replaces_only_its_own_block(tmp_path: Path) -> None:
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    first = ledger(tmp_path)
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    assert ledger(tmp_path) == first
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    assert ledger(tmp_path) == first


def test_stdout_is_the_runs_own_block(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Owner decision: stdout is what this run produced, so a pipe's output
    depends only on its inputs, never on what ran earlier in the workspace."""
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    capsys.readouterr()
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    assert capsys.readouterr().out == SURFACE_GOLDEN.read_text(encoding="utf-8")


def test_run_json_keeps_one_entry_per_command(tmp_path: Path) -> None:
    """Owner decision: each command replaces only its own entry, so the catalog
    version behind the pattern block survives a later `surfaces` run, and the
    surface entry names the kinds version it ran against — not the catalog's."""
    run(["recon", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)])
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    path = tmp_path / "fixtures" / "unversioned" / "run.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert set(document) == {"recon", "sweep", "surfaces"}
    assert document["sweep"]["window_spec"] == "lines-20"
    assert "catalog_version" in document["sweep"]
    assert document["surfaces"]["window_spec"] == "decl-20"
    assert "kinds_version" in document["surfaces"]
    assert "catalog_version" not in document["surfaces"]


@pytest.mark.parametrize(
    "content",
    ["not json at all\n", '{"id": "x", "source": "somebody_else"}\n', '["a list"]\n'],
)
def test_a_workspace_ledger_that_is_not_ours_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    """Refused, not overwritten: a file this tool cannot read as its own
    ledger is either damaged or someone else's, and replacing a block in it
    would silently discard the rest."""
    directory = tmp_path / "fixtures" / "unversioned"
    directory.mkdir(parents=True)
    (directory / "hits.jsonl").write_text(content, encoding="utf-8")
    code = run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    assert code == EXIT_USAGE
    assert "hits.jsonl" in capsys.readouterr().err
    assert (directory / "hits.jsonl").read_text(encoding="utf-8") == content


# --- found in review -------------------------------------------------------

PATTERN_LINE = '{"id": "p", "source": "pattern"}\n'


@pytest.mark.parametrize("separator", ["\x85", "\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}"])
def test_a_line_separator_inside_a_record_does_not_split_it(separator: str) -> None:
    """`str.splitlines` splits on these and `to_jsonl` writes them unescaped
    (JSON escapes only characters below U+0020), so splitting the ledger that
    way cut a record in two and refused every later run."""
    surface = (
        json.dumps({"id": "s", "source": "surface", "file": f"a{separator}b"}, ensure_ascii=False)
        + "\n"
    )
    assert merge_ledger(surface, "pattern", PATTERN_LINE) == PATTERN_LINE + surface


def test_a_target_cannot_lock_the_ledger_with_a_filename(tmp_path: Path) -> None:
    """The end-to-end shape of the same defect: the reviewed target chooses
    its own filenames, and one carrying U+0085 locked the workspace ledger
    against every later run — the surface source shut out by its target."""
    target = tmp_path / "target"
    skill = target / "a\x85b" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("description: x\n", encoding="utf-8")
    workspace = tmp_path / "ws"
    for command in ("surfaces", "sweep", "surfaces"):
        assert run([command, str(target), "--workspace", str(workspace)]) == EXIT_OK


def test_a_ledger_without_a_final_newline_is_refused_not_joined() -> None:
    with pytest.raises(ValueError, match="newline"):
        merge_ledger(PATTERN_LINE.rstrip("\n"), "surface", '{"id": "s", "source": "surface"}\n')


def test_a_ledger_that_is_not_utf8_is_refused_and_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "fixtures" / "unversioned"
    directory.mkdir(parents=True)
    (directory / "hits.jsonl").write_bytes(b"\xff\xfe\n")
    code = run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])
    assert code == EXIT_USAGE
    assert "hits.jsonl" in capsys.readouterr().err
    assert (directory / "hits.jsonl").read_bytes() == b"\xff\xfe\n"


def test_an_unreadable_run_json_is_replaced_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "fixtures" / "unversioned"
    directory.mkdir(parents=True)
    (directory / "run.json").write_text("{not json", encoding="utf-8")
    assert run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK
    assert "run.json" in capsys.readouterr().err
    document = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert set(document) == {"surfaces"}


def test_an_unexpected_error_is_internal_not_a_gate_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 means "the tool worked and the answer is no" (`STACK.md` §3). A
    bug must not be able to say that."""

    def broken(_root: Path, _kinds: object) -> list[object]:
        raise KeyError("a bug in a source")

    monkeypatch.setattr("secrev.cli.surfaces", broken)
    assert run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_INTERNAL
    assert "internal error" in capsys.readouterr().err
