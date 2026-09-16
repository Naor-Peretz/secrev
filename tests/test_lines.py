"""One definition of a line for every consumer of the walk.

`str.splitlines` breaks on seven characters an editor does not treat as line
breaks, so a form feed shifted every later line number and window in both
candidate sources and the line count in `recon.json`. Found in the
TASK-M2-007 review, fixed by owner decision (TASKS_M2.md). Each consumer is
asserted here against the line an editor shows, so a source that goes back to
`splitlines` turns this file red.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secrev.catalog import load
from secrev.inventory import split_lines
from secrev.kinds import load_file
from secrev.recon import recon, to_json
from secrev.surfaces import surfaces
from secrev.sweep import sweep

ROOT = Path(__file__).resolve().parent.parent

# Written as escapes, never as the characters: several are invisible, and the
# linter rightly refuses them in source.
NOT_LINE_BREAKS = [
    "\x0b",
    "\x0c",
    "\x1c",
    "\x1d",
    "\x1e",
    "\x85",
    "\N{LINE SEPARATOR}",
    "\N{PARAGRAPH SEPARATOR}",
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("a", ["a"]),
        ("a\n", ["a"]),
        ("a\nb", ["a", "b"]),
        ("a\r\nb\r\n", ["a", "b"]),
        ("a\rb", ["a", "b"]),
        ("\n", [""]),
        ("a\n\nb", ["a", "", "b"]),
    ],
)
def test_lines_break_where_an_editor_breaks_them(text: str, expected: list[str]) -> None:
    assert split_lines(text) == expected


def test_agrees_with_splitlines_wherever_splitlines_was_right() -> None:
    text = "one\r\ntwo\rthree\nfour\n\nsix"
    assert split_lines(text) == text.splitlines()


@pytest.mark.parametrize("character", NOT_LINE_BREAKS)
def test_other_separators_stay_inside_their_line(character: str) -> None:
    assert split_lines(f"a{character}b\nc\n") == [f"a{character}b", "c"]


@pytest.mark.parametrize("character", NOT_LINE_BREAKS)
def test_a_pattern_hit_keeps_the_editors_line(tmp_path: Path, character: str) -> None:
    catalog = load(sorted((ROOT / "patterns").glob("*.yaml")))
    (tmp_path / "m.py").write_text(
        f"x = 1{character}\nresult = eval(expression)\n", encoding="utf-8"
    )
    [hit] = [hit for hit in sweep(tmp_path, catalog) if hit.rule_id == "exec.dynamic"]
    assert hit.line == 2


@pytest.mark.parametrize("character", NOT_LINE_BREAKS)
def test_a_surface_keeps_the_editors_line(tmp_path: Path, character: str) -> None:
    kinds = load_file(ROOT / "surfaces" / "_surfaces.yaml")
    (tmp_path / "SKILL.md").write_text(
        f"---\nname: x{character}\ndescription: y\n---\n", encoding="utf-8"
    )
    [hit] = surfaces(tmp_path, kinds)
    assert hit.line == 3


@pytest.mark.parametrize("character", NOT_LINE_BREAKS)
def test_the_line_count_is_the_editors(tmp_path: Path, character: str) -> None:
    (tmp_path / "notes.txt").write_text(f"a{character}b\nc\n", encoding="utf-8")
    assert json.loads(to_json(recon(tmp_path)))["inventory"]["loc_total"] == 2
