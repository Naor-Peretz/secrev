"""NFR-3, asserted before the code it constrains exists.

STACK.md §5 fixes traversal order, path normalisation, line endings and id
derivation. Those rules are not a feature of `inventory.py`; they are the
reason it is the first file. `recon.py` and `sweep.py` are both consumers of
the walk, so a walk that is right gives them determinism for free, and a walk
that is wrong makes both of them rewrites.

Written red on purpose. A determinism check added after the generators exist
is a retrofit onto code composed without it, and NFR-3 is the one requirement
that does not survive being retrofitted: getting it wrong invalidates every
verification recorded above it (D-4).

Three assertions, in the order they are easy to break:

  1. two walks of one tree agree, byte for byte
  2. a filename stored NFD and the same name stored NFC hash the same
  3. adding an unrelated file changes no existing entry

The third is the one that matters most for D-4 and the easiest to break
without noticing, because an identity derived from a counter looks correct
until the day something is inserted ahead of it.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest

from secrev import inventory

# "café" — the same grapheme, composed and decomposed. Both forms occur in real
# trees: HFS+ stored a decomposed form, and tools still emit one, so a name can
# arrive either way and survives onto any filesystem. APFS does NOT decompose —
# it preserves what it was given and is insensitive only on lookup (STACK.md §5,
# D-4). Built with unicodedata rather than typed, because this file holds one
# normalisation and two literals would be the same string.
NFC_NAME = unicodedata.normalize("NFC", "café.txt")
NFD_NAME = unicodedata.normalize("NFD", "café.txt")


def build_tree(root: Path, filename: str = NFC_NAME) -> Path:
    """A small tree with the shapes STACK.md §5 names: nested directories, a
    non-ASCII filename, CRLF content, a binary file, and an excluded dir."""
    (root / "pkg" / "sub").mkdir(parents=True)
    (root / "docs").mkdir()

    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "app.py").write_text("import os\nprint(os.name)\n", encoding="utf-8")
    (root / "pkg" / "sub" / "util.py").write_bytes(b"def f():\r\n    return 1\r\n")
    (root / "docs" / filename).write_text("héllo wörld\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00binary")

    excluded = root / ".git"
    excluded.mkdir()
    (excluded / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return root


def test_two_walks_of_one_tree_are_identical(tmp_path: Path) -> None:
    """The floor. If this fails nothing above it can be trusted, and the cause
    is almost always os.walk order reaching the output."""
    root = build_tree(tmp_path / "tree")
    assert inventory.walk(root) == inventory.walk(root)


def test_paths_are_sorted_on_the_posix_string(tmp_path: Path) -> None:
    """Collect, then sort. Emitting in traversal order is stable on one
    machine and on one filesystem, which is exactly why it survives review."""
    root = build_tree(tmp_path / "tree")
    paths = [entry.path for entry in inventory.walk(root)]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths)), "the same path was emitted twice"


def test_the_sorted_assertion_is_not_vacuous(tmp_path: Path) -> None:
    """The test of the test, and the reason it exists.

    `sorted()` was removed from `walk()` deliberately, and this file stayed
    green except for one assertion. Two walks of one tree agree whether or not
    the output is sorted, because `os.walk` is stable within a machine for an
    unchanged tree — so the byte-identity assertion, the obvious one to write,
    does not test the rule it appears to test. Only the explicit
    `paths == sorted(paths)` caught it.

    That assertion is only worth anything while the raw traversal order of the
    fixture tree actually differs from sorted order. If someone reshapes
    `build_tree` into something `os.walk` happens to yield in order, the
    assertion goes quiet without failing — a control that stops controlling
    and reports nothing. This holds it honest.
    """
    root = build_tree(tmp_path / "tree")
    raw = [
        normalised
        for current, _, filenames in os.walk(root)
        for normalised in (
            unicodedata.normalize("NFC", str((Path(current) / name).relative_to(root)))
            for name in filenames
        )
    ]
    assert raw != sorted(raw), (
        "os.walk already yields this fixture in sorted order, so "
        "test_paths_are_sorted_on_the_posix_string can no longer fail — "
        "give build_tree a shape that distinguishes the two"
    )


def test_creation_order_does_not_reach_the_output(tmp_path: Path) -> None:
    """Fifty files written in opposite orders must inventory identically.

    Recorded honestly: this did **not** catch the removal of `sorted()` on
    ext4, because its directory index orders entries by a hash of the name
    rather than by insertion. It is kept as a cross-filesystem canary — HFS+
    and some network filesystems do return insertion order — and it is not the
    control. The control is the assertion above it.

    Writing this down matters more than the test does. It is the shape of
    failure this project exists to notice: a check that looks like it covers
    something, is green, and covers nothing.
    """
    names = [f"file{index:02d}.txt" for index in range(50)]
    forward = tmp_path / "forward"
    backward = tmp_path / "backward"
    forward.mkdir()
    backward.mkdir()
    for name in names:
        (forward / name).write_text("same content\n", encoding="utf-8")
    for name in reversed(names):
        (backward / name).write_text("same content\n", encoding="utf-8")

    assert inventory.walk(forward) == inventory.walk(backward)


def test_nfd_and_nfc_filenames_produce_one_identical_inventory(tmp_path: Path) -> None:
    """The divergence a single-platform CI cannot see.

    macOS hands back the decomposed form and Linux hands back whatever was
    written. Without NFC the two produce different paths, therefore different
    hashes, therefore verifications that expire for no reason months later
    (D-4) — and nothing about the failure points at Unicode.
    """
    composed = inventory.walk(build_tree(tmp_path / "nfc", NFC_NAME))
    decomposed = inventory.walk(build_tree(tmp_path / "nfd", NFD_NAME))
    assert composed == decomposed

    names = [Path(entry.path).name for entry in composed]
    assert NFC_NAME in names, "the emitted filename is not NFC"
    for name in names:
        assert unicodedata.normalize("NFC", name) == name


def test_normalisation_variants_in_one_directory_are_refused(tmp_path: Path) -> None:
    """The collision NFC normalisation creates rather than removes.

    Both names normalise to one `path`, so two distinct files become one
    record — and with equal content they derive the *same candidate id*. Under
    P4 resolving one would resolve the other, and a verification recorded
    against one file would apply to bytes nobody read. That is D-6's "a wrong
    merge silently loses a question", with a verification transferring on top.

    Refused rather than disambiguated, because APFS will not hold both variants
    in one directory: any scheme that told them apart would build an inventory
    that exists on Linux and cannot exist on macOS, trading a silent collision
    for a guaranteed divergence.

    Skipped where the filesystem folds the two together, which is the correct
    outcome there — the collision cannot arise because the second write lands
    on the first file.
    """
    root = tmp_path / "variants"
    root.mkdir()
    (root / NFC_NAME).write_text("a\n", encoding="utf-8")
    (root / NFD_NAME).write_text("b\n", encoding="utf-8")

    if len(list(root.iterdir())) == 1:
        pytest.skip("normalisation-insensitive filesystem: the two names are one file")

    with pytest.raises(inventory.NormalisationCollision) as caught:
        inventory.walk(root)
    message = str(caught.value)
    assert "normalisation" in message
    assert "Rename one" in message


def test_a_lone_variant_is_not_refused(tmp_path: Path) -> None:
    """The refusal must be about the collision, not about decomposed names.
    NFD filenames are ordinary and must inventory normally — refusing them
    would reject most trees authored on HFS+."""
    root = tmp_path / "single"
    root.mkdir()
    (root / NFD_NAME).write_text("a\n", encoding="utf-8")

    entries = inventory.walk(root)
    assert len(entries) == 1
    assert entries[0].path == NFC_NAME


def test_an_unrelated_file_changes_no_existing_entry(tmp_path: Path) -> None:
    """D-4, and the assertion an id derived from a counter passes until the
    day something is inserted ahead of it.

    The new file sorts before every existing one, so a positional identity
    shifts every entry after it while a path-derived identity does not move.
    """
    root = build_tree(tmp_path / "tree")
    before = {entry.path: entry for entry in inventory.walk(root)}

    (root / "aaa_inserted_first.txt").write_text("nothing here\n", encoding="utf-8")
    after = {entry.path: entry for entry in inventory.walk(root)}

    assert set(before) < set(after), "the added file did not appear"
    for path, entry in before.items():
        assert after[path] == entry, f"{path} changed when an unrelated file was added"


def test_crlf_and_lf_content_hash_the_same(tmp_path: Path) -> None:
    """STACK.md §5: normalise CRLF to LF *before* hashing. A checkout with
    autocrlf on must not invalidate every hash in the ledger."""
    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    (lf / "a.py").write_bytes(b"x = 1\ny = 2\n")
    (crlf / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert inventory.walk(lf)[0].sha256 == inventory.walk(crlf)[0].sha256


def test_excluded_directories_are_reported_not_dropped(tmp_path: Path) -> None:
    """STACK.md §5: exclusions are recorded, never silent. A reader cannot
    tell an empty .git/ from one that was skipped unless told."""
    root = build_tree(tmp_path / "tree")
    entries = inventory.walk(root)
    assert not [entry for entry in entries if entry.path.startswith(".git/")]
    assert ".git/" in inventory.exclusions_applied(root)


def test_binary_files_are_inventoried_but_not_hashed_as_text(tmp_path: Path) -> None:
    """NUL in the first 8 KiB, never the extension (STACK.md §5)."""
    root = build_tree(tmp_path / "tree")
    logo = next(entry for entry in inventory.walk(root) if entry.path == "logo.png")
    assert logo.is_binary


def test_symlinks_are_recorded_and_never_followed(tmp_path: Path) -> None:
    """A symlink escaping the root is a candidate in its own right (P9)."""
    root = build_tree(tmp_path / "tree")
    outside = tmp_path / "outside.txt"
    outside.write_text("elsewhere\n", encoding="utf-8")
    (root / "escape").symlink_to(outside)
    (root / "inside").symlink_to(root / "pkg" / "app.py")

    by_path = {entry.path: entry for entry in inventory.walk(root)}
    assert by_path["escape"].is_symlink
    assert by_path["escape"].escapes_root
    assert by_path["inside"].is_symlink
    assert not by_path["inside"].escapes_root


def test_output_carries_no_absolute_path(tmp_path: Path) -> None:
    """STACK.md §5: paths are relative to the target root. An absolute path in
    a deterministic output makes the hash depend on where it was checked out."""
    root = build_tree(tmp_path / "tree")
    for entry in inventory.walk(root):
        assert not entry.path.startswith("/")
        assert str(tmp_path) not in entry.path


@pytest.mark.parametrize("missing", ["nonexistent", "pkg/app.py"])
def test_walk_refuses_a_root_that_is_not_a_directory(tmp_path: Path, missing: str) -> None:
    """A check that cannot run does not return an empty result (H-1). An empty
    inventory and an unreadable target must not look the same."""
    build_tree(tmp_path / "tree")
    with pytest.raises((NotADirectoryError, FileNotFoundError)):
        inventory.walk(tmp_path / "tree" / missing)
