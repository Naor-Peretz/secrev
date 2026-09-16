"""Surface-kind loading and strict validation. TASKS_M2.md C-1, PRD NFR-6.

Mirrors `test_catalog.py`, and for the same reason the weight is in the
refusals. A kind that loads with a misspelled field is a class of entry point
that silently stops being enumerated, and under P11 that is the review's scope
shrinking with nothing reporting it. So each refusal asserts that the message
names the kind: "invalid surface kinds" sends a reader to a file with no
starting point.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from secrev.catalog import CatalogError
from secrev.catalog import load_file as load_catalog
from secrev.inventory import glob_to_regex
from secrev.kinds import SurfaceKindError, load_file

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = ROOT / "surfaces" / "_surfaces.yaml"

VALID = """\
version: "2026.09.1"
kinds:
  - id: surface.skill_activation
    layer: [manifest]
    precision: high
    files: ["**/SKILL.md"]
    declaration: '^description:\\s*\\S'
    question: Under what requests does this load the skill?
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "kinds.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_kinds_load(tmp_path: Path) -> None:
    kinds = load_file(write(tmp_path, VALID))
    assert kinds.version == "2026.09.1"
    [kind] = kinds.kinds
    assert kind.id == "surface.skill_activation"
    assert kind.layer == "manifest"
    assert kind.precision == "high"
    assert kind.files == ("**/SKILL.md",)


def test_kind_files_ignore_case(tmp_path: Path) -> None:
    [kind] = load_file(write(tmp_path, VALID)).kinds
    assert kind.applies("skills/x/SKILL.md")
    assert kind.applies("skills/x/skill.md")
    assert kind.applies("Skills/X/Skill.MD")
    # Unicode folding comes with IGNORECASE: the long s matches `s`. Pinned so
    # the behaviour is a decision, not a surprise; it only adds candidates.
    assert kind.applies("skills/x/\N{LATIN SMALL LETTER LONG S}kill.md")


def test_the_shared_glob_stays_case_sensitive() -> None:
    """Only a kind ignores case. `glob_to_regex` also serves the catalog's
    `paths_exclude`, where ignoring case would exclude more files from review
    — failing open. This holds the boundary where `kinds.py` draws it."""
    assert glob_to_regex("tests/**").match("TESTS/x.py") is None
    assert glob_to_regex("tests/**").match("tests/x.py") is not None


def test_the_shipped_kinds_load() -> None:
    """The file the surface source will read is valid, and every id is in the
    reserved namespace. A shipped file that fails to load would turn every
    `secrev surfaces` run into exit 2."""
    kinds = load_file(SHIPPED)
    assert kinds.kinds
    assert all(kind.id.startswith("surface.") for kind in kinds.kinds)


def test_declaration_is_compiled_at_load(tmp_path: Path) -> None:
    [kind] = load_file(write(tmp_path, VALID)).kinds
    assert isinstance(kind.declaration, re.Pattern)
    assert kind.declaration.search("description: does a thing")
    assert not kind.declaration.search("  description: indented, so not frontmatter")


def test_files_use_the_project_glob_semantics(tmp_path: Path) -> None:
    """`**/` is any number of leading segments including none — the semantics
    `glob_to_regex` fixes for the catalog too, so a kind and a pattern cannot
    read the same glob differently."""
    [kind] = load_file(write(tmp_path, VALID)).kinds
    assert kind.applies("SKILL.md")
    assert kind.applies("skills/review/SKILL.md")
    assert not kind.applies("skills/review/NOTSKILL.md")
    assert not kind.applies("README.md")


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("    precision: high\n", "    precision: high\n    colour: red\n", "unknown field"),
        (
            "    question: Under what requests does this load the skill?\n",
            "",
            "missing required",
        ),
        ("layer: [manifest]", "layer: [manifest, code]", "exactly one"),
        ("layer: [manifest]", "layer: [prose]", "not one of"),
        ("precision: high", "precision: certain", "precision"),
        ('files: ["**/SKILL.md"]', "files: []", "at least one"),
        ("'^description:\\s*\\S'", "'('", "does not compile"),
        ("    precision: high\n", "    precision: high\n    flags: [s]\n", "permitted subset"),
        ("    precision: high\n", "    precision: high\n    multiline: true\n", "line-oriented"),
    ],
)
def test_malformed_kinds_are_refused_and_name_the_kind(
    tmp_path: Path, old: str, new: str, fragment: str
) -> None:
    text = VALID.replace(old, new)
    assert text != VALID, "the fixture replacement matched nothing"
    with pytest.raises(SurfaceKindError) as caught:
        load_file(write(tmp_path, text))
    message = str(caught.value)
    assert fragment in message
    assert "surface.skill_activation" in message


@pytest.mark.parametrize("bad_id", ["skill.activation", "surface.Skill", "surface", "surface.a.b"])
def test_an_id_outside_the_namespace_is_refused(tmp_path: Path, bad_id: str) -> None:
    text = VALID.replace("id: surface.skill_activation", f"id: {bad_id}")
    with pytest.raises(SurfaceKindError) as caught:
        load_file(write(tmp_path, text))
    assert bad_id in str(caught.value)


def test_a_duplicate_kind_is_refused(tmp_path: Path) -> None:
    text = VALID + VALID.split("kinds:\n", 1)[1]
    with pytest.raises(SurfaceKindError) as caught:
        load_file(write(tmp_path, text))
    assert "duplicate" in str(caught.value)


def test_a_missing_version_is_refused(tmp_path: Path) -> None:
    text = VALID.replace('version: "2026.09.1"\n', "")
    with pytest.raises(SurfaceKindError) as caught:
        load_file(write(tmp_path, text))
    assert "version" in str(caught.value)


def test_a_tagged_document_is_refused_not_acted_on(tmp_path: Path) -> None:
    """`safe_load` refuses the tag rather than constructing the object, so the
    error is a YAML error that names it. The unsafe loader would have run it."""
    text = 'version: "2026.09.1"\nkinds: !!python/object/apply:os.system ["true"]\n'
    with pytest.raises(SurfaceKindError) as caught:
        load_file(write(tmp_path, text))
    assert "not valid YAML" in str(caught.value)
    assert "python/object/apply" in str(caught.value)


def test_kinds_are_sorted_by_id(tmp_path: Path) -> None:
    """NFR-3: the order entries are written in must not decide ledger order."""
    zeta = VALID.split("kinds:\n", 1)[1].replace("surface.skill_activation", "surface.zeta")
    alpha = zeta.replace("surface.zeta", "surface.alpha")
    text = 'version: "2026.09.1"\nkinds:\n' + zeta + alpha
    kinds = load_file(write(tmp_path, text))
    assert [kind.id for kind in kinds.kinds] == ["surface.alpha", "surface.zeta"]


def test_a_kind_error_is_a_usage_error() -> None:
    """`cli.py` reports `ValueError` as exit 2. A bad kinds file is bad input,
    not a broken tool (STACK.md §3), so it must land there and not at exit 3."""
    assert issubclass(SurfaceKindError, ValueError)


def test_a_pattern_cannot_take_a_surface_id(tmp_path: Path) -> None:
    """The other half of the namespace. Without it a catalog pattern could be
    named `surface.x` and share a `rule_id` with surface records."""
    text = """\
version: "2026.09.1"
patterns:
  - id: surface.lookalike
    layer: [code]
    regex: 'nothing'
    precision: low
    question: A pattern pretending to be a surface kind?
    default_severity_hint: low
"""
    path = tmp_path / "cat.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CatalogError) as caught:
        load_catalog(path)
    assert "surface.lookalike" in str(caught.value)
    assert "reserved" in str(caught.value)
