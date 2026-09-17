"""The pure logic inside the gate scripts, which nothing tested until M3.5.

`scripts/` was type-checked by nothing until `-013`, and three of its five
scripts still had no direct tests. `attack.py` covers the gate's *status*
behaviour well — that a missing tool exits 2, that no stage loses its exit code
to a pipe or to `set -e` — but nothing covered the logic inside the scripts
themselves. "Run by something, verified by nothing" is the shape that left
`self_check.py` bypassable for four milestones.

What is tested here is what is worth testing: the pure functions. Deliberately
**not** `deps_audit.py`, which shells out to `pip-audit` over the network — a
unit test there would test the mock, and saying so is a better answer than
manufacturing coverage.

Loaded with `importlib` rather than by mutating `sys.path`: `scripts/` is not a
package, and the existing precedent (`test_codeql_check.py`) runs its script as
a subprocess, which cannot reach a pure function.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None, name
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


license_check = _load("license_check")
determinism_check = _load("determinism_check")


# --- scripts/license_check.py --------------------------------------------


def test_a_trove_classifier_normalises_to_its_spdx_id() -> None:
    """The whole difficulty of this check, per the module's own comment: the
    alternative is an allowlist that silently misses "MIT License" because it
    holds "MIT"."""
    assert license_check._normalise("MIT License") == [["MIT"]]
    assert license_check._normalise("Apache Software License") == [["Apache-2.0"]]
    assert license_check._normalise("  MIT  ") == [["MIT"]]


def test_the_alias_lookup_is_case_folded() -> None:
    assert license_check._normalise("mit license") == [["MIT"]]
    assert license_check._normalise("MIT LICENSE") == [["MIT"]]


def test_every_alias_key_is_lowercase() -> None:
    """Lookup is `ALIASES.get(cleaned.lower(), cleaned)`, so an alias key
    carrying a capital letter can never match anything.

    It would not fail; it would simply never fire, and the licence it was added
    to recognise would be reported as unrecognised — a rule that is dead the
    day it is written. That is the failure shape this milestone has now found
    eight times, so it is asserted rather than left to inspection.
    """
    wrong = [key for key in license_check.ALIASES if key != key.lower()]
    assert wrong == [], f"alias keys that can never match: {wrong}"


def test_an_unrecognised_licence_survives_normalisation_so_it_can_be_refused() -> None:
    """Allowlist polarity, and the property most worth pinning here.

    An unknown string must pass through unchanged, because `main` then asks
    whether it is in `ALLOWED` and it is not. If normalisation ever started
    "helpfully" resolving unknown licences, the check would admit exactly what
    it exists to refuse, and every gate run would still be green.
    """
    assert license_check._normalise("GPL-3.0") == [["GPL-3.0"]]
    assert not license_check.is_allowed("GPL-3.0")


def test_an_empty_licence_field_yields_no_candidates_and_is_refused() -> None:
    """A package declaring nothing is flagged rather than passed, because the
    permissive reading of "no licence stated" is the dangerous one.

    **This is the trap in the conjunction change, and the reason it is pinned
    here.** The old rule was `any(...)`, and `any([])` is `False`, so an empty
    field was refused for free. The stricter rule is `all(...)`, and `all([])`
    is `True` — so flipping the operator without guarding the empty case would
    silently turn "no licence declared" into "acceptable", inside a change that
    reads as tightening.
    """
    assert license_check._normalise("") == []
    assert license_check._normalise("   ") == []
    assert not license_check.is_allowed("")
    assert not license_check.is_allowed("   ")


def test_a_disjunction_passes_when_one_branch_is_allowed() -> None:
    """A genuine SPDX `OR` means the licensee chooses, so one allowed branch is
    enough."""
    assert license_check._normalise("MIT OR Apache-2.0") == [["MIT", "Apache-2.0"]]

    # The regression risk of the stricter reading, pinned: tightening `;` and
    # `,` must not turn a genuine disjunction into a false positive. A package
    # offering "MIT OR GPL-3.0" lets the licensee take MIT.
    assert license_check.is_allowed("MIT OR GPL-3.0")


def test_a_semicolon_list_is_read_as_a_conjunction() -> None:
    """`;` and `,` separate licences that *all* apply; ` OR ` offers a choice.

    This reverses the behaviour an earlier version of this test pinned. `;` and
    `,` are how `pip-licenses` joins multiple trove classifiers, and reading
    them as a disjunction meant `"MIT, GPL-3.0"` passed the allowlist on the
    strength of MIT alone — a check admitting exactly what it exists to refuse,
    while every gate run stayed green.

    So normalisation returns *groups*: each group must be satisfied, and one
    alternative within a group suffices. `"MIT License; BSD License"` is two
    groups of one; `"MIT OR Apache-2.0"` is one group of two.
    """
    assert license_check._normalise("MIT License; BSD License") == [["MIT"], ["BSD-3-Clause"]]
    assert license_check._normalise("MIT OR Apache-2.0; ISC") == [["MIT", "Apache-2.0"], ["ISC"]]

    assert license_check.is_allowed("MIT License; BSD License")
    assert not license_check.is_allowed("MIT License; GPL-3.0")
    assert not license_check.is_allowed("MIT, GPL-3.0")


def test_the_ambiguous_bsd_classifier_is_read_as_the_stricter_form() -> None:
    """The trove classifier does not say which BSD. The module reads it as the
    3-clause form deliberately; pinned because reading it as 2-clause would be
    a silent loosening."""
    assert license_check._normalise("BSD License") == [["BSD-3-Clause"]]


# --- scripts/determinism_check.py ----------------------------------------


def _ledger(*records: dict[str, str]) -> bytes:
    return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records).encode("utf-8")


def test_records_split_on_newline_alone() -> None:
    """The TASK-M2-007 fix, which had no coverage in this script.

    `str.splitlines()` also breaks on U+0085, U+2028 and U+2029, and the ledger
    writes those unescaped inside a record because `to_jsonl` uses
    `ensure_ascii=False`. A target choosing its own filenames could therefore
    cut its own record in two and make every later comparison meaningless — and
    the determinism check would report a difference that was an artifact of its
    own parser.
    """
    # Built with `chr()` rather than written literally. Ruff flags the raw
    # characters as ambiguous and is right for a reason beyond style: a test
    # whose whole subject is "these separators must not split a record" is
    # unreadable when the separators are invisible in the source, and an editor
    # normalising one would silently change what is being asserted. The
    # codepoint numbers say exactly what is meant, and carry no backslash that
    # could be mangled on the way in.
    for separator in (chr(0x85), chr(0x2028), chr(0x2029)):
        blob = _ledger({"id": "a", "file": f"x{separator}y"})
        records = determinism_check._records(blob)
        assert len(records) == 1, f"{separator!r} split a record in two"
        assert records[0]["file"] == f"x{separator}y"


def test_records_ignore_blank_lines() -> None:
    assert determinism_check._records(b"\n\n") == []


def test_ids_are_the_record_ids() -> None:
    blob = _ledger({"id": "a", "file": "one"}, {"id": "b", "file": "two"})
    assert determinism_check._ids(blob) == {"a", "b"}
