"""The surface source. BRIEF_M2.md, PRD P11, FR-3.9 to FR-3.11, TASKS_M2.md.

Written red, before `surfaces.py` exists, for the reason `test_determinism.py`
gives: a determinism check added after the generator is a retrofit onto code
composed without it, and the surface source is a third generator of ids in the
same ledger.

What a surface candidate is, stated by the assertions below rather than by the
module they constrain:

  - every declaration a kind finds becomes a record, `source: surface`,
    `status: unresolved`, whether or not any pattern matched there (P11);
  - the excerpt is the declaration line itself, because nothing matched — it
    is what makes the entry point reachable (BRIEF_M2.md §3);
  - the window is named `decl-20`: the same ±20 lines as `lines-20`, anchored
    on the declaration, under a name that says so (TASKS_M2.md C-2), so a
    surface window is never compared with a pattern window;
  - `catalog_version` carries the kinds file's `version` — the Q4 default,
    pending the owner's decision, and asserted so a change to it is visible.

The ordering assertion is the H-8 control. Files arrive sorted from
`inventory.walk`, so a two-run comparison would not catch a surface source that
emitted in kind order rather than line order; only an assertion over the order
itself does (TASK-M2-003).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from secrev.catalog import Catalog, load
from secrev.kinds import Kinds, load_file
from secrev.ledger import to_jsonl
from secrev.surfaces import surfaces
from secrev.sweep import sweep

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden" / "surfaces.jsonl"

# AC-9a: a reachable entry point no pattern matches (TASK-M2-004). Deliberately
# not under a directory called `surfaces` — that name is protected (H-4).
QUIET_SKILL = "skills/quiet/SKILL.md"

SKILL = """\
---
name: example
description: Does a thing for the user
---

Body text. description: not frontmatter, and not at column 0 of a key.
"""


@pytest.fixture(scope="module")
def kinds() -> Kinds:
    return load_file(ROOT / "surfaces" / "_surfaces.yaml")


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load(sorted((ROOT / "patterns").glob("*.yaml")))


def skill_tree(root: Path, relative: str = "SKILL.md", text: str = SKILL) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root


# --- what a record is ----------------------------------------------------


def test_a_declaration_becomes_a_surface_candidate(tmp_path: Path, kinds: Kinds) -> None:
    [hit] = surfaces(skill_tree(tmp_path), kinds)
    assert hit.source == "surface"
    assert hit.rule_id == "surface.skill_activation"
    assert hit.file == "SKILL.md"
    assert hit.line == 3
    assert hit.layer == "manifest"
    assert hit.status == "unresolved"
    assert hit.window_spec == "decl-20"
    assert hit.catalog_version == kinds.version  # Q4 default, not a decision
    assert hit.match_excerpt == "description: Does a thing for the user"


def test_the_question_is_the_kinds_question_on_one_line(tmp_path: Path, kinds: Kinds) -> None:
    [hit] = surfaces(skill_tree(tmp_path), kinds)
    [kind] = [kind for kind in kinds.kinds if kind.id == hit.rule_id]
    assert hit.question == " ".join(kind.question.split())


def test_the_excerpt_is_redacted(tmp_path: Path, kinds: Kinds) -> None:
    """G-3 applies to every source's excerpt, and a surface excerpt is a whole
    declaration line — more text than a pattern's span, so more to leak.

    The value is deliberately not credential-shaped. An earlier draft used a
    hex-looking string and the secrets stage flagged this file, which is the
    lesson `test_sweep.py` already records: committing realistic-looking
    credentials to prove a redactor works is the thing the redactor is for."""
    text = SKILL.replace("Does a thing for the user", "uses token=hunter2correcthorse for auth")
    [hit] = surfaces(skill_tree(tmp_path, text=text), kinds)
    assert "hunter2correcthorse" not in hit.match_excerpt
    assert "[REDACTED]" in hit.match_excerpt


# --- what is not a surface -----------------------------------------------


def test_a_file_the_kind_does_not_look_in_produces_nothing(tmp_path: Path, kinds: Kinds) -> None:
    """`description:` at column 0 of a README is prose, not an activation."""
    assert surfaces(skill_tree(tmp_path, "README.md"), kinds) == []


def test_an_indented_line_is_not_a_declaration(tmp_path: Path, kinds: Kinds) -> None:
    text = "---\nname: x\n  description: nested, not the skill's own key\n---\n"
    assert surfaces(skill_tree(tmp_path, text=text), kinds) == []


def test_binary_files_are_not_read(tmp_path: Path, kinds: Kinds) -> None:
    (tmp_path / "SKILL.md").write_bytes(b"description: x\n\x00\x01")
    assert surfaces(tmp_path, kinds) == []


def test_symlinks_are_not_followed(tmp_path: Path, kinds: Kinds) -> None:
    """Never followed (STACK.md §5). A symlink escaping the root is a closure
    question with no owner yet (TASKS_M2.md Q7), not a surface."""
    outside = tmp_path / "outside"
    skill_tree(outside)
    root = tmp_path / "root"
    root.mkdir()
    (root / "SKILL.md").symlink_to(outside / "SKILL.md")
    assert surfaces(root, kinds) == []


# --- determinism and identity --------------------------------------------


def test_two_runs_are_byte_identical(tmp_path: Path, kinds: Kinds) -> None:
    root = skill_tree(skill_tree(tmp_path, "a/SKILL.md"), "b/SKILL.md")
    assert to_jsonl(surfaces(root, kinds)) == to_jsonl(surfaces(root, kinds))


def test_ids_survive_an_unrelated_file(tmp_path: Path, kinds: Kinds) -> None:
    """D-4. An identity derived from a traversal counter looks right until
    something is inserted ahead of it — here both an inert file and another
    skill sorted before this one."""
    root = skill_tree(tmp_path, "skills/b/SKILL.md")
    before = {hit.file: hit.id for hit in surfaces(root, kinds)}
    (root / "aaa_unrelated.txt").write_text("nothing here\n", encoding="utf-8")
    skill_tree(root, "skills/a/SKILL.md")
    after = {hit.file: hit.id for hit in surfaces(root, kinds)}
    assert after["skills/b/SKILL.md"] == before["skills/b/SKILL.md"]


def test_nfd_and_nfc_directory_names_give_one_id(tmp_path: Path, kinds: Kinds) -> None:
    composed = unicodedata.normalize("NFC", "café")
    decomposed = unicodedata.normalize("NFD", "café")
    nfc = surfaces(skill_tree(tmp_path / "nfc", f"{composed}/SKILL.md"), kinds)
    nfd = surfaces(skill_tree(tmp_path / "nfd", f"{decomposed}/SKILL.md"), kinds)
    assert [hit.id for hit in nfc] == [hit.id for hit in nfd]
    assert nfd[0].file == f"{composed}/SKILL.md"


def test_order_within_a_file_is_by_line_then_kind(tmp_path: Path) -> None:
    """The H-8 control for TASK-M2-003. Two kinds whose declarations
    interleave: emitting kind by kind gives (2, alpha), (1, beta), (3, beta);
    the total order is by line, then rule id. Removing the within-file sort
    from `surfaces.py` must turn this red."""
    kinds_file = tmp_path / "kinds.yaml"
    kinds_file.write_text(
        'version: "0000.00.0"\n'
        "kinds:\n"
        "  - {id: surface.beta, layer: [code], precision: low, files: ['*.txt'],"
        " declaration: '^b:', question: 'B?'}\n"
        "  - {id: surface.alpha, layer: [code], precision: low, files: ['*.txt'],"
        " declaration: '^a:', question: 'A?'}\n",
        encoding="utf-8",
    )
    root = tmp_path / "tree"
    root.mkdir()
    (root / "entry.txt").write_text("b: 1\na: 2\nb: 3\n", encoding="utf-8")
    hits = surfaces(root, load_file(kinds_file))
    assert [(hit.line, hit.rule_id) for hit in hits] == [
        (1, "surface.beta"),
        (2, "surface.alpha"),
        (3, "surface.beta"),
    ]


def test_surface_and_pattern_rule_ids_are_disjoint(kinds: Kinds, catalog: Catalog) -> None:
    """One ledger, two sources: a shared `rule_id` would be two questions under
    one name. The loaders enforce the namespace; this asserts the shipped data."""
    assert not {kind.id for kind in kinds.kinds} & {pattern.id for pattern in catalog.patterns}


# --- the fixture tree: AC-9a and the golden --------------------------------


def test_an_entry_point_no_pattern_matches_is_still_a_candidate(
    kinds: Kinds, catalog: Catalog
) -> None:
    """AC-9a, both halves, asserted rather than eyeballed. If a later pattern
    happens to match this file the first half fails, which is the point: the
    candidate must come from reachability, not from a coincidence of
    vocabulary (BRIEF_M2.md §1)."""
    assert not [hit for hit in sweep(FIXTURES, catalog) if hit.file == QUIET_SKILL]
    assert [hit for hit in surfaces(FIXTURES, kinds) if hit.file == QUIET_SKILL]


def test_matches_the_golden_byte_for_byte(kinds: Kinds) -> None:
    assert to_jsonl(surfaces(FIXTURES, kinds)) == GOLDEN.read_text(encoding="utf-8")
