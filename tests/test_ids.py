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

The signature under test carries every fact a candidate has — path, rule,
line, window, ordinal. That is deliberate: it lets these assertions state
*which facts may participate* without presupposing the answer, and it is how
they can fail against a derivation that reads the wrong ones.
"""

from __future__ import annotations

import pytest

from secrev import ids

RULE = "py.eval_call"
WINDOW = "result = eval(user_input)\n"
OTHER_WINDOW = "cfg = yaml.load(fh)\n"


def derive(
    path: str = "pkg/app.py",
    rule_id: str = RULE,
    line: int = 90,
    window: str = WINDOW,
    ordinal: int = 1,
) -> str:
    return ids.derive(relative_path=path, rule_id=rule_id, line=line, window=window, ordinal=ordinal)


# ----------------------------------------------------- elsewhere in the tree


def test_a_file_added_elsewhere_changes_nothing() -> None:
    """The easy case, and the one a counter-based id already survives if the
    counter is per-file. Kept because it is the floor, not the ceiling."""
    assert derive() == derive()


def test_the_same_finding_at_a_different_path_is_a_different_candidate() -> None:
    """Identity is per location. Two files with identical content hold two
    findings, and resolving one says nothing about the other."""
    assert derive(path="pkg/app.py") != derive(path="pkg/other.py")


def test_a_different_rule_on_the_same_content_is_a_different_candidate() -> None:
    """D-6: two patterns matching one line stay two hits, and stay two
    findings if both are real. They cannot share an id."""
    assert derive(rule_id="py.eval_call") != derive(rule_id="py.exec_call")


# ------------------------------------------- edits inside the same file
#
# This is where a counter breaks, and it breaks on ordinary edits rather than
# exotic ones. Two occurrences of one rule at lines 40 and 90: delete the
# first and the second becomes ordinal 0 where it was 1. Nothing about the
# surviving match changed — not its content, not its meaning, not its
# location relative to anything a reviewer looked at.


def test_deleting_an_earlier_occurrence_does_not_re_identify_a_later_one() -> None:
    """The occurrence at line 90 was ordinal 1 while one existed at line 40.
    After that one is deleted it is ordinal 0. Same code, same window."""
    before = derive(line=90, ordinal=1)
    after = derive(line=90, ordinal=0)
    assert before == after, (
        "deleting an earlier match in the same file re-identified this one — "
        "FR-4.6 will read that as a vanished hit plus a new unresolved one, "
        "and discard an adjudication for code that did not change"
    )


def test_inserting_an_earlier_occurrence_does_not_re_identify_a_later_one() -> None:
    """The mirror image, and the more common direction: someone adds a second
    `eval` above an existing one."""
    assert derive(line=90, ordinal=0) == derive(line=90, ordinal=1)


def test_an_edit_above_the_match_does_not_re_identify_it() -> None:
    """Worse than the ordinal case and easier to trigger: one added import
    shifts every line below it, so every candidate in the file is re-identified
    by an edit that touched none of them.

    PRD FR-4.5 says a verification "anchored only to a line number is lost the
    moment the content moves". An id containing `line` anchors it to exactly
    that, so the mechanism defeats the requirement it exists to serve.
    """
    assert derive(line=90) == derive(line=91)


def test_content_changing_does_change_the_identity() -> None:
    """The other direction, and why this is not simply "ignore more fields".

    If the window changed, the thing that was reviewed is not the thing that
    is here now. FR-4.6 requires that to invalidate — a stable id must not be
    so stable that it carries a verification onto content nobody looked at.
    """
    assert derive(window=WINDOW) != derive(window=OTHER_WINDOW)


def test_two_identical_windows_in_one_file_stay_two_candidates() -> None:
    """The case that keeps some ordinal alive. Two byte-identical matches in
    one file are indistinguishable by content, and D-6 still says they are two
    hits. Whatever disambiguates them must range over *identical* windows
    only, so an unrelated match appearing or vanishing cannot disturb it.
    """
    first = derive(line=40, window=WINDOW, ordinal=0)
    second = derive(line=90, window=WINDOW, ordinal=1)
    assert first != second


# ------------------------------------------------------------------ shape


def test_the_id_is_stable_across_processes() -> None:
    """Derived, never allocated. A value from `id()`, `uuid4()` or a counter
    over a run is stable within one process and meaningless between two."""
    assert derive() == derive()
    assert len(set(derive() for _ in range(5))) == 1


@pytest.mark.parametrize("field", ["relative_path", "rule_id", "window"])
def test_every_identifying_field_is_required(field: str) -> None:
    """Silently defaulting an identifying field collapses two candidates into
    one id, which loses a finding rather than duplicating one (H-1)."""
    kwargs: dict[str, object] = {
        "relative_path": "pkg/app.py",
        "rule_id": RULE,
        "line": 90,
        "window": WINDOW,
        "ordinal": 0,
    }
    del kwargs[field]
    with pytest.raises(TypeError):
        ids.derive(**kwargs)  # type: ignore[arg-type]
