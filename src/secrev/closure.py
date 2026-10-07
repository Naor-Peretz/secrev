"""The reachable artifact set. PRD FR-1.2, P9, D-11; `BRIEF_M5.md` §2, §3.

P9 says the unit of review is the closure, not the entry file. This module
answers what an artifact can **pull in later**: the roots, every file they
reference, every reference that resolves to nothing, and every reference naming
a resource somewhere else. Progressive disclosure is a legitimate design
pattern and an obvious evasion surface, and the PRD says both in one sentence.

**A fourth consumer of the walk, and the first that is a graph over it.** The
nodes are `inventory` entries and the identity rules are `ids.py`'s; nothing
here invents a second notion of what a file is. What is new is that a file can
be reached rather than merely listed, so the traversal has to terminate on a
cycle — a skill that references a file that references the skill is how
progressive disclosure is actually written — and the output must not depend on
where that cycle was entered. Both are answered by the same thing: the record
order is total before any id is assigned, so the output is sorted and the
traversal order never reaches it.

Nothing here concludes anything, like the three detection sources. Every record
is `unresolved`, and FR-4.4's `deferred` — which is where Q1 expects most of
these to land — is a *triage* status that M7 assigns. Emitting it here would be
this milestone resolving its own candidates (FR-3.2, FR-3.11).

**It is not a fourth detection source** (D-11, as amended). The three detection
mechanisms remain three. What this contributes is the other half of FR-1.2: a
closure member that could not be resolved is "itself a finding candidate, not
an omission", and in this system exactly one mechanism makes skipping
impossible — the ledger plus FR-4.3, which refuses to render a report while any
hit is unresolved. Recorded only in `closure.json` or as a coverage-gap line, a
remote fetch nobody assessed leaves through a *passing* gate.

It imports neither `sweep`, `surfaces` nor `structure`: what the sources share
lives in `ledger.py`, and a source that can see another's module is one
refactor from seeing its results (`TASKS_M2.md` Q2). It does not import `recon`
either, and that direction matters too — recon is a peer that reports declared
metadata, and `recon.py` holds no knowledge of this module (P11).

**It verifies what it read** (`BRIEF_M5.md` A5, `.claude/TASKS_M5.md`). This is
the fifth consumer to re-read a file `inventory` has already read. The
*decisions* travel on the entry — language, binary, size, digest — but the
bytes do not, so a file replaced between the two reads would be examined as
content the inventory never classified, and `window_sha256` would identify
bytes the reviewer never saw. The four existing consumers record that window;
this one closes it, for one hash pass over bytes already in memory, because the
newest consumer adding a fifth silent window knowingly is the one thing the
milestone's own harness rule calls a defect it must fix.

The rules that decide bytes, stated because they are the ones not to revise:

  **Line-oriented, no AST.** A reference is found on a line, and the line
  number is reported against the original (`STACK.md` §5). A path built from
  variables, or split across lines, is a recorded coverage gap rather than a
  silent miss (FR-3.8). The structural seam M4 built is where cross-line
  reasoning belongs, and reaching for it here would make the closure depend on
  a parser that exists for one language.

  **Lexical resolution, never the filesystem.** A reference is joined to the
  referring file's directory and `..` is cancelled textually. `Path.resolve`
  follows symlinks, which `inventory.walk` has never done, and would make the
  artifact depend on what is outside the target.

  **A reference that leaves the root is recorded and never read**, like a
  symlink escaping it (P9, G-4).

  **Nothing is fetched.** `STACK.md` §2.1 forbids runtime network calls, and
  FR-1.2 already gives the answer: a resource named for fetching is a member
  that could not be resolved statically.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from secrev.ids import Match, assign
from secrev.inventory import (
    LANGUAGE_BY_SUFFIX,
    NOT_CODE_LANGUAGES,
    FileEntry,
    content_sha256,
    language_of,
    normalise_path,
    split_lines,
    walk,
)
from secrev.ledger import CLOSURE_DIGEST_SPEC, WINDOW_SPEC, Hit, excerpt, window

# The version of *these* rules, carried on every record this module emits.
#
# `catalog_version` holds the version of whichever ruleset produced a record, so
# that FR-4.6 can expire a verification when the rules behind it change, and so
# that nothing reading the ledger has to branch on `source` first. The three
# detection sources read their rules from a versioned YAML file; this source's
# rules are the regexes below, so the version is here and is bumped by hand when
# what counts as a reference changes.
#
# Bumping it expires every closure verification, which is the intended cost: a
# reviewer who concluded "this reference is fine" concluded it about what this
# module recognised at the time.
CLOSURE_RULES_VERSION = "1"

# The layer every closure record carries.
#
# `ledger.LAYERS` is `{code, instruction, manifest}` and FR-3.11 defines `layer`
# as a field of a *pattern* — the three values describe what kind of question a
# pattern asks. A closure record asks a different kind: how the artifact is
# composed. `code` is the closest of the three, and it is right in the sense
# that matters — composition is a property of the artifact's structure rather
# than of its prose (instruction) or its grants (manifest), whichever file the
# reference happens to sit in.
#
# That the field's name and value set fit patterns better than they fit this is
# the same PRD naming question already raised for `catalog_version` in
# `.claude/TASKS_M2.md`, and it is raised rather than resolved here
# (`BRIEF_M1.md` §8).
CLOSURE_LAYER = "code"

# How a member enters the closure. Not a kind of file — the two are separate
# axes, and a member has both.
#
#   direct       the referring line names it outright
#   conditional  the referring line reads as loading it only sometimes
#   fetch        the reference names a resource somewhere else
LOAD_DIRECT = "direct"
LOAD_CONDITIONAL = "conditional"
LOAD_FETCH = "fetch"

# What a resolved member *is*. `source` is FR-1.2's "bundled script", `binary`
# its "bundled binaries"; `data` is everything else that resolved.
KIND_SOURCE = "source"
KIND_BINARY = "binary"
KIND_DATA = "data"

# Suffixes that name a file but no language — `inventory.LANGUAGE_BY_SUFFIX`
# answers "what language is this", and these are files with none.
#
# **Not a copy of `recon._BINARY_ASSETS`**, which answers a different question:
# whether an *unread* file may be passed over without being a coverage gap. This
# one decides whether a token in a line looks like a filename at all. The two
# sets need not agree and are not asserted to: a token ending `.png` is a
# reference whether or not an unread `.png` is a gap.
_EXTRA_REFERENCE_SUFFIXES = frozenset(
    {
        # Executables and loadable objects — FR-1.2's "bundled binaries".
        ".bin",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".wasm",
        ".node",
        # Archives, which carry whatever is inside them past every rule here.
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".whl",
        ".jar",
        # Prose and configuration formats the language map does not name.
        # `.mdc` is Cursor's rules file: prose an agent reads as instruction.
        ".mdc",
        ".rst",
        ".lock",
        ".env",
        ".conf",
        ".service",
        ".plist",
    }
)

_REFERENCE_SUFFIXES = frozenset(LANGUAGE_BY_SUFFIX) | _EXTRA_REFERENCE_SUFFIXES

# A resource somewhere else. Any scheme, not an allowlist of network ones: the
# question FR-1.2 asks is whether the artifact pulls something in at load or run
# time, and `file://`, `data:` with a URL shape and a private scheme a client
# resolves are all answers to it. The scheme is named in the record's reason, so
# a reader can tell which kind they are looking at.
#
# The left-hand guard is what keeps this linear. Without it every position
# inside a long token is a start position; with it, only a token's first
# character can begin a match, so a crafted single line costs one pass rather
# than one pass per character.
_URL = re.compile(
    r"(?i)(?<![A-Za-z0-9+.-])(?P<scheme>[a-z][a-z0-9+.-]{1,31})://[^\s'\"`<>)\]},]{1,2048}"
)

# A token that looks like a path to a file. Deliberately shaped so that only a
# dot-suffix can end it, which is what keeps `self.path`, `re.compile` and
# `data.get` out of the closure: the suffix is then tested against
# `_REFERENCE_SUFFIXES`, and `.compile` is not a file extension.
#
# The same left-hand guard as `_URL`, for the same reason, and the final segment
# excludes `.` so the suffix group is the last dot rather than the first.
# `\w` rather than `[A-Za-z0-9_]`, and it is load-bearing rather than tidier:
# `\w` is Unicode-aware for a `str` pattern, so `cyclé.md` is a reference. An
# ASCII class would have skipped exactly the filenames the NFC rule exists for
# (`STACK.md` §5, §9) — the closure maps names to names, so a decomposed or
# accented filename going unreferenced is the one miss no other source could
# reveal. The suffix stays ASCII, because `_REFERENCE_SUFFIXES` is.
_PATH = re.compile(
    r"""(?x)
    (?<![\w./@+-])
    (?P<path>
        (?: \.{1,2} / )?
        (?: [\w@.+-]{1,128} / ){0,16}
        [\w@+-]{1,128}
        (?P<suffix> \. [A-Za-z0-9]{1,8} )
    )
    (?![\w/-])
    """
)

# A Markdown link or image target, which needs no suffix to be a reference:
# `[the playbook](references/playbook)` names a file and `_PATH` cannot see it.
_MD_TARGET = re.compile(r"!?\]\(\s*(?P<target>[^)\s]{1,512})\s*\)")

# Words on the referring line that read as loading something only sometimes.
#
# Low precision by construction — paraphrase defeats this exactly as FR-3.15
# says it defeats the instruction layer — and deliberately not load-bearing:
# the classification decides a *field* on a member that is in the closure either
# way. Getting it wrong costs a reader one mislabelled row; it can never remove
# a member, which is the only error that would matter.
_CONDITIONAL = re.compile(
    r"""(?ix)
    \b (?: if | when | unless | optional(?:ly)? | progressive(?:ly)?
         | lazy | lazily | conditional(?:ly)? | on[-\s]demand
         | as[-\s]needed | only[-\s]for | depending ) \b
    """
)

# The rule ids, in the `closure` namespace — reserved in `ledger.py`, so
# `catalog.py` refuses a pattern that claims one and a `rule_id` in `hits.jsonl`
# names exactly one question whichever source produced it.
RULE_REMOTE = "closure.remote_resource"
RULE_MISSING = "closure.missing_reference"
RULE_ESCAPING = "closure.escaping_reference"
RULE_CHANGED = "closure.content_changed"
RULE_AMBIGUOUS = "closure.ambiguous_reference"

# One question per rule, phrased as a question (FR-3.2: patterns are questions,
# not verdicts, and a source that concluded would be deciding what M7 decides).
_QUESTIONS = {
    RULE_REMOTE: (
        "This artifact names a resource somewhere else. Is it fetched at load or "
        "run time, what would it contain, and who controls it? Nothing here "
        "fetched it, so nothing here has reviewed it."
    ),
    RULE_MISSING: (
        "This path is referenced and no file in the target holds it. Is it "
        "generated, installed, or written before use, and by what?"
    ),
    RULE_ESCAPING: (
        "This reference resolves outside the target root. What is read from "
        "there, and is it inside the artifact's control?"
    ),
    RULE_CHANGED: (
        "This file's bytes changed between the inventory read and the closure "
        "read. Which content did the review actually see?"
    ),
    RULE_AMBIGUOUS: (
        "This name matches more than one file in the target and the line does "
        "not say which. Which one is loaded, and does the loader resolve it the "
        "same way under every working directory?"
    ),
}

_PRECISIONS = {
    # A URL is certainly a reference to somewhere else and is often only
    # documentation. The question is whether it is fetched, and that is the
    # low-precision half.
    RULE_REMOTE: "low",
    # A filename in a sentence is a filename, and most of them are prose.
    RULE_MISSING: "low",
    # Fewer ways to write this by accident, and `../` out of a tree is the
    # shape P9 cares about.
    RULE_ESCAPING: "medium",
    # Two digests over the same path disagreed. There is nothing imprecise
    # about it.
    RULE_CHANGED: "high",
    # The name really does match several files. Whether the line meant one of
    # them is the imprecise half.
    RULE_AMBIGUOUS: "medium",
}

# What this source cannot reach, one line each, so a reader sees the limit
# rather than inferring it from a regex (FR-3.8). Fixed text; the per-member
# lines are derived below and sit beside these.
_CLOSURE_GAPS = (
    "closure: references are read line by line, so a path built from variables, "
    "concatenated, or split across lines is not seen",
    "closure: a reference is recognised by its file suffix or by a Markdown link "
    "target, so a directory, an extensionless script, or a bare module name "
    "named in prose is not followed",
    "closure: whether a member is loaded conditionally is read from words on the "
    "referring line, which paraphrase defeats — the label never removes a member "
    "from the closure, so a wrong label costs a row and not a file",
    "closure: a resource named for fetching is recorded and never fetched "
    "(STACK.md §2.1 forbids runtime network calls), so what it would have "
    "contained is unreviewed by construction (FR-1.2)",
    "closure: a member that is binary, unreadable, not a regular file, or past "
    "the size bound is in the closure and is not read, so references inside it "
    "are not followed",
    "closure: a reference is resolved relative to the referring file, then "
    "relative to the target root, then by filename when it names no directory "
    "— so a name matching one file somewhere in the target is reported as that "
    "file even where the line meant another, which over-reports a member rather "
    "than missing one (P4, P6)",
)

# How many paths a derived gap line names before it says "and N more". The same
# number `recon.GAP_LIST_LIMIT` uses, and spelled here rather than imported
# because importing it would be this module reaching into a peer for a display
# rule (P11). Asserted equal in `tests/test_closure.py`, so the two cannot drift
# without something saying so.
GAP_LIST_LIMIT = 5


@dataclass(frozen=True, order=True)
class Member:
    """One file in the closure.

    `referenced_from` is `"<path>:<line>"` for every line that reaches it,
    sorted. A root reached by nothing carries an empty tuple, which is how a
    reader tells "this is where the review started" from "this is pulled in".
    """

    path: str
    kind: str
    load: str
    size: int
    sha256: str | None
    referenced_from: tuple[str, ...]


@dataclass(frozen=True, order=True)
class Unresolved:
    """One reference that did not become a member, and why.

    The reference is kept **as written**, not as a path: a resolution that
    failed has no path, and showing the token is what lets a reader find the
    line again.
    """

    reference: str
    load: str
    rule_id: str
    reason: str
    referenced_from: tuple[str, ...]


@dataclass(frozen=True)
class Closure:
    """What `closure.json` holds, plus the block this source contributes.

    `hits` is not in the artifact. It goes to `hits.jsonl` through `ledger.py`
    exactly as the three detection sources' records do (§6 Q1), and keeping it
    off `closure.json` means the two files never carry two spellings of one
    record.
    """

    roots: tuple[str, ...]
    roots_given: bool
    members: tuple[Member, ...]
    unresolved: tuple[Unresolved, ...]
    hits: list[Hit]
    coverage_gaps: tuple[str, ...]


@dataclass(frozen=True, order=True)
class _Reference:
    """A reference as found: where it was written, and what it said."""

    from_path: str
    line: int
    raw: str
    load: str


def _kind(entry: FileEntry) -> str:
    """What a resolved member is: FR-1.2's bundled binary, bundled script, or
    neither.

    Binary first, because `is_binary` is a measurement over bytes and the
    language map is a guess from a suffix — a `.py` file that is 90% non-text is
    a binary that was named `.py`, and the proportion is the one of the two the
    target cannot choose for free (`STACK.md` §5).
    """
    if entry.is_binary:
        return KIND_BINARY
    name = language_of(entry.path)
    if name is None or name in NOT_CODE_LANGUAGES:
        return KIND_DATA
    return KIND_SOURCE


def _load_of(sighted: set[str] | None) -> str:
    """One load label from every label a member was sighted under.

    `direct` wins. A member named outright on one line is directly loaded
    whatever another line says about it, so the label cannot depend on which
    line the walk reached first — and a root nothing references is direct
    because the caller named it.

    This is order-independence by construction rather than by the frontier
    happening to be sorted: A2 asks that the closure not depend on where a cycle
    was entered, and a first-sighting rule would have made one field of every
    member depend on exactly that.
    """
    if not sighted or LOAD_DIRECT in sighted:
        return LOAD_DIRECT
    return LOAD_CONDITIONAL if LOAD_CONDITIONAL in sighted else LOAD_FETCH


def _is_readable_text(entry: FileEntry) -> bool:
    """Whether this entry's bytes may be read and scanned for references.

    The same five conditions the three detection sources apply, in the same
    order and for the same reason: `inventory` already tried, and a peer must
    skip exactly what the others skip or they disagree about scope with only one
    of them saying so.
    """
    return not (
        entry.is_binary
        or entry.is_symlink
        or not entry.is_readable
        or not entry.is_regular
        or not entry.is_within_size_bound
    )


def _lexical_join(from_path: str, reference: str) -> str | None:
    """`reference` as a root-relative POSIX path, or None when it leaves the root.

    Lexical, never `Path.resolve`: resolving follows symlinks, which
    `inventory.walk` has never done, so a resolving join would read a file
    outside the target through a link inside it — the breach M3.5 found in
    `recon`, where containment held for every file the walk discovered and
    failed for every file something went looking for by name.

    An absolute reference is not joined at all. It names a location on the
    machine running the review rather than one in the artifact, so it is a
    reference that leaves the root by definition.
    """
    if reference.startswith("/"):
        return None
    base = from_path.rsplit("/", 1)[0] if "/" in from_path else ""
    parts: list[str] = []
    for segment in f"{base}/{reference}".split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not parts:
                # Nothing left to cancel: the reference points above the root.
                return None
            parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts) if parts else None


def _references_on_line(from_path: str, number: int, line: str) -> list[_Reference]:
    """Every reference on one line, in the order the line gives them.

    Order inside a line is the match order of three regexes rather than the
    textual order, which is deliberate: the output is sorted before any id is
    assigned, so this order never reaches an artifact, and sorting here as well
    would be a second ordering rule to keep in agreement with the first.
    """
    load = LOAD_CONDITIONAL if _CONDITIONAL.search(line) else LOAD_DIRECT
    found: list[_Reference] = []

    for match in _URL.finditer(line):
        found.append(
            _Reference(from_path=from_path, line=number, raw=match.group(0), load=LOAD_FETCH)
        )

    # A Markdown target first, then bare tokens. A target carrying a suffix is
    # found by both and de-duplicated by the caller's mapping, which is keyed on
    # the reference text — two sightings of one reference on one line are one
    # reference, where D-6's "two hits stay two hits" is about two *questions*.
    for match in _MD_TARGET.finditer(line):
        target = match.group("target")
        if _URL.match(target) or target.startswith("#"):
            continue
        found.append(_Reference(from_path=from_path, line=number, raw=target, load=load))

    for match in _PATH.finditer(line):
        if match.group("suffix").lower() in _REFERENCE_SUFFIXES:
            found.append(
                _Reference(from_path=from_path, line=number, raw=match.group("path"), load=load)
            )
    return found


def _changed_reason(entry: FileEntry, actual: str) -> str:
    """A5's reason: what happened first, then both digests.

    **The digests are redacted out of `match_excerpt`, and that is G-3 working
    rather than a defect.** `ledger._LONG_OPAQUE` replaces any unbroken run of
    32 or more credential-shaped characters, and a 64-character hex digest is
    one. Over-redaction costs a reader some context in one excerpt; the
    alternative is either weakening a credential rule or shortening a digest to
    slip under its floor, and tuning a safety rule to make an excerpt prettier
    is the move this project exists to refuse.

    So the sentence is ordered for the redacted reading: what happened, which
    file, and what it invalidates come first, and the digests last. The full
    pair survives in `closure.json`, which is not an excerpt, and in the
    `window_sha256` input — `ledger.py` hashes the window unredacted, so the
    record's id is keyed on the real digests either way.
    """
    return (
        f"content changed between the inventory read and this one, so the window "
        f"digests and line numbers any other source reported for {entry.path} "
        f"describe bytes this review did not see. The inventory recorded "
        f"{entry.sha256}; the closure read {actual}."
    )


def _derived_gaps(members: tuple[Member, ...]) -> list[str]:
    """`BRIEF_M5.md` E1: a member in a language with no coverage, named.

    Two lines rather than one, because the two states have different remedies: a
    code language this tool reads no rules for is a tool gap, and an extension
    naming no language at all is a file whose kind nobody has decided.

    The honest half of FR-3.8 is that this names the members rather than the
    languages. "no coverage for: ruby" tells a reviewer a gap exists; the paths
    tell them where to look.
    """
    lines: list[str] = []
    for label, why, paths in (
        (
            "a code language no rule set reads",
            "structural rules are Python only, and the catalog's code patterns "
            "declare their own languages",
            sorted(
                member.path
                for member in members
                for name in (language_of(member.path),)
                if name is not None and name not in NOT_CODE_LANGUAGES and name != "python"
            ),
        ),
        (
            "an extension naming no language this tool knows",
            "so no rule set claims it and nothing decided whether it is code",
            sorted(
                member.path
                for member in members
                if language_of(member.path) is None and member.kind != KIND_BINARY
            ),
        ),
    ):
        if not paths:
            continue
        shown = ", ".join(paths[:GAP_LIST_LIMIT])
        if len(paths) > GAP_LIST_LIMIT:
            shown += f", and {len(paths) - GAP_LIST_LIMIT} more — the full list is members[]"
        lines.append(f"closure: members in {label} — {why}: {shown}")
    return lines


@dataclass(frozen=True, order=True)
class _Record:
    """One ledger record before it has an id.

    A dataclass rather than a tuple, and the reason is a bug it had: with a
    tuple the line number was unpacked from a string in one loop and used as an
    integer in another, in one function scope, which `mypy --strict` caught and
    a reader would not have. Field order is the sort order, which is why `line`
    is first — records inside one file are ordered by line, then rule, before
    any id is assigned.
    """

    line: int
    rule_id: str
    reference: str
    reason: str
    window_spec: str


def _pending_records(
    unresolved: tuple[Unresolved, ...],
    changed: list[tuple[FileEntry, str]],
) -> dict[str, list[_Record]]:
    """Every record this source will emit, grouped by the file it is anchored in.

    One record per (reference, referring line), which is what makes two
    references on one line two records (D-6).
    """
    pending: dict[str, list[_Record]] = {}
    for item in unresolved:
        for origin in item.referenced_from:
            from_path, _, raw_number = origin.rpartition(":")
            pending.setdefault(from_path, []).append(
                _Record(
                    line=int(raw_number),
                    rule_id=item.rule_id,
                    reference=item.reference,
                    reason=item.reason,
                    window_spec=WINDOW_SPEC,
                )
            )
    for entry, actual in changed:
        # Line 0: there is no line. A content mismatch is a fact about the whole
        # file, and `_record_text` reads the zero as "nothing to anchor on"
        # rather than as line one, which would quote a line at random.
        pending.setdefault(entry.path, []).append(
            _Record(
                line=0,
                rule_id=RULE_CHANGED,
                reference=entry.path,
                reason=_changed_reason(entry, actual),
                window_spec=CLOSURE_DIGEST_SPEC,
            )
        )
    return pending


def _record_text(record: _Record, lines: list[str]) -> tuple[str, str]:
    """The window text and the excerpt source for one record.

    Both at once, because they must agree: an excerpt quoting a line the window
    does not cover sends a reviewer to the wrong place, and the two were
    computed by two copies of the same three-branch decision until this returned
    a pair.
    """
    if record.window_spec == CLOSURE_DIGEST_SPEC:
        # `digest-pair`: the two digests and nothing else. There is no line to
        # anchor on, and the file's own bytes are what the finding is about —
        # windowing them would identify the content whose provenance is in
        # question.
        return record.reason, record.reason
    if 1 <= record.line <= len(lines):
        return window(lines, record.line - 1), lines[record.line - 1]
    # A reference whose referring file has no lines this run read: a root the
    # target does not contain. The reference is the only text there is.
    return record.reference, record.reference


def _hits(
    unresolved: tuple[Unresolved, ...],
    changed: list[tuple[FileEntry, str]],
    lines_by_path: dict[str, list[str]],
) -> list[Hit]:
    """The block this source contributes to `hits.jsonl` (§6 Q1).

    **Anchored on the referring line, not on the member.** A member that could
    not be resolved has no content to window, and the text a reviewer has to
    read is the line that pulls it in — so `file` and `line` name the referring
    file, the excerpt is that line redacted, and the window is `lines-20` around
    it. FR-4.6 then expires the verification when the line that names the member
    changes, which is exactly the right trigger.

    `lines-20` rather than a name of its own: C-2 keeps differently *shaped*
    spans from being compared, and this is `lines-20`'s shape anchored on a line
    in a file, as a pattern record's is. `decl-20` exists because FR-4.1 says a
    surface is traced rather than windowed, so a surface verification is not a
    judgment of its span; a closure verification *is* a judgment of this one.

    A content mismatch is the exception and carries `digest-pair`, because its
    span is not lines at all — there is no line to anchor on, and quoting the
    file would be quoting the bytes whose provenance is the finding.
    """
    pending = _pending_records(unresolved, changed)
    hits: list[Hit] = []
    for from_path in sorted(pending):
        records = sorted(pending[from_path])
        lines = lines_by_path.get(from_path, [])
        # One window per (line, spec), shared by every record on it — the same
        # memoisation `sweep.py` and `surfaces.py` carry, and for the same
        # reason: `ids.assign` hands a shared string to its own digest cache.
        texts: dict[tuple[int, str], tuple[str, str]] = {}
        matches: list[Match] = []
        for record in records:
            key = (record.line, record.window_spec)
            if key not in texts:
                texts[key] = _record_text(record, lines)
            matches.append(Match(rule_id=record.rule_id, line=record.line, window=texts[key][0]))

        for record, identifier in zip(records, assign(from_path, matches), strict=True):
            shown = texts[(record.line, record.window_spec)][1]
            hits.append(
                Hit(
                    id=identifier,
                    file=from_path,
                    line=record.line,
                    layer=CLOSURE_LAYER,
                    source="closure",
                    rule_id=record.rule_id,
                    precision=_PRECISIONS[record.rule_id],
                    question=" ".join(_QUESTIONS[record.rule_id].split()),
                    # Redacted (G-3), like every other source's excerpt: a URL
                    # with userinfo in it is a credential written down.
                    match_excerpt=excerpt(shown, 0, len(shown)),
                    status="unresolved",
                    catalog_version=CLOSURE_RULES_VERSION,
                    window_spec=record.window_spec,
                )
            )
    return hits


def _roots(
    inventory: dict[str, FileEntry], entries: list[str] | None
) -> tuple[tuple[str, ...], bool]:
    """The roots, and whether the caller named them.

    `None` means every inventoried file whose bytes may be read. The two answer
    different questions and the artifact records which was asked, which is why
    the boolean travels with the list rather than being inferred from its
    length.
    """
    if entries is None:
        return (
            tuple(path for path, entry in sorted(inventory.items()) if _is_readable_text(entry)),
            False,
        )
    given = {normalise_path(name) for name in entries}
    # A usage error rather than a finding, and the difference is who made the
    # mistake. An entry the *target* does not contain is a hole in the artifact
    # and becomes an unresolved member. An entry pointing outside the target is
    # a hole in the invocation: the caller asked this tool to begin its review
    # somewhere it refuses to read (G-4, P9), and answering with a review of
    # what remained would be a partial answer reported as a whole one.
    #
    # `_lexical_join("x", …)` rather than a second rule: the one definition of
    # "does this leave the root" is the one the references use, so a reference
    # and an entry cannot disagree about the same path.
    outside = sorted(
        name for name in given if name.startswith("/") or _lexical_join("x", name) is None
    )
    if outside:
        raise ValueError(
            f"--entry must name a path inside the target; these do not: {', '.join(outside)}"
        )
    return tuple(sorted(given)), True


@dataclass
class _Graph:
    """What the traversal accumulates. Mutable, and local to one `closure` call.

    `origins` and `failures` hold sets because one line naming one reference
    twice is one edge, while two *different* references on one line stay two
    (D-6) — the de-duplication is per reference text, not per line.
    """

    origins: dict[str, set[str]]
    failures: dict[tuple[str, str, str, str], set[str]]
    # Every load label a member was sighted under, not the first one. See
    # `_load_of`: a first-sighting rule would make the label depend on which
    # root the walk started from, which is the property A2 asks the closure not
    # to have.
    load_kinds: dict[str, set[str]]
    lines_by_path: dict[str, list[str]]
    changed: list[tuple[FileEntry, str]]
    seen: set[str]

    def fail(self, reference: str, rule_id: str, reason: str, load: str, origin: str) -> None:
        """One unresolved reference, keyed on everything that describes it.

        `load` is part of the key rather than kept in a side table: the same
        token written once as a direct reference and once conditionally is two
        statements about how the artifact loads it, and a side table keyed on
        the token alone would silently keep whichever was seen first.
        """
        self.failures.setdefault((reference, rule_id, reason, load), set()).add(origin)


def _by_basename(inventory: dict[str, FileEntry]) -> dict[str, list[str]]:
    """Inventory paths grouped by filename, for the last resolution step."""
    grouped: dict[str, list[str]] = {}
    for path in inventory:
        grouped.setdefault(path.rsplit("/", 1)[-1], []).append(path)
    return {name: sorted(paths) for name, paths in grouped.items()}


def _resolve(
    from_path: str,
    reference: _Reference,
    inventory: dict[str, FileEntry],
    by_basename: dict[str, list[str]],
) -> tuple[str | None, str, str]:
    """A reference as either a member path, or the rule and reason it is not one.

    **Three resolution conventions, tried in order, because three exist.** The
    first version tried only the first and the result was unusable: run against
    this repository it produced 3,692 records, 3,692 of which were documents
    citing each other by name — `STACK.md` alone 415 times, because a mention
    inside `src/secrev/` resolved to `src/secrev/STACK.md`. CLAUDE.md's own
    sentence applies: a signal that is always on is H-1's habit in a new place,
    and a reviewer who has to read 3,692 lines to find four reads none of them.

      1. **Relative to the referring file's directory.** What a relative
         reference means, and what progressive disclosure usually writes: a
         skill naming `reference.md` means the one beside it.
      2. **Relative to the target root.** What documentation writes:
         `scripts/check.sh`, `src/secrev/closure.py`. Resolving this is not a
         convenience — without it every root-relative citation in an artifact's
         own documentation is reported as a reference to nothing.
      3. **By filename, when the reference names no directory.** What a
         sentence means by "see STACK.md". Only when exactly one file in the
         target carries that name; several is its own finding, because which
         one is loaded then depends on the loader's working directory and the
         line does not say.

    Each step can only *add* members, so none of them can hide one. What they
    cost is a mis-resolution — a reference reported as a member of the target
    when the artifact meant something else — and the cost of that is a file a
    reviewer reads unnecessarily, against a miss, which is a file nobody reads.
    P4 and P6 decide the direction.

    The ways to fail are kept apart, for the reason `recon`'s four "present but
    not read" fields are kept apart: a resource somewhere else, a path above the
    root, a name matching several files, and a path that is simply not there are
    four different problems with four different remedies, and folding them would
    send a reviewer to check the wrong thing.
    """
    if reference.load == LOAD_FETCH:
        scheme = reference.raw.split(":", 1)[0].lower()
        return (
            None,
            RULE_REMOTE,
            f"names a {scheme} resource; nothing here fetches it "
            "(STACK.md §2.1 forbids runtime network calls)",
        )

    # The escape test comes first and uses the referring directory, because a
    # reference climbing out of the tree is a question about *this* file's
    # neighbourhood (P9) — testing it root-relative would silently turn
    # `../../../etc/x.conf` into a path that simply does not exist.
    relative = _lexical_join(from_path, reference.raw)
    if relative is None:
        return None, RULE_ESCAPING, "resolves outside the target root and was not read (P9)"
    if relative in inventory:
        return relative, "", ""

    root_relative = _lexical_join("", reference.raw)
    if root_relative is not None and root_relative in inventory:
        return root_relative, "", ""

    if "/" in reference.raw:
        return None, RULE_MISSING, "no file at that path in the target"
    return _by_name(reference.raw, by_basename)


def _by_name(reference: str, by_basename: dict[str, list[str]]) -> tuple[str | None, str, str]:
    """`_resolve`'s third convention, split out so neither function has seven
    exits — which `ruff`'s PLR0911 is right about: a resolver with seven ways
    out is one a reader has to trace rather than read."""
    matches = by_basename.get(reference, [])
    if len(matches) == 1:
        return matches[0], "", ""
    if not matches:
        return None, RULE_MISSING, "no file at that path in the target"
    shown = ", ".join(matches[:GAP_LIST_LIMIT])
    if len(matches) > GAP_LIST_LIMIT:
        shown += f", and {len(matches) - GAP_LIST_LIMIT} more"
    return (
        None,
        RULE_AMBIGUOUS,
        f"names {len(matches)} files in the target and the line does not say which: {shown}",
    )


def _traverse(root: Path, roots: tuple[str, ...], inventory: dict[str, FileEntry]) -> _Graph:
    """Breadth-first from the roots, following references, terminating on cycles.

    The traversal order does not reach the output — every list in `Closure` is
    sorted before it is returned — so this is free to be the simple thing. What
    it must do is terminate, and `seen` is the whole of that.
    """
    graph = _Graph(origins={}, failures={}, load_kinds={}, lines_by_path={}, changed=[], seen=set())
    # Computed once for the whole traversal. Per file it would be a pass over
    # the inventory per reference, which on a real target is the difference
    # between one walk and thousands.
    by_basename = _by_basename(inventory)
    pending = sorted(roots)
    for path in pending:
        # A root the caller named and the target does not contain. Not an
        # error: a review of an artifact whose declared entry file is missing is
        # a review with a hole in it, and the hole is the finding.
        if path not in inventory:
            graph.fail(
                path,
                RULE_MISSING,
                "given as an entry point and not present in the target",
                LOAD_DIRECT,
                f"{path}:0",
            )

    while pending:
        path = pending.pop(0)
        if path in graph.seen:
            # The cycle terminates here, and this is the whole of it: a skill
            # that references a file that references the skill is how
            # progressive disclosure is written, not an exotic case.
            continue
        graph.seen.add(path)
        entry = inventory.get(path)
        if entry is None or not _is_readable_text(entry):
            continue
        pending.extend(sorted(_read_one(root, entry, inventory, by_basename, graph)))
    return graph


def _read_one(
    root: Path,
    entry: FileEntry,
    inventory: dict[str, FileEntry],
    by_basename: dict[str, list[str]],
    graph: _Graph,
) -> set[str]:
    """Read one member, verify it, and return the members it reaches."""
    # `os_path`, never `path`: the record is NFC and the filesystem may not be,
    # and on ext4 an NFD filename does not exist under its NFC spelling.
    raw = (root / entry.os_path).read_bytes()

    # A5: the bytes are verified against the digest `inventory` recorded for the
    # same path. A mismatch means the file changed under the review, and the
    # record goes to `hits.jsonl` rather than to stderr — the ledger is the only
    # mechanism here that makes passing over it impossible.
    #
    # The references are still read, from the bytes just verified as
    # *different*. Skipping them would let a changed file hide its own closure,
    # which is the evasion this check exists to notice.
    actual = content_sha256(raw)
    if entry.sha256 is not None and actual != entry.sha256:
        graph.changed.append((entry, actual))

    lines = split_lines(raw.decode("utf-8", errors="replace"))
    graph.lines_by_path[entry.path] = lines

    frontier: set[str] = set()
    for number, line in enumerate(lines, start=1):
        for reference in _references_on_line(entry.path, number, line):
            origin = f"{entry.path}:{number}"
            target, rule_id, reason = _resolve(entry.path, reference, inventory, by_basename)
            if target is None:
                graph.fail(reference.raw, rule_id, reason, reference.load, origin)
                continue
            graph.origins.setdefault(target, set()).add(origin)
            graph.load_kinds.setdefault(target, set()).add(reference.load)
            frontier.add(target)
    return frontier


def closure(
    root: Path,
    entries: list[str] | None = None,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> Closure:
    """The reachable artifact set under `root`, in a deterministic order.

    `entries` names the roots. `None` means every inventoried file whose bytes
    may be read, and `closure.json` says which of the two it was — because the
    two answer different questions. Given roots answer "what does this entry
    pull in", which is FR-1.2's question and the one a reviewer asks once they
    know the artifact's entry file. The default answers "what does this tree
    pull in that is not in it", which is the question that can be asked of an
    arbitrary target with no entry file declared anywhere, and which never
    under-reports: every file is a root, so nothing is missed because the entry
    was guessed wrongly.

    A given root that is not in the inventory is itself an unresolved member. A
    root that exists and cannot be read is a member whose references were not
    followed, and the coverage gap says so.

    `excluded` and `max_bytes` are threaded to `inventory.walk` (M3.5 A2). A
    consumer of the walk must skip exactly what the others skip, or an override
    would change scope for one and not the others.
    """
    inventory = {entry.path: entry for entry in walk(root, excluded, max_bytes)}
    roots, roots_given = _roots(inventory, entries)
    graph = _traverse(root, roots, inventory)

    members = tuple(
        sorted(
            Member(
                path=path,
                kind=_kind(inventory[path]),
                load=_load_of(graph.load_kinds.get(path)),
                size=inventory[path].size,
                sha256=inventory[path].sha256,
                referenced_from=tuple(sorted(graph.origins.get(path, set()))),
            )
            for path in sorted(graph.seen | set(graph.origins))
            if path in inventory
        )
    )
    unresolved = tuple(
        sorted(
            Unresolved(
                reference=reference,
                load=load,
                rule_id=rule_id,
                reason=reason,
                referenced_from=tuple(sorted(found)),
            )
            for (reference, rule_id, reason, load), found in graph.failures.items()
        )
    )
    return Closure(
        roots=roots,
        roots_given=roots_given,
        members=members,
        unresolved=unresolved,
        hits=_hits(unresolved, graph.changed, graph.lines_by_path),
        coverage_gaps=(*_derived_gaps(members), *_CLOSURE_GAPS),
    )


def to_json(result: Closure) -> str:
    """`closure.json`, byte-stable.

    Two-space indent and a trailing newline so a diff of the golden is readable;
    `sort_keys=False` because the key order is the contract rather than an
    accident of insertion — the same reasoning as `recon.to_json`, and the two
    artifacts are read side by side.
    """
    document = {
        "closure_version": CLOSURE_RULES_VERSION,
        "roots": {
            "given": result.roots_given,
            "paths": list(result.roots),
        },
        "members": [
            {
                "path": member.path,
                "kind": member.kind,
                "load": member.load,
                "size": member.size,
                "sha256": member.sha256,
                "referenced_from": list(member.referenced_from),
            }
            for member in result.members
        ],
        "unresolved": [
            {
                "reference": item.reference,
                "load": item.load,
                "rule_id": item.rule_id,
                "reason": item.reason,
                "referenced_from": list(item.referenced_from),
            }
            for item in result.unresolved
        ],
        "coverage_gaps": list(result.coverage_gaps),
    }
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
