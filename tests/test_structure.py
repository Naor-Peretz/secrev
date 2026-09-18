"""The structural source. `BRIEF_M4.md` §4, PRD FR-3.5 to FR-3.8, NFR-3, NFR-6.

Fixtures live in `tests/fixtures/structural/`, not in `tests/fixtures/rules/`.
Two reasons, and both are about a guard rather than about taste.
`test_patterns.py` asserts fixture coverage **in both directions**, so a
directory under `rules/` naming no *pattern* fails it — structural ids would
break a test that is right to be strict. And the directory is not named
`structure`, because M4 made that a protected name: a fixture tree spelled that
way reads to `bash-guard.sh` as the rule data itself.

The coverage assertion is repeated here rather than shared, in both directions
for the same reason it exists there: a rule with no fixtures is a rule nobody
demonstrated, and a fixture directory naming no rule is what an id rename leaves
behind.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from secrev.catalog import CatalogError
from secrev.catalog import load as load_catalog
from secrev.ledger import BLOCK_WINDOW_SPEC, Hit, to_jsonl
from secrev.parser import PythonParser
from secrev.structure import SHAPES, structure
from secrev.structure_rules import (
    ShapeSpec,
    StructureRuleError,
    StructureRules,
    load_file,
    validate_shape_specs,
)

ROOT = Path(__file__).resolve().parent.parent
RULE_FILE = ROOT / "structure" / "_structure.yaml"
FIXTURES = ROOT / "tests" / "fixtures"
STRUCTURAL = FIXTURES / "structural"
GOLDEN = ROOT / "tests" / "golden" / "structure.jsonl"


@pytest.fixture(scope="module")
def rules() -> StructureRules:
    return load_file(RULE_FILE, SHAPES)


def rule_ids(rules: StructureRules) -> list[str]:
    return [rule.id for rule in rules.rules]


def hits_for(rules: StructureRules, directory: Path) -> list[Hit]:
    return structure(directory, rules).hits


# --- the golden ----------------------------------------------------------


def test_matches_the_golden_byte_for_byte(rules: StructureRules) -> None:
    """`read_bytes`: see the note in `tests/test_recon.py`. This golden was
    written after the source, which is the wrong order — the determinism
    decisions that precede it (`is_nfr3_path`, the parser's ordering, the window
    spec) are the ones §5 requires first, and those did come first."""
    assert to_jsonl(structure(FIXTURES, rules).hits).encode("utf-8") == GOLDEN.read_bytes()


def test_the_golden_covers_the_whole_fixture_tree(rules: StructureRules) -> None:
    """The golden is over `fixtures/`, not over `fixtures/structural/`.

    Worth an assertion of its own: a golden restricted to the structural
    fixtures would compare the source against files written to make it fire,
    and would say nothing about the tree it is actually run over. Three of the
    ten records come from files written for other sources entirely.
    """
    produced = structure(FIXTURES, rules).hits
    outside = {hit.file for hit in produced if not hit.file.startswith("structural/")}
    assert outside, "the golden only covers files written to make these rules fire"


def test_the_tool_does_not_contain_the_shape_it_asks_about(rules: StructureRules) -> None:
    """AC-10, and it is not decoration here: F1 found this exact shape in
    `cli.py` on the milestone that shipped the rule.

    `_prepare` created the workspace with `mkdir(parents=True, exist_ok=True)`
    and then walked it setting `0o700`. Between the two calls every level stood
    at whatever the umask gave — 0o775 on the machine M3.5 measured — while the
    directory is the one holding `match_excerpt` values, the single field G-3
    spends its effort making safe to write down. M3.5's E4 fixed the mode those
    directories *end up* with and left the window they pass through, and the
    comment explaining the walk was written while looking straight at it.

    The fix is the fused form the rule's own negative fixture demonstrates:
    `mode=` at creation, which umask can only clear bits from and 0o700 has
    none to clear. Asserted over `src/` rather than fixed once, because a rule
    this tool ships and then contains is the credibility failure AC-10 names.
    """
    produced = structure(ROOT / "src", rules).hits
    offenders = [
        f"{hit.file}:{hit.line}"
        for hit in produced
        if hit.rule_id == "structure.permission_after_creation"
    ]
    assert not offenders, f"the tool contains the shape it asks about: {offenders}"


# --- A1: every rule is demonstrated, in both directions ------------------


def test_every_rule_has_both_fixtures(rules: StructureRules) -> None:
    missing = [
        f"{rule.id}/{kind}.py"
        for rule in rules.rules
        for kind in ("positive", "negative")
        if not (STRUCTURAL / rule.id / f"{kind}.py").is_file()
    ]
    assert not missing, f"rules with no demonstration: {missing}"


def test_every_fixture_directory_names_a_rule(rules: StructureRules) -> None:
    """The other direction, which is what an id rename leaves behind: fixtures
    that still pass while demonstrating a rule that no longer exists."""
    known = set(rule_ids(rules))
    orphans = sorted(
        directory.name for directory in STRUCTURAL.iterdir() if directory.name not in known
    )
    assert not orphans, f"fixture directories naming no rule: {orphans}"


@pytest.mark.parametrize(
    "rule_id",
    [
        "structure." + name
        for name in (
            "permission_after_creation",
            "denylist_decision",
            "unvalidated_path_reach",
            "built_value_into_sink",
        )
    ],
)
def test_the_positive_fixture_produces_its_rule(rules: StructureRules, rule_id: str) -> None:
    produced = hits_for(rules, STRUCTURAL / rule_id)
    assert rule_id in {hit.rule_id for hit in produced if hit.file.startswith("positive")}, (
        f"{rule_id} did not fire on its own positive fixture"
    )


@pytest.mark.parametrize(
    "rule_id",
    [
        "structure." + name
        for name in (
            "permission_after_creation",
            "denylist_decision",
            "unvalidated_path_reach",
            "built_value_into_sink",
        )
    ],
)
def test_the_negative_fixture_does_not(rules: StructureRules, rule_id: str) -> None:
    """A2. Each negative is the rule's nearest neighbour, not an unrelated file:
    the fused create, the reversed membership, the validator in the argument,
    the literal command. A negative that simply removed the sink would pass
    without the rule's actual decision ever running."""
    produced = hits_for(rules, STRUCTURAL / rule_id)
    offenders = [
        hit for hit in produced if hit.file.startswith("negative") and hit.rule_id == rule_id
    ]
    assert not offenders, (
        f"{rule_id} fired on its negative fixture at line(s) {[h.line for h in offenders]}"
    )


# --- A3: a rule is a question --------------------------------------------


def test_every_question_reads_as_one(rules: StructureRules) -> None:
    """FR-3.2. A rule whose `question` can be answered from the record alone is
    misfiled — it has concluded, and concluding is a later phase's job."""
    for rule in rules.rules:
        assert rule.question.strip().endswith("?"), f"{rule.id}: question does not ask anything"


def test_no_record_concludes(rules: StructureRules) -> None:
    produced = hits_for(rules, STRUCTURAL)
    assert produced, "the fixture tree produced nothing — this test would pass vacuously"
    assert {hit.status for hit in produced} == {"unresolved"}


def test_records_carry_the_structural_source_and_window(rules: StructureRules) -> None:
    """D1 and D3. `block-20` is the name STACK.md §5 has held since M1, not a
    new one invented here (BRIEF_M4.md §6 Q2)."""
    produced = hits_for(rules, STRUCTURAL)
    assert {hit.source for hit in produced} == {"structure"}
    assert {hit.window_spec for hit in produced} == {BLOCK_WINDOW_SPEC}


def test_records_carry_the_rule_files_version(rules: StructureRules) -> None:
    produced = hits_for(rules, STRUCTURAL)
    assert {hit.catalog_version for hit in produced} == {rules.version}


# --- B1: a fifth rule of an existing shape is a data edit ----------------


def test_a_fifth_rule_of_an_existing_shape_needs_no_python(
    rules: StructureRules, tmp_path: Path
) -> None:
    """NFR-6's test, and the one that matters. The `shape` field exists for
    this: if the loader knew the parameters per *rule id*, this would need an
    entry in Python and the requirement would be met in name only.

    Written against the loader rather than against a committed extra rule, so
    the assertion is about the mechanism and not about a rule we would then have
    to keep.
    """
    extra = RULE_FILE.read_text(encoding="utf-8") + (
        "\n"
        "  - id: structure.secrets_into_sink\n"
        "    shape: sink_adjacency\n"
        "    layer: [code]\n"
        "    precision: low\n"
        "    question: >\n"
        "      Does a built value reach a logger here, and what is in it?\n"
        "    parameters:\n"
        "      dangerous_calls: [logging.info, logger.warning]\n"
    )
    path = tmp_path / "_structure.yaml"
    path.write_text(extra, encoding="utf-8")
    loaded = load_file(path, SHAPES)
    assert "structure.secrets_into_sink" in rule_ids(loaded)
    assert len(loaded.rules) == len(rules.rules) + 1


# --- B2: the loader refuses, and names the rule --------------------------


def load_text(tmp_path: Path, body: str) -> StructureRules:
    path = tmp_path / "_structure.yaml"
    path.write_text(body, encoding="utf-8")
    return load_file(path, SHAPES)


VALID = (
    'version: "2026.09.1"\n'
    "rules:\n"
    "  - id: structure.example\n"
    "    shape: sink_adjacency\n"
    "    layer: [code]\n"
    "    precision: low\n"
    "    question: What reaches this call?\n"
    "    parameters:\n"
    "      dangerous_calls: [os.system]\n"
)


def test_the_valid_rule_file_still_loads(tmp_path: Path) -> None:
    """The control. Every refusal below is worth nothing if the shape they are
    built from does not itself pass."""
    assert rule_ids(load_text(tmp_path, VALID)) == ["structure.example"]


def test_a_misspelled_parameter_is_refused_and_the_rule_is_named(tmp_path: Path) -> None:
    """The dangerous case, and the reason the check runs in both directions. A
    missing parameter raises in the analysis and someone notices; an unknown one
    leaves the analysis reading a parameter that is not there — a structural
    check that stops firing while the gate stays green."""
    broken = VALID.replace("dangerous_calls:", "dangerus_calls:")
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, broken)
    assert "structure.example" in str(failure.value)
    assert "dangerus_calls" in str(failure.value)


def test_an_unknown_shape_is_refused_with_the_limit_stated(tmp_path: Path) -> None:
    broken = VALID.replace("shape: sink_adjacency", "shape: taint_flow")
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, broken)
    assert "taint_flow" in str(failure.value)


def test_a_rule_outside_the_namespace_is_refused(tmp_path: Path) -> None:
    broken = VALID.replace("structure.example", "exec.dynamic")
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, broken)
    assert "exec.dynamic" in str(failure.value)


def test_a_regex_field_is_refused_by_name(tmp_path: Path) -> None:
    """D-11 at the schema. A rule wanting a regex is a pattern, and the message
    says where it belongs rather than only that the field is unknown."""
    broken = VALID.replace("    parameters:", "    regex: os\\.system\n    parameters:")
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, broken)
    assert "regex" in str(failure.value)


def test_a_boolean_threshold_is_refused(tmp_path: Path) -> None:
    """`True` is an `int` in Python, so a YAML `true` would arrive as the
    threshold 1 and the rule would fire on everything. The loader tests `bool`
    before `int` for exactly this."""
    body = VALID.replace("shape: sink_adjacency", "shape: decision_shape").replace(
        "      dangerous_calls: [os.system]\n",
        "      minimum_alternatives: true\n      validating_name_fragments: [is_]\n",
    )
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, body)
    assert "minimum_alternatives" in str(failure.value)


def test_a_duplicate_id_is_refused(tmp_path: Path) -> None:
    doubled = VALID + VALID.split("rules:\n")[1]
    with pytest.raises(StructureRuleError) as failure:
        load_text(tmp_path, doubled)
    assert "duplicate" in str(failure.value)


def test_a_file_without_a_version_is_refused(tmp_path: Path) -> None:
    with pytest.raises(StructureRuleError):
        load_text(tmp_path, VALID.split("\n", 1)[1])


def test_a_shape_spec_with_an_unknown_parameter_type_is_refused() -> None:
    """The specs are validated too. A typo'd *type* — `name` for `names` — would
    send a good list down the count branch and report a data error in a file
    that is correct."""
    with pytest.raises(StructureRuleError):
        validate_shape_specs({"x": ShapeSpec(name="x", parameters={"y": "name"})})


def test_the_shipped_shape_specs_are_valid() -> None:
    validate_shape_specs(SHAPES)


# --- B3: the namespace is closed from both sides -------------------------


def test_the_catalog_refuses_the_structural_namespace(tmp_path: Path) -> None:
    """B3, and it was open until this test asked.

    `catalog.py` named `surface` inline from M2, so when the structural source
    arrived its namespace was unreserved and a pattern could have taken a
    `structure.` id — two different questions under one `rule_id` in one ledger,
    with nothing red. The reservation now reads from
    `ledger.RESERVED_NAMESPACES`, so the next source is closed by adding one
    name in one place rather than by someone remembering this.

    Written into `tmp_path`, not into the fixture tree: a probe left in
    `tests/fixtures/structural/` would be a directory naming no rule, which the
    coverage assertion above is right to fail on.
    """
    pack = tmp_path / "probe.yaml"
    pack.write_text(
        'version: "1"\npatterns:\n'
        "  - id: structure.example\n"
        "    layer: [code]\n"
        "    regex: x\n"
        "    default_severity_hint: low\n"
        "    precision: low\n"
        "    question: What?\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError) as failure:
        load_catalog([pack])
    assert "structure" in str(failure.value)


# --- C1: determinism ------------------------------------------------------


def test_two_runs_agree(rules: StructureRules) -> None:
    assert hits_for(rules, STRUCTURAL) == hits_for(rules, STRUCTURAL)


def test_adding_an_unrelated_file_moves_no_id(rules: StructureRules, tmp_path: Path) -> None:
    """NFR-3's second half, and the one a single-run comparison cannot see."""
    tree = tmp_path / "tree"
    shutil.copytree(STRUCTURAL, tree)
    before = [hit.id for hit in structure(tree, rules).hits]
    (tree / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    after = [hit.id for hit in structure(tree, rules).hits]
    assert before == [identifier for identifier in after if identifier in set(before)]
    assert set(before) <= set(after)


def test_records_are_ordered_by_line_then_rule(rules: StructureRules) -> None:
    """The order has to be total before ids are assigned: the ordinal counts
    over byte-identical windows, and two candidates in one body share a window
    by construction rather than by coincidence."""
    produced = hits_for(rules, STRUCTURAL)
    by_file: dict[str, list[tuple[int, str]]] = {}
    for hit in produced:
        by_file.setdefault(hit.file, []).append((hit.line, hit.rule_id))
    for path, entries in by_file.items():
        assert entries == sorted(entries), f"{path} is not in (line, rule_id) order"


# --- the parse failure contract ------------------------------------------


def test_a_file_that_does_not_parse_is_recorded_and_the_run_continues(
    rules: StructureRules, tmp_path: Path
) -> None:
    """H-1 at the level of a run. A hostile or merely broken file must not be
    able to end the review — that was M3.5's whole subject — and it must not
    pass for a clean one either."""
    (tmp_path / "broken.py").write_text("def f(\n", encoding="utf-8")
    (tmp_path / "fine.py").write_text(
        "import os\n\n\ndef run(name):\n    os.system('x ' + name)\n", encoding="utf-8"
    )
    result = structure(tmp_path, rules)
    assert result.unparsed == ["broken.py"]
    # Two records from one line, and that is D-6 rather than a defect:
    # `os.system` is named by `sink_calls` and by `dangerous_calls` alike, so
    # the line raises two different questions and earns two answers. Merging
    # them would be deduplicating by location, which D-6 forbids.
    assert {hit.file for hit in result.hits} == {"fine.py"}
    assert sorted(hit.rule_id for hit in result.hits) == [
        "structure.built_value_into_sink",
        "structure.unvalidated_path_reach",
    ]


def test_nothing_unparsed_is_an_empty_list_and_not_a_missing_field(
    rules: StructureRules, tmp_path: Path
) -> None:
    (tmp_path / "fine.py").write_text("x = 1\n", encoding="utf-8")
    assert structure(tmp_path, rules).unparsed == []


def test_a_second_parser_would_change_no_rule(rules: StructureRules, tmp_path: Path) -> None:
    """STACK.md §7's requirement, exercised rather than asserted.

    The four analyses read a vocabulary, so a `Parser` that claims a different
    extension and produces the same shapes is all a second language costs. If
    any rule reached for an `ast` node this would not compile, let alone pass.
    """

    class DotPyish(PythonParser):
        language = "pyish"

        def applies(self, relative_path: str) -> bool:
            return relative_path.endswith(".pyish")

    (tmp_path / "a.pyish").write_text(
        "import os\n\n\ndef run(name):\n    os.system('x ' + name)\n", encoding="utf-8"
    )
    result = structure(tmp_path, rules, parser=DotPyish())
    assert sorted(hit.rule_id for hit in result.hits) == [
        "structure.built_value_into_sink",
        "structure.unvalidated_path_reach",
    ]
    assert {hit.file for hit in result.hits} == {"a.pyish"}


def test_the_module_scope_is_reviewed_like_any_other_body(
    rules: StructureRules, tmp_path: Path
) -> None:
    """FR-3.7 scopes the rules to a function body. Read strictly that exempts
    every top-level script, which is most of what an agentic artifact is."""
    (tmp_path / "script.py").write_text(
        "import os\n\nname = 'x'\nos.system('run ' + name)\n", encoding="utf-8"
    )
    result = structure(tmp_path, rules)
    assert [hit.rule_id for hit in result.hits] == ["structure.built_value_into_sink"]


def test_an_unreadable_parser_is_not_silently_skipped(
    rules: StructureRules, tmp_path: Path
) -> None:
    """A file the parser does not claim is not a candidate-free file; it is a
    file of another language, and E1 makes that a coverage gap in `recon.json`
    rather than silence here."""
    (tmp_path / "a.js").write_text("const x = 1;\n", encoding="utf-8")
    result = structure(tmp_path, rules)
    assert result.hits == [] and result.unparsed == []
