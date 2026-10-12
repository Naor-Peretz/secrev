"""F1's resolution of every candidate the two M5 packs raise against `.claude/`.

`BRIEF_M5.md` F1 asks for `secrev closure .` over this repository **and** "every
candidate the two new packs raise against `.claude/` resolved under P4 — this
repository *is* an agentic artifact, and the instruction layer is the one place
where that is not a cute observation."

**The owner's reading of P4, which is what this module implements:** P4 forbids
unexamined membership, not shared reasoning. A candidate may be resolved by a
class, provided the row for it carries one *instance-level* fact showing the
class condition holds for that candidate. So the table this module generates has
one row per candidate — asserted, not assumed — and each row carries the fact.
That is the answer to the question `.claude/TASKS_M5.md` recorded for M7: a
class resolution is admissible when it is per-candidate evidence that the
candidate is in the class, rather than a sentence standing in for 175 reads.

**The discriminator is what a client actually loads, and closure membership is
not it.** The obvious idea was to let the closure resolve these — a candidate in
a file no declared entry point reaches is a record about the repository rather
than content an agent loads, which would be P9 doing exactly what it is for.
Measured: **159 of the 175 candidates sit in files that *are* closure members**,
including `receipts.md`, `TASKS_M0.md` and the guard sources, which no client
loads as instruction. They are members only through the prose-citation chains
`.claude/TASKS_M5.md` records as the open problem. So the closure cannot resolve
these until that is settled, and the discriminator here is a property of the
*client* instead: which paths under `.claude/` Claude Code reads into a context
window, which paths it executes, and which it never opens at all.

That is a fact about the host rather than about this repository, so it is written
down as one, with the consequence spelled out per class.

**This table is content-keyed and will go stale.** A candidate id derives from
`(path, rule_id, window_sha256, ordinal)`, so editing any file under `.claude/`
re-identifies the candidates in it and this golden moves. That is FR-4.6
arriving by hand rather than a defect: a verification is keyed to the content it
was made against, and content that changed needs re-affirming. The test reports
which ids gained or lost a row rather than only failing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from secrev.catalog import Catalog, load
from secrev.inventory import split_lines
from secrev.ledger import Hit
from secrev.sweep import sweep

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / ".claude"

# Paths that exist on a developer's machine and not in CI, so a committed golden
# must not depend on them. `.claude/.gitignore` covers both: `settings.local.json`
# holds this machine's own permissions, and `hooks/state/` is the background
# gate's scratch space. Excluded by name rather than by asking git, so the test
# needs no subprocess — and a *new* ignored file appearing would make this table
# fail locally while passing in CI, which is a loud failure naming the ids
# rather than a silent divergence.
IGNORED = ("settings.local.json", "hooks/state/")


@dataclass(frozen=True)
class Resolution:
    """One candidate, its class, and the instance-level fact for it."""

    candidate_id: str
    file: str
    line: int
    rule_id: str
    role: str
    fact: str


# What Claude Code does with each path under `.claude/`. **This is the class
# condition**, and it is a fact about the host: the resolution of a candidate
# turns on whether the text it matched ever reaches an agent's context as
# instruction, and that is decided by the client, not by the file's format.
#
# `inventory.is_prose` answers a different question — does this format hold prose
# — and answering it is all an instruction-layer pattern can do on its own. The
# gap between the two is why there are candidates here in the hundreds rather
# than the dozen files a client actually loads.
ROLE_LOADED_ON_ACTIVATION = "loaded-on-activation"
ROLE_LOADED_ON_DEMAND = "loaded-on-demand"
ROLE_LOADED_WITH_SUBAGENT = "loaded-with-subagent"
ROLE_LOADED_AS_COMMAND = "loaded-as-command"
ROLE_CLIENT_CONFIGURATION = "client-configuration"
ROLE_EXECUTED_NOT_LOADED = "executed-not-loaded"
ROLE_REPOSITORY_RECORD = "repository-record"

# One sentence per class: what the client does, and what that makes the
# candidate. These are the shared half of the reasoning; the per-row fact is the
# half that makes each candidate examined.
ROLE_MEANING = {
    ROLE_LOADED_ON_ACTIVATION: (
        "A skill body. The client loads it into the context window when the skill "
        "activates, so its prose **is** instruction-layer content for this artifact and "
        "the candidate is a true positive about text an agent reads. **Resolved "
        "`verified-ok`:** the text is this artifact's own intended behaviour, authored by "
        "the owner and seen by `scope-guard.sh` when written. G-6 does not apply — it "
        "governs content in a *reviewed target* addressing the reviewing agent, and here "
        "the target and the reviewer are one repository (AC-10), so this is the harness "
        "instructing itself rather than a third party instructing it."
    ),
    ROLE_LOADED_ON_DEMAND: (
        "A file beside a skill, loaded only when that skill's body tells the agent to "
        "read it — progressive disclosure. Instruction-layer content on the same terms "
        "as the body, one hop further out, and **resolved `verified-ok` for the same "
        "reason**. The one thing this class is not is unexamined: progressive disclosure "
        "is exactly where P9 says to look, which is why the hop is named rather than "
        "folded into the class above."
    ),
    ROLE_LOADED_WITH_SUBAGENT: (
        "A subagent definition. The client loads it when that subagent runs, so its "
        "prose is instruction-layer content for the subagent rather than for the session "
        "that spawned it. **Resolved `verified-ok`**, on the activation class's reasoning, "
        "with the narrower blast radius stated: a direction here reaches one subagent's "
        "turn and not the session."
    ),
    ROLE_LOADED_AS_COMMAND: (
        "A slash-command body, loaded into the context window when the command is "
        "invoked. Instruction-layer content scoped to that invocation, **resolved "
        "`verified-ok`** on the same terms."
    ),
    ROLE_CLIENT_CONFIGURATION: (
        "Client configuration. The client reads it as data rather than as prose, so a "
        "match here is manifest-layer: a declaration to assess, not text to obey. "
        "**Resolved `verified-ok` where the declaration is one `settings.json` makes "
        "deliberately** — the hook bindings and the read-only allowlist are the controls "
        "this repository documents and tests. The one grant that is *not* resolved here "
        "is in `settings.local.json`, which is gitignored and therefore outside this "
        "table; it is recorded in `.claude/TASKS_M5.md` and the owner is narrowing it."
    ),
    ROLE_EXECUTED_NOT_LOADED: (
        "A guard the client executes. Nothing in it enters an agent's context as "
        "instruction — the match is in the source of the control itself. **Resolved "
        "`verified-ok` as a false positive of a rule that reads format rather than "
        "reachability:** `inventory.is_prose` can say a file holds prose and cannot say "
        "whether anything loads it, which is the gap this whole table exists to cross. "
        "Each row says where in the source the match sits, because a match in a comment "
        "explaining what a guard refuses and a match in a protocol string the guard "
        "emits are different facts."
    ),
    ROLE_REPOSITORY_RECORD: (
        "A repository record — a ledger, a receipt, a README. No client loads it into any "
        "context window; it is written for people reading the history. **Resolved "
        "`verified-ok` as a false positive of the same kind**, and these are the ones "
        "`BRIEF_M5.md` §5 said to expect: the densest are the milestone ledgers arguing "
        "*for removing* auto-approved rules, which a rule looking for directions to "
        "pre-approve will always match. Tuning that away would be tuning away the "
        "ability to read prose."
    ),
}


# The classification, in order. A table rather than a chain of returns, so the
# ordering is data a reader can check against the client's behaviour rather than
# control flow they have to trace — and `ruff` is right that eight exits is a
# function nobody reads twice.
#
# **Order is load-bearing.** A `SKILL.md` under `skills/` is a body before it is
# a file beside one; `skill-rules.json` is configuration before it is a file
# beside a skill; a `.sh` shipped with a skill is executed rather than read.
_ROLE_RULES: tuple[tuple[str, str], ...] = (
    ("hooks/", ROLE_EXECUTED_NOT_LOADED),
    ("check.sh", ROLE_EXECUTED_NOT_LOADED),
    ("settings.json", ROLE_CLIENT_CONFIGURATION),
    ("skills/skill-rules.json", ROLE_CLIENT_CONFIGURATION),
    ("ruff.toml", ROLE_CLIENT_CONFIGURATION),
    ("agents/", ROLE_LOADED_WITH_SUBAGENT),
    ("commands/", ROLE_LOADED_AS_COMMAND),
)


def role_of(relative: str) -> str:
    """Which class a path under `.claude/` falls in."""
    for prefix, role in _ROLE_RULES:
        if relative == prefix or relative.startswith(prefix):
            return role
    if relative.startswith("skills/"):
        if relative.endswith("/SKILL.md"):
            return ROLE_LOADED_ON_ACTIVATION
        if relative.endswith((".sh", ".py")):
            return ROLE_EXECUTED_NOT_LOADED
        return ROLE_LOADED_ON_DEMAND
    return ROLE_REPOSITORY_RECORD


def _where_in_source(line: str) -> str:
    """Where in a guard's own source the match sits: comment, string, or code.

    The instance-level fact for `executed-not-loaded`, and it earned the
    distinction: a first version answered comment-or-not and three rows came back
    "NOT in a comment" — two module docstrings and
    `hook_ask.py`'s `"hookEventName": "PreToolUse"`, which is the hook
    protocol's own field name in the code that emits it. Calling those "not a
    comment" was true and useless; calling them comments would have been false.
    Three states is what the records actually are.

    Computed rather than asserted, which is the whole reason the negative case
    surfaced at all.
    """
    stripped = line.strip()
    if stripped.startswith("#"):
        return "in a comment"
    if stripped.startswith(('"""', "'''", '"', "'")) or '"' in stripped or "'" in stripped:
        return "in a string or docstring"
    return "in executable code"


# Where the match sits, for the classes whose fact is the matched text plus the
# path's role. The two classes with a *computed* fact are handled in `_fact`
# itself, because a phrase from a table would hide that something was measured.
_WHERE = {
    ROLE_LOADED_ON_ACTIVATION: "in a skill body the client loads on activation",
    ROLE_LOADED_ON_DEMAND: "in a file a skill body points at",
    ROLE_LOADED_WITH_SUBAGENT: "in a subagent definition",
    ROLE_LOADED_AS_COMMAND: "in a slash-command body",
    ROLE_REPOSITORY_RECORD: "in a record written for people reading the history",
}


def _fact(relative: str, hit: Hit, line: str) -> str:
    """One instance-level fact showing this candidate is in its class.

    Every row carries the matched text, because that is what a reader needs to
    see the class condition holding. Three classes carry a computed fact beside
    it, and those are the three where a path alone would be a label rather than
    evidence.
    """
    role = role_of(relative)
    excerpt = " ".join(hit.match_excerpt.split())[:150]
    if role == ROLE_EXECUTED_NOT_LOADED:
        # Computed, and the one that found its own negative cases.
        return f"{_where_in_source(line)}, in a file the client executes: `{excerpt}`"
    if role == ROLE_CLIENT_CONFIGURATION:
        declaration = line.strip().startswith(('"', "'")) or ":" in line
        shape = "a declaration" if declaration else "NOT a declaration"
        return f"{shape} in client configuration: `{excerpt}`"
    return f"{_WHERE[role]}: `{excerpt}`"


def new_pack_ids(catalog: Catalog) -> set[str]:
    """The rule ids M5's two packs added, derived from `layer` rather than named."""
    return {
        pattern.id
        for pattern in catalog.patterns
        if pattern.layer in (("instruction",), ("manifest",))
    }


def candidates() -> list[Hit]:
    """Every candidate the two new packs raise against the committed `.claude/`."""
    catalog = load(sorted((ROOT / "patterns").glob("*.yaml")))
    wanted = new_pack_ids(catalog)
    return [
        hit
        for hit in sweep(HARNESS, catalog)
        if hit.rule_id in wanted and not any(part in hit.file for part in IGNORED)
    ]


def resolutions() -> list[Resolution]:
    """One row per candidate, sorted so the table is a pure function of the tree."""
    lines_by_file: dict[str, list[str]] = {}
    rows: list[Resolution] = []
    for hit in candidates():
        if hit.file not in lines_by_file:
            raw = (HARNESS / hit.file).read_bytes().decode("utf-8", errors="replace")
            lines_by_file[hit.file] = split_lines(raw)
        lines = lines_by_file[hit.file]
        line = lines[hit.line - 1] if 1 <= hit.line <= len(lines) else ""
        rows.append(
            Resolution(
                candidate_id=hit.id,
                file=hit.file,
                line=hit.line,
                rule_id=hit.rule_id,
                role=role_of(hit.file),
                fact=_fact(hit.file, hit, line),
            )
        )
    return sorted(rows, key=lambda row: (row.file, row.line, row.rule_id, row.candidate_id))


def to_markdown(rows: list[Resolution]) -> str:
    """The table, byte-stable, with the shared reasoning above it.

    One file rather than a table and a separate explanation: a reader checking a
    row needs the class's meaning in front of them, and a class sentence in
    another document is one that drifts away from the rows it governs.
    """
    out: list[str] = [
        "# F1 — every candidate the two M5 packs raise against `.claude/`, resolved",
        "",
        "Generated by `tests/f1_resolutions.py` and pinned by",
        "`tests/test_f1_resolutions.py`. Regenerated, never repaired.",
        "",
        "**Why this file exists.** `BRIEF_M5.md` F1 asks for every candidate the two new",
        "packs raise against `.claude/` to be resolved under P4. The owner's reading,",
        "which this implements: P4 forbids *unexamined membership*, not shared reasoning.",
        "A class resolution is admissible when each row carries one instance-level fact",
        "showing the class condition holds for that candidate — so there is one row per",
        "candidate, asserted rather than assumed, and each row carries the matched text.",
        "",
        "**The discriminator is what the client loads, and closure membership is not it.**",
        "Letting the closure resolve these was the first idea and it fails on measurement:",
        "when it was measured, **159 of 175** candidates sat in files that *are* closure",
        "members, including the",
        "receipts, the ledgers and the guard sources, which no client loads as",
        "instruction. They are members only through the prose-citation chains",
        "`.claude/TASKS_M5.md` records as the open problem. So the class condition is a",
        "property of the host — which paths it reads into a context window, which it",
        "executes, and which it never opens — and that is written down as a fact about",
        "the host rather than about this repository.",
        "",
        "**This file is content-keyed and will go stale.** A candidate id derives from",
        "`(path, rule_id, window_sha256, ordinal)`, so editing any file under `.claude/`",
        "re-identifies the candidates in it. That is FR-4.6 arriving by hand rather than a",
        "defect: a verification is keyed to the content it was made against. The test",
        "names the ids that gained or lost a row.",
        "",
        "## The classes",
        "",
    ]
    for role in sorted(ROLE_MEANING):
        out.append(f"- **`{role}`** — {ROLE_MEANING[role]}")
    out += [
        "",
        "## The rows",
        "",
        f"{len(rows)} candidates, {len(rows)} rows.",
        "",
        "| candidate | rule | where | class | instance-level fact |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        out.append(
            f"| `{row.candidate_id}` | `{row.rule_id}` | `{row.file}:{row.line}` "
            f"| `{row.role}` | {row.fact} |"
        )
    return "\n".join(out) + "\n"
