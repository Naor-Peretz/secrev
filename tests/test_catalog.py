"""Catalog loading and strict validation. BRIEF_M1.md §4.

Written before `catalog.py`, and red against a missing module.

The weight of this file is in the rejections, not the acceptance. §4's reason
is that "a silently ignored typo in a pattern file is a missing check that
nobody sees" — a catalog that loads with a misspelled field is worse than one
that fails, because the check it was supposed to add is simply absent and the
run still reports success. So every assertion below that matters asserts a
refusal, and asserts that the refusal *names the pattern id*: an error that
says "invalid catalog" sends a reader to a 200-entry file with no starting
point.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from secrev.catalog import ALLOWED_FLAGS, CatalogError, load, load_file

VALID = """\
version: "2026.08.1"
patterns:
  - id: exec.shell_true
    layer: [code]
    languages: [python]
    regex: 'subprocess\\.[a-zA-Z_]+\\([^)]*shell\\s*=\\s*True'
    flags: [i]
    precision: high
    question: Where does the command string originate?
    default_severity_hint: high
    owasp: ASI-02
    references: ["CWE-78"]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "cat.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_catalog_loads(tmp_path: Path) -> None:
    catalog = load_file(write(tmp_path, VALID))
    # `versions` is per pack since M5, and the version travels onto the pattern
    # so the record it produces can carry it. See `Pattern.pack_version`.
    assert catalog.versions == (("cat.yaml", "2026.08.1"),)
    assert len(catalog.patterns) == 1

    pattern = catalog.patterns[0]
    assert pattern.pack_version == "2026.08.1"
    assert pattern.id == "exec.shell_true"
    assert pattern.layer == ("code",)
    assert pattern.languages == ("python",)
    assert pattern.precision == "high"
    assert pattern.default_severity_hint == "high"
    assert pattern.owasp == "ASI-02"
    assert pattern.references == ("CWE-78",)


def test_regex_is_compiled_at_load_not_at_match(tmp_path: Path) -> None:
    """A malformed regex is a catalog error, not a crash partway through a
    sweep. Compiling at load is what makes the exit-2 contract reachable."""
    pattern = load_file(write(tmp_path, VALID)).patterns[0]
    assert isinstance(pattern.regex, re.Pattern)
    assert pattern.regex.search("subprocess.run(cmd, shell=True)")


def test_flags_reach_the_engine_as_flags_not_as_text(tmp_path: Path) -> None:
    text = VALID.replace("flags: [i]", "flags: [i]")
    pattern = load_file(write(tmp_path, text)).patterns[0]
    assert pattern.regex.flags & re.IGNORECASE

    without = load_file(write(tmp_path, VALID.replace("    flags: [i]\n", ""))).patterns[0]
    assert not without.regex.flags & re.IGNORECASE


def test_line_oriented_only_no_dotall_or_multiline(tmp_path: Path) -> None:
    """§4: line-oriented matching only in M1. Neither flag may be set, however
    the pattern was written — anything needing cross-line reasoning is a
    structural rule by definition."""
    pattern = load_file(write(tmp_path, VALID)).patterns[0]
    assert not pattern.regex.flags & re.DOTALL
    assert not pattern.regex.flags & re.MULTILINE


# --- refusals ------------------------------------------------------------
# Each of these asserts two things: that it fails at all, and that the message
# names the offending pattern id.


def test_unknown_key_is_rejected_and_names_the_id(tmp_path: Path) -> None:
    text = VALID.replace("    precision: high", "    precisoin: high\n    precision: high")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "precisoin" in str(caught.value)


def test_multiline_field_is_rejected_by_name(tmp_path: Path) -> None:
    """§4 forbids a `multiline` field "for later" — an unused field invites
    misuse. Unknown-key rejection would catch it anyway; this asserts the
    message says why, because someone adding it is acting on a belief that
    needs correcting rather than a typo that needs pointing at."""
    text = VALID.replace("    precision: high", "    multiline: true\n    precision: high")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "multiline" in str(caught.value)


def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    text = VALID.replace("    question: Where does the command string originate?\n", "")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "question" in str(caught.value)


def test_flag_outside_the_fixed_subset_is_rejected(tmp_path: Path) -> None:
    """§4: `flags` accepts only a fixed subset, never arbitrary passthrough."""
    text = VALID.replace("flags: [i]", "flags: [zzz]")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "zzz" in str(caught.value)


def test_flag_subset_is_small_and_deliberate() -> None:
    """Guards the subset itself. Widening it is a §4 decision, not a
    convenience — `s` or `m` would make a line-oriented rule cross lines."""
    assert sorted(ALLOWED_FLAGS) == ["i"]


def test_layer_must_be_a_list_even_with_one_element(tmp_path: Path) -> None:
    text = VALID.replace("layer: [code]", "layer: code")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "layer" in str(caught.value)


def test_multi_layer_is_refused_in_m1_rather_than_silently_flattened(tmp_path: Path) -> None:
    """§4, owner decision: §5's record carries `layer` as a scalar, so a
    two-layer pattern has no defined ledger representation. Refusing names the
    gap; accepting would emit one of the two layers and lose the other with no
    trace."""
    text = VALID.replace("layer: [code]", "layer: [code, instruction]")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)
    assert "undecided" in str(caught.value).lower()


def test_unknown_layer_value_is_rejected(tmp_path: Path) -> None:
    text = VALID.replace("layer: [code]", "layer: [prose]")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)


def test_unknown_precision_is_rejected(tmp_path: Path) -> None:
    text = VALID.replace("precision: high", "precision: certain")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)


def test_precision_low_is_accepted_as_an_ordinary_value(tmp_path: Path) -> None:
    """§4: `precision: low` is first-class and expected, not an admission of
    failure. Asserted so nobody "fixes" it into a warning."""
    text = VALID.replace("precision: high", "precision: low")
    assert load_file(write(tmp_path, text)).patterns[0].precision == "low"


def test_uncompilable_regex_is_rejected_and_names_the_id(tmp_path: Path) -> None:
    text = VALID.replace("regex: 'subprocess\\.[a-zA-Z_]+\\([^)]*shell\\s*=\\s*True'", "regex: '('")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)


def test_id_must_be_namespaced(tmp_path: Path) -> None:
    """§4: `id` is `namespace.name` — the hierarchy has to hold at 200
    patterns, and it cannot be imposed retroactively."""
    text = VALID.replace("id: exec.shell_true", "id: shelltrue")
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "shelltrue" in str(caught.value)


def test_duplicate_id_is_rejected(tmp_path: Path) -> None:
    """Two patterns sharing an id collapse two questions into one, and D-6 is
    explicit that two questions earn two answers."""
    text = VALID + VALID.split("patterns:\n")[1]
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "exec.shell_true" in str(caught.value)


def test_missing_version_is_rejected(tmp_path: Path) -> None:
    """FR-3.12: every run records the catalog version it ran under, and that is
    what makes FR-4.6 invalidation possible. A catalog with no version silently
    disables it."""
    text = VALID.replace('version: "2026.08.1"\n', "")
    with pytest.raises(CatalogError):
        load_file(write(tmp_path, text))


def test_empty_pattern_list_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CatalogError):
        load_file(write(tmp_path, 'version: "2026.08.1"\npatterns: []\n'))


def test_missing_file_is_a_catalog_error_not_an_oserror(tmp_path: Path) -> None:
    """The CLI turns CatalogError into exit 2 (a configuration error). An
    OSError escaping here would surface as exit 3, internal error, which says
    the tool broke when in fact the argument was wrong."""
    with pytest.raises(CatalogError):
        load_file(tmp_path / "absent.yaml")


def test_yaml_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(CatalogError):
        load_file(write(tmp_path, "- just\n- a\n- list\n"))


def test_load_does_not_execute_yaml_tags(tmp_path: Path) -> None:
    """STACK.md §2.1: the safe loader only. A scanner that flags the unsafe one
    and then calls it is not credible, and this is the file that would do it.

    The assertion is on *which layer* refused, and that is the entire point of
    it. An earlier version of this test asserted only that a `CatalogError` was
    raised, which it would have been either way: under an unsafe loader the tag
    below evaluates to `0`, and the schema check then rejects `patterns` for
    not being a non-empty list. The test would have passed against precisely
    the defect it was written to catch. Only the refusal happening at the YAML
    layer distinguishes the two, so that is what is asserted.
    """
    text = 'version: "2026.08.1"\npatterns: !!python/object/apply:os.system ["true"]\n'
    with pytest.raises(CatalogError) as caught:
        load_file(write(tmp_path, text))
    assert "not valid YAML" in str(caught.value)
    assert "python/object/apply" in str(caught.value)


# --- per-pack versions (M5, owner decision 2026-10-07) -------------------


def pack(tmp_path: Path, name: str, version: str, layer: str, rule_id: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / name
    path.write_text(
        f'version: "{version}"\n'
        "patterns:\n"
        f"  - id: {rule_id}\n"
        f"    layer: [{layer}]\n"
        "    regex: 'nothing_in_particular'\n"
        "    precision: low\n"
        "    question: Is this what it looks like?\n"
        "    default_severity_hint: observation\n",
        encoding="utf-8",
    )
    return path


def test_two_packs_may_declare_different_versions(tmp_path: Path) -> None:
    """The rule this replaced: every pack had to carry the same `version`.

    It sounded right — "the version is a property of the catalog, not of one
    pack" — and did not survive a second pack being added. Bumping one pack
    would mean editing every other pack's version line, so `_instruction.yaml`
    arriving in M5 would have required editing M1's closed `_base.yaml` and
    `python.yaml` for a change that corrects no pattern in them.

    **Nothing asserted the old rule**, which is why removing it turned no test
    red. This is the assertion the replacement gets.
    """
    first = pack(tmp_path, "_base.yaml", "2026.09.3", "code", "net.bind_all")
    second = pack(tmp_path, "_instruction.yaml", "2026.10.1", "instruction", "prose.example")
    catalog = load(sorted([first, second]))
    assert dict(catalog.versions) == {
        "_base.yaml": "2026.09.3",
        "_instruction.yaml": "2026.10.1",
    }
    by_id = {pattern.id: pattern for pattern in catalog.patterns}
    assert by_id["net.bind_all"].pack_version == "2026.09.3"
    assert by_id["prose.example"].pack_version == "2026.10.1"


def test_bumping_one_pack_moves_only_its_own_records(tmp_path: Path) -> None:
    """The defect in the alternative, asserted rather than described.

    A single catalog version derived as the maximum of the packs' would hide a
    bump: with `_instruction.yaml` at 2026.10.1, correcting a pattern in
    `_base.yaml` and bumping it to 2026.09.4 leaves the maximum unchanged. So
    `catalog_version` would not move, FR-4.6 would never fire, and the
    verifications the corrected pattern now reaches would stay in force.

    Per pack, the bump is visible in exactly its own records and in no others —
    which is the granularity FR-4.6's second trigger asks for ("a new/changed
    pattern matches **this location**").
    """
    before = load(
        sorted(
            [
                pack(tmp_path, "_base.yaml", "2026.09.3", "code", "net.bind_all"),
                pack(tmp_path, "_instruction.yaml", "2026.10.1", "instruction", "prose.example"),
            ]
        )
    )
    after = load(
        sorted(
            [
                pack(tmp_path, "_base.yaml", "2026.09.4", "code", "net.bind_all"),
                pack(tmp_path, "_instruction.yaml", "2026.10.1", "instruction", "prose.example"),
            ]
        )
    )
    moved = {
        pattern.id
        for pattern in after.patterns
        if pattern.pack_version
        != next(item.pack_version for item in before.patterns if item.id == pattern.id)
    }
    assert moved == {"net.bind_all"}, (
        "a bump to one pack must move that pack's records and no others — this is "
        "the failure a maximum-of-versions scheme would have had, silently"
    )


def test_two_packs_with_one_filename_are_refused(tmp_path: Path) -> None:
    """A pack's version is recorded under its filename, so two files sharing one
    basename make the record name a pack a reader cannot find. Impossible inside
    one directory; reachable across two `--catalog` arguments."""
    one = pack(tmp_path / "a", "_base.yaml", "2026.09.3", "code", "net.bind_all")
    two = pack(tmp_path / "b", "_base.yaml", "2026.09.4", "code", "log.sensitive")
    with pytest.raises(CatalogError, match=r"both named _base\.yaml"):
        load([one, two])


# --- A6: a pack's filename and its patterns' `layer` must agree ----------


def test_an_instruction_pattern_outside_its_pack_is_refused(tmp_path: Path) -> None:
    """§6 Q2's rule, and the id is named — "invalid catalog" sends a reader to a
    200-entry file with no starting point."""
    path = pack(tmp_path, "_base.yaml", "2026.09.3", "instruction", "prose.example")
    with pytest.raises(CatalogError) as caught:
        load_file(path)
    assert "prose.example" in str(caught.value)
    assert "_instruction.yaml" in str(caught.value)


def test_a_code_pattern_inside_the_instruction_pack_is_refused(tmp_path: Path) -> None:
    """The reverse direction, which is the half that is easy to leave out: the
    pack must hold *only* instruction patterns, or a code rule written as a code
    rule would meet FR-3.15's never-auto-classify treatment in M7."""
    path = pack(tmp_path, "_instruction.yaml", "2026.10.1", "code", "exec.example")
    with pytest.raises(CatalogError) as caught:
        load_file(path)
    assert "exec.example" in str(caught.value)
    assert "layer: [instruction]" in str(caught.value)


def test_the_manifest_pack_is_checked_the_same_way(tmp_path: Path) -> None:
    for name, layer, rule_id in (
        ("_base.yaml", "manifest", "grant.example"),
        ("_manifest.yaml", "instruction", "prose.example"),
    ):
        with pytest.raises(CatalogError) as caught:
            load_file(pack(tmp_path, name, "2026.10.1", layer, rule_id))
        assert rule_id in str(caught.value)


def test_each_pack_permits_its_own_layer(tmp_path: Path) -> None:
    """The permit, and A6 asks for it by name: a rule that only refuses passes
    by refusing everything."""
    for name, layer, rule_id in (
        ("_instruction.yaml", "instruction", "prose.example"),
        ("_manifest.yaml", "manifest", "grant.example"),
        ("_base.yaml", "code", "net.bind_all"),
        ("python.yaml", "code", "exec.example"),
    ):
        catalog = load_file(pack(tmp_path, name, "2026.10.1", layer, rule_id))
        assert catalog.patterns[0].layer == (layer,)
