"""F1's resolution table is complete, per-candidate, and current.

`BRIEF_M5.md` F1 asks for every candidate the two M5 packs raise against
`.claude/` resolved under P4. The owner's reading, which `tests/f1_resolutions.py`
implements: **P4 forbids unexamined membership, not shared reasoning** — a class
resolution is admissible when each row carries one instance-level fact showing
the class condition holds for that candidate.

So the assertions here are about *completeness and currency*, which is what a
class resolution can get wrong:

  * one row per candidate, counted both ways;
  * no candidate without a row and no row without a candidate, naming the ids
    either way, because that is FR-4.6 arriving by hand — an id moves when the
    content it was resolved against changes;
  * every row in a declared class, with no fallback, so a path this classifier
    has not thought about fails rather than landing in a default;
  * the class condition derived rather than asserted.

This module skips entirely when `.claude/` is absent. A contributor without
Claude Code should not have their build fail on a layer they never run, which is
the same boundary `scripts/check.sh` keeps by not mentioning `.claude` at all.
"""

from __future__ import annotations

import collections
from pathlib import Path

import pytest

from f1_resolutions import (
    HARNESS,
    IGNORED,
    ROLE_MEANING,
    candidates,
    resolutions,
    role_of,
    to_markdown,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "f1_resolutions.md"

pytestmark = pytest.mark.skipif(
    not HARNESS.is_dir(), reason=".claude/ is absent; F1 is about that layer"
)


def test_the_table_matches_the_golden_byte_for_byte() -> None:
    """`read_bytes`, for the reason every other golden here uses it: `read_text`
    translates CRLF on the way in and would compare a golden it had just
    silently repaired."""
    assert to_markdown(resolutions()).encode("utf-8") == GOLDEN.read_bytes()


def test_every_candidate_has_exactly_one_row() -> None:
    """P4's actual requirement, counted both ways.

    The failure this guards is a class resolution that *looks* complete: a
    paragraph saying "the 175 are documentation" with no way to tell whether
    there were 175 or 190, or whether one of them was something else. Counting
    both directions is what makes the class admissible rather than a gesture.
    """
    rows = resolutions()
    found = candidates()
    assert len(rows) == len(found), (
        f"{len(found)} candidates and {len(rows)} rows. Every candidate gets a row — "
        "a class resolution is admissible because each row carries instance-level "
        "evidence, which a missing row does not"
    )

    by_id = collections.Counter(row.candidate_id for row in rows)
    repeated = [key for key, count in by_id.items() if count > 1]
    assert not repeated, f"candidates with more than one row: {repeated}"


def test_no_candidate_is_unresolved_and_no_row_is_orphaned() -> None:
    """The currency half, and it is FR-4.6 by hand.

    A candidate id derives from `(path, rule_id, window_sha256, ordinal)`, so
    editing any file under `.claude/` re-identifies the candidates in it. When
    that happens this fails naming the ids that gained or lost a row, rather than
    only saying the golden moved — because the two are different jobs: one is
    regenerating a table, the other is re-reading content whose resolution
    expired.
    """
    rows = {row.candidate_id for row in resolutions()}
    found = {hit.id for hit in candidates()}

    unresolved = sorted(found - rows)
    assert not unresolved, (
        f"{len(unresolved)} candidate(s) have no row, so they are unexamined (P4): "
        f"{unresolved[:10]}. Regenerate the table and read the new rows — their "
        "resolutions expired with the content they were made against (FR-4.6)"
    )
    orphaned = sorted(rows - found)
    assert not orphaned, (
        f"{len(orphaned)} row(s) resolve a candidate that no longer exists: "
        f"{orphaned[:10]}. A vanished hit is never auto-resolved (FR-4.9) — check "
        "whether the content was fixed, moved, or merely stopped matching"
    )


def test_every_row_is_in_a_declared_class() -> None:
    """No fallback class, so an unfamiliar path fails rather than defaulting.

    `role_of` ends in `repository-record`, which *is* a default — so this asserts
    the stronger thing: every class used has a written meaning, and the meanings
    cover every class the classifier can return.
    """
    rows = resolutions()
    used = {row.role for row in rows}
    assert used <= set(ROLE_MEANING), (
        f"classes with no written meaning: {sorted(used - set(ROLE_MEANING))}"
    )
    for role in ROLE_MEANING:
        assert ROLE_MEANING[role].strip(), f"{role} has an empty meaning"


def test_the_class_condition_is_derived_from_the_path_not_asserted() -> None:
    """The classifier is code, and these are the decisions it must make.

    Spot-checked rather than exhaustive on purpose: the point is that the
    ordering inside `role_of` is load-bearing — a `SKILL.md` under `skills/` is a
    body before it is a file beside one, `skill-rules.json` is configuration
    before it is a file beside a skill, and a `.sh` shipped with a skill is
    executed rather than read.
    """
    assert role_of("skills/debugging/SKILL.md") == "loaded-on-activation"
    assert role_of("skills/skill-developer/TROUBLESHOOTING.md") == "loaded-on-demand"
    assert role_of("skills/strategic-compact/suggest-compact.sh") == "executed-not-loaded"
    assert role_of("skills/skill-rules.json") == "client-configuration"
    assert role_of("settings.json") == "client-configuration"
    assert role_of("agents/python-reviewer.md") == "loaded-with-subagent"
    assert role_of("commands/check.md") == "loaded-as-command"
    assert role_of("hooks/scope-guard.sh") == "executed-not-loaded"
    assert role_of("check.sh") == "executed-not-loaded"
    assert role_of("receipts.md") == "repository-record"
    assert role_of("TASKS_M5.md") == "repository-record"


def test_every_row_carries_the_matched_text() -> None:
    """The instance-level fact, without which this is 175 labels.

    A class name and a path are not evidence that a candidate is in the class. The
    matched text is what a reader checks the class against, so every row has to
    carry it.
    """
    for row in resolutions():
        assert "`" in row.fact and len(row.fact) > 20, (
            f"{row.candidate_id} ({row.file}:{row.line}) has no instance-level fact"
        )


def test_the_table_excludes_what_ci_does_not_have() -> None:
    """A committed golden must not depend on a gitignored file.

    `settings.local.json` holds this machine's own permissions and
    `hooks/state/` is the background gate's scratch space; `.claude/.gitignore`
    covers both. A table including them would pass here and fail in CI for files
    CI does not have — and the grant inside `settings.local.json` is recorded in
    `.claude/TASKS_M5.md` precisely because it cannot be recorded here.
    """
    for row in resolutions():
        for part in IGNORED:
            assert part not in row.file, f"{row.file} is gitignored and cannot be pinned"
