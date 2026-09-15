"""Candidate identity, and what must not change it. STACK.md §5, PRD FR-4.5/4.6.

The id is not a label. It is the thread a verification hangs on across
re-reviews: FR-4.6 matches this review's candidates against the last one's by
id, and an id that moved reads as two events — a `vanished` hit whose
adjudication is discarded, and an `unresolved` one demanding fresh work. For
code nobody touched. That is the precise inverse of what D-4 exists to
provide, and the cost is not a wrong answer but a slow erosion of the reason
to trust any prior answer.

So the assertions here are almost all negative: they name a change that must
leave the id alone. Each is written as the edit someone actually makes.

Two levels, deliberately.

`derive()` is the primitive and takes the components directly, so its tests
state which components participate. `assign()` takes a file's matches and
computes the ordinal itself, so its tests state *scenarios* — an occurrence
deleted, an occurrence inserted — without presupposing how identity is
derived.

The split exists because an earlier version of this file got it wrong. It
expressed "deleting an earlier occurrence must not re-identify a later one"
as `derive(ordinal=1) == derive(ordinal=0)`, which encoded the very mechanism
under review: an ordinal ranging over every match of the rule in the file. A
test whose *parameters* assume the mechanism cannot judge it. Scenarios go to
`assign()`; only genuine component questions stay at `derive()`.
"""

from __future__ import annotations

import pytest

from secrev import ids

PATH = "pkg/app.py"
RULE = "py.eval_call"
WINDOW = "result = eval(user_input)\n"
OTHER_WINDOW = "cfg = yaml.load(fh)\n"
THIRD_WINDOW = "value = eval(payload)\n"


def derive(
    path: str = PATH,
    rule_id: str = RULE,
    window: str = WINDOW,
    ordinal: int = 0,
) -> str:
    return ids.derive(relative_path=path, rule_id=rule_id, window=window, ordinal=ordinal)


def match(line: int, window: str, rule_id: str = RULE) -> ids.Match:
    return ids.Match(rule_id=rule_id, line=line, window=window)


# ---------------------------------------------------- derive(): the components


def test_the_same_finding_at_a_different_path_is_a_different_candidate() -> None:
    """Identity is per location. Two files with identical content hold two
    findings, and resolving one says nothing about the other."""
    assert derive(path="pkg/app.py") != derive(path="pkg/other.py")


def test_a_different_rule_on_the_same_content_is_a_different_candidate() -> None:
    """D-6: two patterns matching one line stay two hits, and stay two
    findings if both are real. They cannot share an id."""
    assert derive(rule_id="py.eval_call") != derive(rule_id="py.exec_call")


def test_content_changing_does_change_the_identity() -> None:
    """The direction that keeps this from being "identify by less".

    If the window changed, the thing reviewed is not the thing here now.
    FR-4.6 requires that to invalidate, and `window_sha256` sitting inside the
    id makes it structural rather than a separate check that can be forgotten.
    """
    assert derive(window=WINDOW) != derive(window=OTHER_WINDOW)


def test_line_takes_no_part_in_the_identity() -> None:
    """`derive()` has no `line` parameter, and that is the assertion.

    PRD FR-4.5: a verification "anchored only to a line number is lost the
    moment the content moves". One added import shifts every line below it,
    so an id containing `line` re-identifies every candidate in a file after
    an edit that touched none of them.
    """
    with pytest.raises(TypeError):
        ids.derive(  # type: ignore[call-arg]
            relative_path=PATH, rule_id=RULE, window=WINDOW, ordinal=0, line=90
        )


def test_the_id_is_stable_across_calls() -> None:
    """Derived, never allocated. A value from `id()`, `uuid4()` or a counter
    over a run is stable within one process and meaningless between two."""
    assert len({derive() for _ in range(5)}) == 1


@pytest.mark.parametrize("field", ["relative_path", "rule_id", "window"])
def test_every_identifying_component_is_required(field: str) -> None:
    """Silently defaulting an identifying component collapses two candidates
    into one id, which loses a finding rather than duplicating one (H-1)."""
    kwargs: dict[str, object] = {
        "relative_path": PATH,
        "rule_id": RULE,
        "window": WINDOW,
        "ordinal": 0,
    }
    del kwargs[field]
    with pytest.raises(TypeError):
        ids.derive(**kwargs)  # type: ignore[arg-type]


# ------------------------------------------------------- assign(): the edits
#
# Where a counter breaks, and it breaks on ordinary edits rather than exotic
# ones. The ordinal is computed here rather than supplied, so these say what
# must survive without saying how.


def test_an_unrelated_file_elsewhere_changes_nothing() -> None:
    assert ids.assign(PATH, [match(90, WINDOW)]) == ids.assign(PATH, [match(90, WINDOW)])


def test_deleting_an_earlier_occurrence_does_not_re_identify_a_later_one() -> None:
    """Two matches of one rule at lines 40 and 90. Delete the first. Nothing
    about the survivor changed — not its content, not its meaning, not its
    position relative to anything a reviewer looked at."""
    both = ids.assign(PATH, [match(40, OTHER_WINDOW), match(90, WINDOW)])
    survivor = ids.assign(PATH, [match(90, WINDOW)])
    assert survivor[0] == both[1], (
        "deleting an earlier match re-identified this one — FR-4.6 reads that "
        "as a vanished hit plus a new unresolved one, discarding an "
        "adjudication for code that did not change"
    )


def test_inserting_an_earlier_occurrence_does_not_re_identify_a_later_one() -> None:
    """The mirror image, and the commoner direction: a second `eval` is added
    above an existing one."""
    alone = ids.assign(PATH, [match(90, WINDOW)])
    joined = ids.assign(PATH, [match(40, THIRD_WINDOW), match(90, WINDOW)])
    assert joined[1] == alone[0]


def test_an_edit_above_the_match_does_not_re_identify_it() -> None:
    """One added import shifts every line below it."""
    before = ids.assign(PATH, [match(90, WINDOW)])
    after = ids.assign(PATH, [match(91, WINDOW)])
    assert before == after


def test_two_identical_windows_in_one_file_stay_two_candidates() -> None:
    """D-6. Byte-identical matches are indistinguishable by content and are
    still two hits, so something must separate them."""
    assigned = ids.assign(PATH, [match(40, WINDOW), match(90, WINDOW)])
    assert len(set(assigned)) == 2


def test_identical_windows_are_the_one_case_an_id_still_moves() -> None:
    """The residue, asserted so it is documented rather than discovered.

    Delete the first of two byte-identical matches and the second's ordinal
    shifts. This is irreducible: the two cannot be told apart by content, so
    any identity separating them is positional, and positional identity moves.

    It is bounded — identical windows, same file — where the old scheme's
    instability was not, and it is the price of D-6. Asserted in the direction
    it actually behaves, because a test claiming it is stable would be a test
    that fails for the right reason and gets "fixed" the wrong way.
    """
    both = ids.assign(PATH, [match(40, WINDOW), match(90, WINDOW)])
    survivor = ids.assign(PATH, [match(90, WINDOW)])
    assert survivor[0] != both[1]


def test_ordinal_does_not_range_over_the_whole_rule() -> None:
    """The scoping, stated directly. Three matches of one rule, two of them
    identical: the odd one out must be ordinal 0 in its own group, not 2 in a
    file-wide sequence — otherwise deleting either of the others moves it."""
    assigned = ids.assign(PATH, [match(10, WINDOW), match(40, OTHER_WINDOW), match(90, WINDOW)])
    assert assigned[1] == derive(window=OTHER_WINDOW, ordinal=0)
