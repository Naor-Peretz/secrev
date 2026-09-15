"""`recon.json`. BRIEF_M1.md §3, FR-1.1.

The golden is `tests/golden/recon.json`, compared byte for byte. As with the
sweep golden it is regenerated deliberately and never repaired — a diff means
the fixture tree or the classification rules changed, and both are decisions.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from secrev.recon import git_identity, recon, slug, to_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden" / "recon.json"


def test_matches_the_golden_byte_for_byte() -> None:
    assert to_json(recon(FIXTURES)) == GOLDEN.read_text(encoding="utf-8")


def test_two_runs_are_byte_identical() -> None:
    assert to_json(recon(FIXTURES)) == to_json(recon(FIXTURES))


def test_no_absolute_path_appears_in_the_artifact() -> None:
    """`STACK.md` §5: paths are relative to the target root. An absolute path
    makes the output depend on where the target happened to be checked out,
    which breaks NFR-3 across machines while looking fine on one."""
    assert str(ROOT) not in to_json(recon(FIXTURES))


def test_no_timestamp_appears_in_the_artifact() -> None:
    """Time lives in `run.json` alone, which NFR-3 exempts. Two runs a second
    apart must produce the same bytes, so nothing date-shaped may appear."""
    document = to_json(recon(FIXTURES))
    assert not re.search(r"\d{4}-\d{2}-\d{2}", document)
    assert "started_at" not in document


def test_exclusions_are_recorded_as_applied_not_silently() -> None:
    """`STACK.md` §5. A reader cannot tell an empty `node_modules/` from a
    skipped one unless told, and the fixture tree contains a populated one
    precisely so this is exercised."""
    result = recon(FIXTURES)
    assert "node_modules/" in result.inventory["excluded"]
    assert not any("node_modules" in path for path in result.inventory["binary"])


def test_binary_is_detected_by_content_and_listed() -> None:
    result = recon(FIXTURES)
    assert result.inventory["binary"] == ["assets/blob.bin"]


def test_binary_files_are_not_counted_as_a_language() -> None:
    result = recon(FIXTURES)
    assert sum(result.inventory["by_language"].values()) < result.inventory["files_total"]


def test_coverage_gaps_state_what_m1_does_not_do() -> None:
    """FR-3.8: degrade honestly. §3's example implies structural analysis
    exists for some languages; in M1 it exists for none, and saying "no
    coverage for yaml, markdown" would understate the gap by implying the rest
    were covered."""
    gaps = recon(FIXTURES).coverage_gaps
    assert any("structural analysis not implemented" in gap for gap in gaps)
    assert any("surface enumeration not implemented" in gap for gap in gaps)


def test_entrypoints_are_declared_metadata_only(tmp_path: Path) -> None:
    """§3: "Deeper enumeration is M2's job; do not attempt it here."""
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\ndemo = "demo.cli:main"\n', encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    result = recon(tmp_path)
    assert result.entrypoints["declared"] == ["demo = demo.cli:main"]


def test_a_malformed_manifest_does_not_crash_the_run(tmp_path: Path) -> None:
    """A target's manifest is untrusted input like everything else in it. An
    unparseable one means "no declared entry points found", not a traceback —
    the tool has to survive reviewing a broken artifact."""
    (tmp_path / "pyproject.toml").write_text("[project.scripts\nbroken", encoding="utf-8")
    assert recon(tmp_path).entrypoints["declared"] == []


def test_git_identity_reads_a_real_checkout() -> None:
    """This repository is one, so the assertion has a real subject."""
    source, sha = git_identity(ROOT)
    assert source == "git"
    assert sha is not None
    assert len(sha) == 40


def test_git_identity_degrades_rather_than_guesses(tmp_path: Path) -> None:
    """A tree that is not a checkout yields a true statement instead of an
    inferred version. `version` becomes part of the workspace path, and a
    fabricated one splits a single target's history across two directories
    that never reconcile."""
    assert git_identity(tmp_path) == ("directory", None)
    result = recon(tmp_path)
    assert result.target["version"] == "unversioned"
    assert result.target["sha"] is None


def test_git_identity_does_not_follow_a_worktree_pointer(tmp_path: Path) -> None:
    """`.git` as a file points outside the target. P9 makes leaving the tree a
    question rather than a path to chase silently."""
    (tmp_path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
    assert git_identity(tmp_path) == ("directory", None)


def test_slug_is_stable_across_unicode_forms() -> None:
    """The slug is a directory name in the workspace, so it must be the same
    string whether the filesystem handed back NFC or NFD.

    Both inputs are built with `unicodedata` rather than typed as literals. A
    source file holds exactly one normalisation, so a literal-versus-literal
    comparison here would compare a string to itself and pass no matter what
    `slug` did — which is precisely the defect the assertion is about.
    """
    composed = unicodedata.normalize("NFC", "Caf\u00e9 Project")
    decomposed = unicodedata.normalize("NFD", "Caf\u00e9 Project")
    assert composed != decomposed
    assert slug(composed) == slug(decomposed) == "cafe-project"


def test_slug_collapses_and_trims_separators() -> None:
    assert slug("My Target!!") == "my-target"
    assert slug("...") == "target"
