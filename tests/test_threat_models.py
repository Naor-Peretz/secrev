"""The threat-model layer's structure, pinned. `BRIEF_M3.md` §4, PRD §8.

M3 ships prose, so NFR-3 has no claim on it and the artifact goldens do not
cover it. That removes the safety net M1 and M2 leaned on, and this file is what
replaces it.

**Discovery in code, the pin in data.** Nothing here names an overlay. The
tests glob `threat-models/*.md`, extract the ids, and compare against
`tests/golden/question_ids.json` in both directions. Adding an archetype is then
a content change — a new overlay plus its entry in the golden — with no Python
edited, which is what AC-4 requires ("no script changes") and what NFR-6 means
by "new archetype = new or edited data file". Owner decision, 2026-09-16.

Discovery *alone* would defeat the purpose: if the expected set were simply
whatever was found, deleting an overlay or a question would shrink both sides at
once and the test would stay green — the silent narrowing `STACK.md` §8 H-4
exists to prevent. Discovery finds; the golden pins. Neither half works without
the other.

Ids are append-only. A superseded question keeps its id and says it is
superseded, because the id is what a later milestone cites: M9's report states
which questions were asked, and a finding cites the question it came from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "threat-models"
CORE_NAME = "_agentic-core.md"
CORE = MODELS / CORE_NAME
GOLDEN = ROOT / "tests" / "golden" / "question_ids.json"

# One question per list item, `- **CORE-01 — Title.**`. The shape is what makes
# the set machine-readable at all, so it is asserted rather than assumed — see
# `test_every_question_uses_the_shape_the_golden_can_see`, without which a
# question written another way would never enter the golden and would ship
# unpinned.
QUESTION = re.compile(r"^- \*\*([A-Z]+-\d{2}) — ", re.MULTILINE)

# PRD §8.1, in its order. The order is part of the contract: §8.1 is a numbered
# list, and a file carrying the eight headings in another sequence is a
# different document.
CORE_SECTIONS = (
    "1. Trust boundaries",
    "2. Text as instruction (P8)",
    "3. File write as execution (P7)",
    "4. Capability grants (P10)",
    "5. Closure and deferred loading (P9)",
    "6. Autonomous reachability",
    "7. Persistence and lateral reach",
    "8. Egress",
)

# PRD §8.2's six, in its order. `BRIEF_M3.md` §2 says "in that order" and means
# it: an overlay is read by an agent composing several of them, and six sections
# appearing in a different sequence in each file cost the reader the structure
# the two-layer split was meant to buy.
OVERLAY_SECTIONS = (
    "1. Applies when",
    "2. Additional trust boundaries",
    "3. Archetype-specific dangerous sinks",
    "4. Mandatory questions",
    "5. Pattern packs to enable",
    "6. Known-good implementations",
)


def golden() -> dict[str, list[str]]:
    """The committed id sets, keyed by filename.

    Keys starting `_` are the shared files (the core, and the classifier when
    it lands); the rest are overlays. `README.md` is orientation and carries no
    questions, so it is outside the golden entirely.
    """
    document = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return {name: ids for name, ids in document.items() if not name.startswith("_comment")}


def model_files() -> list[str]:
    return sorted(item.name for item in MODELS.glob("*.md") if item.name != "README.md")


def overlay_files() -> list[str]:
    return [name for name in model_files() if not name.startswith("_")]


def questions(path: Path) -> list[str]:
    return QUESTION.findall(path.read_text(encoding="utf-8"))


def blocks(path: Path) -> dict[str, str]:
    """Each question's text, from its id up to the next question or heading.

    Splitting on the question shape rather than on blank lines keeps a
    multi-paragraph question whole.
    """
    text = path.read_text(encoding="utf-8")
    found = list(QUESTION.finditer(text))
    out: dict[str, str] = {}
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        out[match.group(1)] = text[match.start() : end]
    return out


def test_the_golden_covers_exactly_the_files_on_disk() -> None:
    """Both directions, which is the half a one-directional check misses. A new
    file with no committed id set fails here rather than shipping unpinned; an
    entry naming no file fails too, because that is what a rename leaves
    behind."""
    assert model_files() == sorted(golden())


@pytest.mark.parametrize("name", sorted(golden()))
def test_question_ids_are_the_committed_set(name: str) -> None:
    """The assertion the whole id convention exists for. It fails when a
    question is deleted, renumbered, or added without the golden being updated —
    and the last of those is deliberate: a new mandatory question changes what
    every review of that archetype asks."""
    assert questions(MODELS / name) == golden()[name]


@pytest.mark.parametrize("name", sorted(golden()))
def test_ids_are_unique(name: str) -> None:
    """Separate from the golden comparison, which a duplicated id would also
    fail but for a reason a reader would have to work out. Two questions sharing
    an id makes a citation ambiguous in exactly the milestone that starts citing
    them (M9)."""
    found = questions(MODELS / name)
    assert len(found) == len(set(found)), f"{name}: duplicate question ids: {found}"


@pytest.mark.parametrize("name", sorted(golden()))
def test_every_question_names_its_evidence(name: str) -> None:
    """`BRIEF_M3.md` §4: every mandatory question is answerable from an artifact
    this tool already produces, or is explicitly marked as needing a phase that
    does not exist. A question with no path to an answer is a wish.

    The check is that the marker is present, not that the claim is true — no
    test can verify the latter. What it prevents is the silent case: a question
    added with no evidence line at all, which reads as answerable and is not."""
    for question_id, block in blocks(MODELS / name).items():
        assert "*Evidence:*" in block, f"{name}: {question_id} names no evidence"


@pytest.mark.parametrize("name", sorted(golden()))
def test_every_question_uses_the_shape_the_golden_can_see(name: str) -> None:
    """`QUESTION`'s shape, asserted rather than assumed. Without this, a
    question written `- **CORE-28: Title**` never enters `questions()`, so it
    never joins the golden, nothing fails, and it ships unpinned — after which
    it can be dropped in silence, which is the one failure the ids exist to
    prevent.

    Deletion was always caught, because the count changes. An addition in a
    non-conforming shape was not."""
    loose = re.compile(r"^- \*\*[A-Z]+-\d.*$", re.MULTILINE)
    for line in loose.findall((MODELS / name).read_text(encoding="utf-8")):
        assert QUESTION.match(line), (
            f"{name}: {line!r} looks like a question but does not match the "
            "shape the golden reads — it would ship unpinned"
        )


@pytest.mark.parametrize("name", sorted(golden()))
def test_no_question_concludes(name: str) -> None:
    """`threat-models/README.md`: what a file here may not do is conclude.

    **This catches only the blunt spelling of that failure**, and the limit is
    written here rather than left for a reader to discover: four substrings
    cannot see a question that tells the agent what to conclude in its own
    words, which is the form the failure actually takes. It is a tripwire for
    the phrasings that arrive when a question is rewritten in a hurry, not
    coverage of the property. Review is what covers the property.

    Saying so matters more here than in most test docstrings: this file is the
    safety net for a milestone with no goldens, and a check that reads as
    coverage it does not have is the exact shape the overlays are careful to
    flag about the ledger's own silence."""
    for question_id, block in blocks(MODELS / name).items():
        lowered = block.lower()
        for verdict in ("is a vulnerability", "is insecure", "is unsafe", "severity: "):
            assert verdict not in lowered, f"{name}: {question_id} concludes: {verdict!r}"


def test_the_core_carries_every_section_in_order() -> None:
    """`BRIEF_M3.md` §4, first box."""
    text = CORE.read_text(encoding="utf-8")
    positions = []
    for heading in CORE_SECTIONS:
        marker = f"\n## {heading}\n"
        assert marker in text, f"{CORE_NAME} is missing the §8.1 section {heading!r}"
        positions.append(text.index(marker))
    assert positions == sorted(positions), "the §8.1 sections are present but out of order"


def test_the_core_is_not_archetype_specific() -> None:
    """`TASKS_M3.md` TASK-M3-001: no sentence that only applies to one form. The
    archetype vocabulary is the observable symptom of the core absorbing an
    overlay's content — PRD §8's failure mode, where every overlay restates the
    core and the copies drift.

    Deliberately narrow. It cannot catch reasoning that is archetype-specific
    without using the word, which is what review is for; it does catch the
    mechanical case, which is what happens under time pressure."""
    text = CORE.read_text(encoding="utf-8").lower()
    for word in ("skill", "mcp"):
        assert word not in text, f"{CORE_NAME} names {word!r}, which belongs to an overlay"


@pytest.mark.parametrize("name", overlay_files())
def test_overlay_carries_every_section_in_order(name: str) -> None:
    text = (MODELS / name).read_text(encoding="utf-8")
    positions = []
    for heading in OVERLAY_SECTIONS:
        marker = f"\n## {heading}\n"
        assert marker in text, f"{name} is missing the §8.2 section {heading!r}"
        positions.append(text.index(marker))
    assert positions == sorted(positions), f"{name}: the §8.2 sections are out of order"


@pytest.mark.parametrize("name", overlay_files())
def test_overlay_ids_share_one_prefix(name: str) -> None:
    """One archetype, one prefix. A citation in a later milestone is only
    unambiguous if the prefix identifies the file the question came from."""
    prefixes = {found.split("-", 1)[0] for found in questions(MODELS / name)}
    assert len(prefixes) == 1, f"{name}: questions use several prefixes: {sorted(prefixes)}"
    assert "CORE" not in prefixes, f"{name}: an overlay must not reuse the core's prefix"


@pytest.mark.parametrize("name", overlay_files())
def test_overlay_declares_when_it_applies(name: str) -> None:
    """`TASKS_M3.md` D-2: the signals live in each overlay's applies-when
    section and the classifier holds only the procedure, so there is one source
    of truth rather than two that drift the first time one is edited. An overlay
    with no signals makes the classifier unable to place it, and the procedure's
    fail-toward-inclusion rule cannot rescue a file offering nothing to match
    on."""
    text = (MODELS / name).read_text(encoding="utf-8")
    assert "\n## 1. Applies when\n" in text, f"{name} declares no applicability signals"


def sinks_section(name: str) -> str:
    """An overlay's §3, which is where a reader composing overlays looks. The
    required sinks below are asserted against this span rather than the whole
    file: a file-wide search would pass while §3 sat empty."""
    text = (MODELS / name).read_text(encoding="utf-8")
    start = text.index("\n## 3. Archetype-specific dangerous sinks\n")
    return text[start : text.index("\n## 4. Mandatory questions\n")].lower()


def test_the_skill_overlay_names_the_activation_descriptions_breadth() -> None:
    """`BRIEF_M3.md` §4 and PRD §8.2 item 3 require it by name — it is the sink
    the archetype is organised around, because the description is what loads
    everything else into contexts nobody reviewed it for."""
    sinks = sinks_section("skill.md")
    assert "activation description" in sinks
    assert "breadth" in sinks


def test_no_threat_model_declares_a_skill_activation() -> None:
    """Self-application (AC-10), and a trap rather than a coincidence.

    `surface.skill_activation` matches `**/SKILL.md`, and M2 made a kind's file
    globs case-insensitive (TASK-M2-006b) — so `threat-models/skill.md` is *in
    scope for that kind*. It yields no record today only because no line in it
    begins `description:` at column 0.

    This is the file that explains activation descriptions, so an example
    written flush to the margin is the likeliest edit anyone would make to it.
    That would make `secrev surfaces` emit a surface candidate pointing at the
    tool's own threat model, which a reader then has to resolve under P4 — a
    false positive the tool generates about itself. Cheap to pin here,
    confusing to meet by surprise in a self-review.

    The fix if it ever fires is to indent the example, not to narrow the kind:
    the kind is right, and frontmatter starts at column 0."""
    declaration = re.compile(r"^description:\s*\S", re.MULTILINE)
    for path in sorted(MODELS.glob("*.md")):
        assert not declaration.search(path.read_text(encoding="utf-8")), (
            f"{path.name} declares a skill activation at column 0: `secrev surfaces` "
            "would record a surface candidate pointing at a threat model (AC-10). "
            "Indent the example rather than narrowing the kind."
        )


def test_the_mcp_overlay_names_tool_return_values() -> None:
    """`BRIEF_M3.md` §4 and PRD §8.2 item 3, for the reason the PRD gives in the
    same sentence: return values "land in an agent's context and become
    instructions"."""
    assert "tool return values" in sinks_section("mcp-server.md")
