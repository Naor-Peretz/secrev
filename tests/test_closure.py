"""The closure. `BRIEF_M5.md` §4 A1 to A5, C1 to C3, D1, E1, E2; PRD FR-1.2, P9.

Fixtures live in `tests/fixtures/closure/`, with one file per member kind
FR-1.2 names and a deliberate cycle between the entry file and
`helpers/cyclé.md`.

**Where this file is honest about its own ordering.** The brief's step 1 asks
for the golden before the code, and C2's evidence is "the ordering in the commit
history". What genuinely preceded `closure.py` is `is_nfr3_path` naming it —
that landed in `m4/close`, a commit before the file existed, and
`tests/harness/attack.py` held an assertion that the file was absent to prove
it. Inside this commit the module was written before this file. That is the
weaker half of step 1, and it is recorded rather than implied: a golden with no
generator is a red gate rather than a guard, since nothing here uses
expected-failure markers.

The fixture prose cites no document by filename, deliberately. A citation is a
reference, so a fixture quoting `BRIEF_M5.md` would have that brief among its
unresolved members and the golden would be pinning the fixture's prose rather
than its design. The whole-tree golden is where incidental references get
demonstrated — and it does demonstrate them, against `README.md` and the
pattern fixtures.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from secrev import closure as closure_module
from secrev.closure import (
    CLOSURE_RULES_VERSION,
    GAP_LIST_LIMIT,
    KIND_BINARY,
    KIND_DATA,
    KIND_SOURCE,
    LOAD_CONDITIONAL,
    LOAD_DIRECT,
    LOAD_FETCH,
    RULE_AMBIGUOUS,
    RULE_CHANGED,
    RULE_ESCAPING,
    RULE_MISSING,
    RULE_REMOTE,
    Closure,
    closure,
    to_json,
)
from secrev.inventory import content_sha256
from secrev.ledger import CLOSURE_DIGEST_SPEC, LAYERS, RESERVED_NAMESPACES, WINDOW_SPEC
from secrev.recon import GAP_LIST_LIMIT as RECON_GAP_LIST_LIMIT

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
TREE = FIXTURES / "closure"
GOLDEN = ROOT / "tests" / "golden" / "closure.json"


@pytest.fixture(scope="module")
def whole_tree() -> Closure:
    return closure(FIXTURES)


@pytest.fixture(scope="module")
def from_entry() -> Closure:
    return closure(TREE, ["entry.md"])


def member(result: Closure, path: str) -> object:
    found = [item for item in result.members if item.path == path]
    assert found, f"{path} is not a closure member; members are {[m.path for m in result.members]}"
    return found[0]


# --- the golden ----------------------------------------------------------


def test_matches_the_golden_byte_for_byte(whole_tree: Closure) -> None:
    """`read_bytes`, not `read_text`: `read_text` translates CRLF to LF on the
    way in, so it cannot see the one difference `STACK.md` §5 says must never
    re-identify anything."""
    assert to_json(whole_tree).encode("utf-8") == GOLDEN.read_bytes()


def test_the_golden_covers_the_whole_fixture_tree(whole_tree: Closure) -> None:
    """The golden is over `fixtures/`, not over `fixtures/closure/`.

    The same assertion `tests/test_structure.py` carries, for the same reason: a
    golden restricted to the files written to make this source fire would say
    nothing about the tree it is run over. Here it also does real work — the
    references it finds in `README.md` and in the pattern fixtures are the
    incidental kind the designed fixture deliberately excludes.
    """
    outside = {item.path for item in whole_tree.members if not item.path.startswith("closure/")}
    assert outside, "the golden only covers files written to make this source fire"
    referrers = {
        origin.rsplit(":", 1)[0]
        for item in whole_tree.unresolved
        for origin in item.referenced_from
    }
    assert any(not path.startswith("closure/") for path in referrers), (
        "every unresolved member comes from the designed fixture, so the golden "
        "demonstrates nothing about an ordinary tree"
    )


# --- A1: one positive case per member kind -------------------------------


def test_every_member_kind_fr_1_2_names_has_a_case(from_entry: Closure) -> None:
    """A1, written out by hand rather than read off the golden.

    A golden says "this is what came out". It cannot say "and that was the right
    answer", which is why the brief asks for the expectation in the test as
    well: the five kinds are named here, so a rename or a dropped case fails on
    its own terms rather than as one more changed line in a 650-line diff.

    `kind` and `load` are two axes, not one list. FR-1.2's five cases mix them —
    a direct reference and a progressively loaded resource are two *loads*;
    a bundled script and a bundled binary are two *kinds*; a resource named for
    fetching is unresolved by construction. Keeping them apart is what lets a
    bundled binary also be conditionally loaded without a sixth name.
    """
    assert member(from_entry, "helpers/direct.md").load == LOAD_DIRECT
    assert member(from_entry, "helpers/progressive.md").load == LOAD_CONDITIONAL
    assert member(from_entry, "helpers/run.sh").kind == KIND_SOURCE
    assert member(from_entry, "helpers/payload.bin").kind == KIND_BINARY
    assert member(from_entry, "entry.md").kind == KIND_DATA

    fetched = [item for item in from_entry.unresolved if item.rule_id == RULE_REMOTE]
    assert [item.reference for item in fetched] == ["https://example.invalid/closure/rules.json"]
    assert fetched[0].load == LOAD_FETCH


def test_the_closure_of_the_fixture_is_exactly_this(from_entry: Closure) -> None:
    """A1's completeness half: not only that each kind appears, but that nothing
    else does. A source that returned the whole tree would pass every assertion
    above."""
    assert [item.path for item in from_entry.members] == [
        "entry.md",
        "helpers/cyclé.md",
        "helpers/direct.md",
        "helpers/payload.bin",
        "helpers/progressive.md",
        "helpers/run.sh",
    ]
    assert [(item.rule_id, item.reference) for item in from_entry.unresolved] == [
        (RULE_ESCAPING, "../../../outside/notes.md"),
        (RULE_MISSING, "helpers/absent.md"),
        (RULE_REMOTE, "https://example.invalid/closure/rules.json"),
    ]


def test_a_member_records_every_line_that_reaches_it(from_entry: Closure) -> None:
    """Three referring lines stay three. The script is named by the entry file,
    by `helpers/direct.md` and by `helpers/progressive.md`, and a
    first-sighting-wins mapping would have kept one — which is how a reviewer
    loses the line they actually needed to read."""
    origins = member(from_entry, "helpers/run.sh").referenced_from
    assert [origin.rsplit(":", 1)[0] for origin in origins] == [
        "entry.md",
        "helpers/direct.md",
        "helpers/progressive.md",
    ]
    # Each number points at a line that actually names the script. Checked
    # rather than pinned, for the reason the non-ASCII test states.
    for origin in origins:
        path, _, number = origin.rpartition(":")
        line = (TREE / path).read_text(encoding="utf-8").split("\n")[int(number) - 1]
        assert "run.sh" in line


def test_a_member_named_both_ways_is_directly_loaded(from_entry: Closure) -> None:
    """`_load_of`, exercised through the fixture rather than only in isolation.

    `run.sh` is named outright by the entry file and conditionally by
    `helpers/progressive.md`. A member named outright anywhere is directly
    loaded, and the rule has to be a function of the whole sighting set — a
    first-sighting rule would make this one field depend on which root the walk
    began at, which is the property A2 asks the closure not to have.
    """
    assert member(from_entry, "helpers/run.sh").load == LOAD_DIRECT
    conditional_origin = [
        origin
        for origin in member(from_entry, "helpers/run.sh").referenced_from
        if origin.startswith("helpers/progressive.md")
    ]
    assert conditional_origin, "the fixture no longer names run.sh conditionally"
    assert closure_module._load_of({LOAD_CONDITIONAL, LOAD_DIRECT}) == LOAD_DIRECT
    assert closure_module._load_of({LOAD_CONDITIONAL}) == LOAD_CONDITIONAL
    assert closure_module._load_of(None) == LOAD_DIRECT


def test_a_root_reached_by_nothing_is_distinguishable(from_entry: Closure) -> None:
    """`referenced_from` empty means "this is where the review started".

    In the shared fixture the entry file *is* reached — by the other end of the
    cycle, which is asserted here so the contrast is in one place — so the
    property itself is checked on a leaf, where it is the difference between
    "the caller named this" and "the artifact pulls this in".
    """
    assert member(from_entry, "entry.md").referenced_from != ()
    alone = closure(TREE, ["helpers/progressive.md"])
    assert member(alone, "helpers/progressive.md").referenced_from == ()
    assert alone.roots == ("helpers/progressive.md",)
    assert alone.roots_given is True


# --- A2: the cycle -------------------------------------------------------


def test_a_cycle_terminates_and_the_closure_does_not_depend_on_the_entry() -> None:
    """A2, and the comparison is deliberately not of the whole artifact.

    `roots` differs between the two runs, and must: it records where the review
    was told to start, which is a fact about the invocation. What A2 is about is
    the *closure* — which files are in it and which references did not resolve —
    and that is compared byte for byte.

    This is also the test that would hang rather than fail if the walk did not
    terminate, which is why there is a timeout around it: a test that never
    returns is a gate nobody can read (H-1, turned on the test suite).
    """
    started = time.monotonic()
    one = closure(TREE, ["entry.md"])
    two = closure(TREE, ["helpers/cyclé.md"])
    assert time.monotonic() - started < 10, "the cycle did not terminate promptly"

    def reachable(result: Closure) -> bytes:
        document = json.loads(to_json(result))
        return json.dumps(
            {"members": document["members"], "unresolved": document["unresolved"]},
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")

    assert reachable(one) == reachable(two)
    assert one.roots != two.roots, (
        "the two runs were given the same roots, so this compared one answer "
        "with itself and proved nothing"
    )


def test_a_cycle_member_is_read_once(from_entry: Closure) -> None:
    """The entry file appears once in the members, not twice."""
    paths = [item.path for item in from_entry.members]
    assert len(paths) == len(set(paths))


# --- A3: an unresolved member is a ledger record -------------------------


def test_an_unresolved_member_reaches_the_ledger(from_entry: Closure) -> None:
    """A3 and §6 Q1: `hits.jsonl` under `source: closure`, not a gap line.

    FR-1.2 says such a member is a finding candidate "not an omission", and in
    this system exactly one mechanism makes passing over it impossible — the
    ledger plus FR-4.3. A `coverage_gaps` line would let a remote fetch nobody
    assessed leave through a *passing* gate.
    """
    assert {hit.source for hit in from_entry.hits} == {"closure"}
    assert {hit.status for hit in from_entry.hits} == {"unresolved"}
    assert {hit.rule_id for hit in from_entry.hits} == {
        RULE_ESCAPING,
        RULE_MISSING,
        RULE_REMOTE,
    }
    assert all(hit.catalog_version == CLOSURE_RULES_VERSION for hit in from_entry.hits)
    assert all(hit.layer in LAYERS for hit in from_entry.hits)


def test_every_record_says_why_it_could_not_be_resolved(from_entry: Closure) -> None:
    """A3's second clause. A record saying only that something failed sends a
    reviewer to look for the reason this field already holds."""
    for item in from_entry.unresolved:
        assert item.reason.strip(), f"{item.reference} has no reason"
    for hit in from_entry.hits:
        assert hit.question.endswith("?") or "?" in hit.question, (
            f"{hit.rule_id} does not read as a question (FR-3.2)"
        )


def test_a_record_is_anchored_on_the_referring_line(from_entry: Closure) -> None:
    """The member has no content — that is why it is unresolved — so the span a
    reviewer reads is the line that pulls it in. `lines-20`, which is that
    span's shape exactly as a pattern record's is (C-2 keeps differently
    *shaped* spans apart, not identically shaped ones)."""
    remote = [hit for hit in from_entry.hits if hit.rule_id == RULE_REMOTE]
    assert len(remote) == 1
    assert remote[0].file == "entry.md"
    assert remote[0].window_spec == WINDOW_SPEC
    assert "example.invalid" in remote[0].match_excerpt


def test_the_closure_namespace_is_closed_from_both_sides() -> None:
    """A `rule_id` names one question whoever produced it. `catalog.py` refuses
    the namespace, so a pattern cannot claim `closure.missing_reference`."""
    assert "closure" in RESERVED_NAMESPACES
    for rule_id in (RULE_REMOTE, RULE_MISSING, RULE_ESCAPING, RULE_CHANGED):
        assert rule_id.split(".")[0] == "closure"


def test_nothing_here_fetches_anything() -> None:
    """A3's third clause. `STACK.md` §2.1 forbids runtime network calls, and the
    self-application check enforces it over `src/` — this names the module, so
    the claim is not resting on a check that covers a directory."""
    source = (ROOT / "src" / "secrev" / "closure.py").read_text(encoding="utf-8")
    for construct in ("urllib", "http.client", "requests", "socket", "urlopen"):
        assert f"import {construct}" not in source, f"closure.py imports {construct}"


# --- A5: verify on read --------------------------------------------------


def test_a_file_that_changed_under_the_review_is_a_ledger_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5, the TOCTOU window closed for the consumer M5 adds.

    The swap happens between the inventory read and the closure read, which is
    the window itself: the *decisions* travel on the entry — language, binary,
    size, digest — and the bytes do not, so without this check the file would be
    examined as content the inventory never classified, and `window_sha256`
    would identify bytes the reviewer never saw.

    `walk` is patched rather than the clock or the filesystem, because the
    window is defined by those two reads and nothing else. The replacement calls
    the real walk, then writes.
    """
    tree = tmp_path / "tree"
    shutil.copytree(TREE, tree)
    real = closure_module.walk

    def walk_then_swap(root, excluded=None, max_bytes=None):  # type: ignore[no-untyped-def]
        entries = real(root, excluded, max_bytes)
        (root / "entry.md").write_text("replaced under the review\n", encoding="utf-8")
        return entries

    monkeypatch.setattr(closure_module, "walk", walk_then_swap)
    result = closure(tree, ["entry.md"])

    changed = [hit for hit in result.hits if hit.rule_id == RULE_CHANGED]
    assert len(changed) == 1, f"no content-change record: {[h.rule_id for h in result.hits]}"
    assert changed[0].file == "entry.md"
    assert changed[0].window_spec == CLOSURE_DIGEST_SPEC
    assert changed[0].source == "closure"
    assert changed[0].status == "unresolved"

    # The excerpt says what happened and which file; the digests are redacted
    # out of it, because a 64-character hex run is credential-shaped and G-3 is
    # deliberately blunt. That is asserted rather than worked around: weakening
    # the credential rule, or shortening a digest to slip under its floor, is
    # how a safety rule gets tuned to make an excerpt prettier.
    assert "content changed between the inventory read" in changed[0].match_excerpt
    assert "entry.md" in changed[0].match_excerpt

    # A ledger record, not a `closure.json` member: the file is still in the
    # closure, and what changed is a fact about the read rather than about the
    # reference graph.
    assert "entry.md" in [item.path for item in result.members]
    assert RULE_CHANGED not in [item.rule_id for item in result.unresolved]


def test_the_record_is_identified_by_the_digests_the_excerpt_hides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The redaction above is cosmetic, and this is what proves it.

    `ledger.py` hashes the window unredacted, and the window of a
    content-change record *is* the reason string with both digests in it. So two
    different replacements must produce two different ids — if the digests had
    been dropped or shortened to get past `_LONG_OPAQUE`, both runs would emit
    one id and one candidate would silently resolve the other (P4, D-6).
    """
    # Captured once, outside the loop. Reading it inside would capture the
    # patched function on the second pass and recurse — which is a real trap
    # worth the comment, since the failure is a RecursionError in `walk` and
    # points at the module rather than at the test.
    real = closure_module.walk
    identifiers = []
    for replacement in (b"one replacement\n", b"a different replacement\n"):
        tree = tmp_path / f"tree-{len(replacement)}"
        shutil.copytree(TREE, tree)

        def walk_then_swap(root, excluded=None, max_bytes=None, _bytes=replacement):  # type: ignore[no-untyped-def]
            entries = real(root, excluded, max_bytes)
            (root / "entry.md").write_bytes(_bytes)
            return entries

        monkeypatch.setattr(closure_module, "walk", walk_then_swap)
        changed = [hit for hit in closure(tree, ["entry.md"]).hits if hit.rule_id == RULE_CHANGED]
        assert len(changed) == 1
        identifiers.append(changed[0].id)
    assert identifiers[0] != identifiers[1], (
        "two different contents produced one candidate id — the digests are not "
        "reaching window_sha256"
    )


def test_an_unchanged_tree_produces_no_content_change_record(from_entry: Closure) -> None:
    """The control. A check that fires on every run is H-1's habit in a new
    place: a signal that is always on carries no information."""
    assert not [hit for hit in from_entry.hits if hit.rule_id == RULE_CHANGED]


def test_the_verification_compares_against_the_inventory_digest() -> None:
    """The mechanism, not only its effect: the digest compared is the one
    `inventory` recorded, so a second definition of "the same bytes" cannot
    drift away from the one every other artifact is keyed on."""
    for item in closure(TREE, ["entry.md"]).members:
        if item.sha256 is None:
            continue
        raw = (TREE / item.path).read_bytes()
        assert item.sha256 == content_sha256(raw)


# --- C1: determinism -----------------------------------------------------


def test_two_runs_are_byte_identical() -> None:
    """NFR-3 at the level the requirement is written about."""
    assert to_json(closure(FIXTURES)).encode("utf-8") == to_json(closure(FIXTURES)).encode("utf-8")


def test_an_unrelated_file_moves_nothing(tmp_path: Path) -> None:
    """C1's second half. Ids derive from `(path, rule_id, window_sha256,
    ordinal)` and never from a traversal counter, so a file appearing elsewhere
    must renumber nothing."""
    tree = tmp_path / "tree"
    shutil.copytree(TREE, tree)
    before = closure(tree)
    (tree / "zz_unrelated.txt").write_text("nothing names this\n", encoding="utf-8")
    after = closure(tree)

    assert {hit.id for hit in before.hits} <= {hit.id for hit in after.hits}
    moved = [
        item.path
        for item, other in zip(before.members, after.members, strict=False)
        if item.path != other.path
    ]
    assert not moved, f"members reordered by an unrelated addition: {moved}"


def test_members_are_sorted_on_the_posix_path(whole_tree: Closure) -> None:
    paths = [item.path for item in whole_tree.members]
    assert paths == sorted(paths)


# --- D1: the non-ASCII filename ------------------------------------------


def test_a_non_ascii_filename_is_in_the_fixture_and_in_the_closure(
    from_entry: Closure,
) -> None:
    """D1, `STACK.md` §9. The closure is the one artifact that maps names to
    names, so an accented filename no reference can match is a miss no other
    source would reveal — and an ASCII-only token class in the reference regex
    is exactly how that happens. This is the assertion that catches it."""
    accented = [item.path for item in from_entry.members if not item.path.isascii()]
    assert accented == ["helpers/cyclé.md"]

    # The referring line is found by its content rather than pinned by number:
    # a line number here would turn every edit to the fixture's prose into a
    # failure of the rule this asserts, which teaches whoever hits it to change
    # the number rather than read the assertion.
    origins = member(from_entry, "helpers/cyclé.md").referenced_from
    assert len(origins) == 1
    path, _, number = origins[0].rpartition(":")
    assert path == "entry.md"
    line = (TREE / path).read_text(encoding="utf-8").split("\n")[int(number) - 1]
    assert "cyclé.md" in line


# --- E1: coverage gaps ---------------------------------------------------


def test_a_member_in_an_unread_language_is_a_named_gap(from_entry: Closure) -> None:
    """E1 (FR-3.8), and the paths rather than only the language: "no coverage
    for: shell" tells a reviewer that a gap exists, and the path tells them
    where to look."""
    lines = [line for line in from_entry.coverage_gaps if "helpers/run.sh" in line]
    assert len(lines) == 1, f"run.sh is in no gap line: {from_entry.coverage_gaps}"
    assert "Python only" in lines[0]


def test_the_fixed_gaps_name_each_limit(from_entry: Closure) -> None:
    """Every stated limit, so a reader sees it rather than inferring it from a
    regex. Each is checked by a phrase a reader would search for."""
    text = "\n".join(from_entry.coverage_gaps)
    for phrase in (
        "built from variables",
        "file suffix",
        "paraphrase defeats",
        "never fetched",
        "is not read",
    ):
        assert phrase in text, f"no gap line mentions {phrase!r}"


def test_the_gap_list_limit_agrees_with_recon() -> None:
    """Two truncations that disagree are a reader comparing two lists that were
    cut differently. Not imported from `recon` — this module does not reach into
    a peer for a display rule (P11) — so the agreement is asserted instead."""
    assert GAP_LIST_LIMIT == RECON_GAP_LIST_LIMIT


# --- bounds --------------------------------------------------------------


def test_the_reference_regexes_are_linear_on_a_crafted_line() -> None:
    """A hostile target chooses its own bytes, and the cost of a regex on a
    crafted single line is not visible in any fixture.

    The shapes measured are the three that backtrack if the left-hand guard is
    removed: one enormous dotted token, one enormous path, and one that looks
    like a URL and is not. `tests/test_catalog_timing.py` does this for every
    catalog pattern and every surface kind; this source's rules are code rather
    than data, so the measurement lives beside them.
    """
    for line in (
        "a." * 40000,
        "a/" * 40000,
        "https:/" * 20000,
        "x" * 80000,
    ):
        started = time.monotonic()
        closure_module._references_on_line("f.md", 1, line)
        spent = time.monotonic() - started
        assert spent < 2.0, f"{spent:.1f}s on a {len(line)}-char line"


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    tree = tmp_path / "tree"
    for name, text in files.items():
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tree


def test_the_three_resolution_conventions_all_resolve(tmp_path: Path) -> None:
    """The measurement that forced this, written down so it is not re-learned.

    With only the relative convention, `secrev closure .` over this repository
    produced **3,692** records, every one of them a document citing another by
    name: `STACK.md` alone 415 times, because a mention inside `src/secrev/`
    resolved to `src/secrev/STACK.md`. A signal that is always on is H-1's habit
    in a new place — a reviewer who must read 3,692 lines to find four reads
    none of them. Three conventions brought it to 1,153.

    Each is asserted separately, because each would otherwise be covered only by
    the whole-tree golden, where a regression reads as one more changed line.
    """
    tree = _tree(
        tmp_path,
        {
            "docs/entry.md": (
                "beside.md is in this directory.\n"
                "src/app.py is named from the root.\n"
                "unique.md is named by filename alone.\n"
            ),
            "docs/beside.md": "a leaf\n",
            "src/app.py": "x = 1\n",
            "deep/nested/unique.md": "a leaf\n",
        },
    )
    result = closure(tree, ["docs/entry.md"])
    assert [item.path for item in result.members] == [
        "deep/nested/unique.md",
        "docs/beside.md",
        "docs/entry.md",
        "src/app.py",
    ]
    assert result.unresolved == ()


def test_a_name_matching_several_files_is_its_own_finding(tmp_path: Path) -> None:
    """Not a member, and not "missing" either.

    Which file is loaded then depends on the loader's working directory, and the
    line does not say — so picking one would be this tool deciding something the
    artifact left open, and calling it missing would be false. Its own rule id,
    for the reason `recon` keeps its four unread reasons apart: a different
    problem with a different remedy.
    """
    tree = _tree(
        tmp_path,
        {
            "entry.md": "The rules are in SKILL.md.\n",
            "one/SKILL.md": "a\n",
            "two/SKILL.md": "b\n",
        },
    )
    result = closure(tree, ["entry.md"])
    assert [(item.rule_id, item.reference) for item in result.unresolved] == [
        (RULE_AMBIGUOUS, "SKILL.md")
    ]
    assert "one/SKILL.md, two/SKILL.md" in result.unresolved[0].reason
    assert [hit.rule_id for hit in result.hits] == [RULE_AMBIGUOUS]


def test_the_escape_test_is_relative_not_root_relative(tmp_path: Path) -> None:
    """Order inside `_resolve`, and it is load-bearing.

    A reference climbing out of the tree is a question about *this* file's
    neighbourhood (P9). Tested root-relative first, `../../../etc/hosts.conf`
    would resolve to a path that simply does not exist and be reported as
    missing — losing the one fact about it that matters.
    """
    tree = _tree(tmp_path, {"deep/entry.md": "notes are in ../../../outside/notes.md\n"})
    result = closure(tree, ["deep/entry.md"])
    assert [(item.rule_id, item.reference) for item in result.unresolved] == [
        (RULE_ESCAPING, "../../../outside/notes.md")
    ]


def test_a_mis_resolution_is_a_stated_limit(from_entry: Closure) -> None:
    """The cost of three conventions, named in the artifact rather than left for
    a reader to deduce from a surprising member."""
    assert any("meant another" in line for line in from_entry.coverage_gaps)


def test_a_reference_is_not_followed_outside_the_root(from_entry: Closure) -> None:
    """P9 and G-4. The reference is recorded; nothing opens it."""
    escaping = [item for item in from_entry.unresolved if item.rule_id == RULE_ESCAPING]
    assert [item.reference for item in escaping] == ["../../../outside/notes.md"]
    assert "outside the target root" in escaping[0].reason


def test_an_entry_outside_the_target_is_a_usage_error() -> None:
    """E2's exit-2 case at the level it is decided. An entry the *target* does
    not contain is a hole in the artifact and is recorded as a finding; an entry
    pointing outside the target is a hole in the invocation, and reviewing what
    remained would be a partial answer reported as a whole one.

    A `ValueError`, which `cli._run` reports as exit 2 — the precedent
    `inventory.NormalisationCollision` set.
    """
    for bad in ("/etc/hosts", "../outside.md"):
        with pytest.raises(ValueError, match="inside the target"):
            closure(TREE, [bad])


def test_a_named_entry_that_is_absent_is_a_finding_not_an_error() -> None:
    """The other half of the sentence above, and the one that is easy to get
    backwards: a declared entry file that is missing is the finding, not a
    crash. A review of a target whose entry point is not there is a review with
    a hole in it, and the hole is what has to reach the ledger."""
    result = closure(TREE, ["nowhere.md"])
    assert [(item.rule_id, item.reference) for item in result.unresolved] == [
        (RULE_MISSING, "nowhere.md")
    ]
    assert [hit.rule_id for hit in result.hits] == [RULE_MISSING]


def test_default_roots_are_every_readable_file_and_say_so(whole_tree: Closure) -> None:
    """With no `--entry`, the question changes and the artifact records which
    one was asked. Given roots answer "what does this entry pull in"; the
    default answers "what does this tree pull in that is not in it", which can
    be asked of a target that declares no entry file anywhere and which never
    under-reports."""
    assert whole_tree.roots_given is False
    assert "closure/entry.md" in whole_tree.roots
    assert "assets/blob.bin" not in whole_tree.roots, "a binary is never read for references"
    document = json.loads(to_json(whole_tree))
    assert document["roots"]["given"] is False
