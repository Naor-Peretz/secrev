"""The ledger record, shared by every candidate source. PRD §7, D-11, BRIEF_M1.md §5.

Three sources feed one `hits.jsonl` as peers (D-11): patterns, surfaces, and in
M4 structure. What they share is the record — its fields, their order, how it
is serialised, how its excerpt is redacted, what window it names — and nothing
else. That shared part lives here so that no source has to import another to
emit a record. `recon.py` and `sweep.py` already kept that separation; the
surface source would have broken it by reaching into `sweep.py` for `Hit`, and
a source that can see another source's module is one refactor away from seeing
its results, which is the dependency P11 exists to prevent (`TASKS_M2.md`, Q2).

Everything here decides bytes in every ledger the tool will ever produce, so
this file is in `is_nfr3_path` and a change to it is checked against the
goldens rather than trusted.

Redaction (G-3) applies to `match_excerpt` and stops there. The window that
feeds `window_sha256` is hashed unredacted: a digest is not a reproduction, and
redacting first would make every candidate id depend on the redaction rules, so
tuning them would re-identify candidates whose content never changed.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

# The ledger's vocabulary, the same for every source. A value outside these is
# a record no later phase can place (PRD §7), so each source validates against
# the one definition rather than its own copy.
LAYERS = frozenset({"code", "instruction", "manifest"})
PRECISIONS = frozenset({"high", "medium", "low"})

# ±20 lines. Named, carried on every record, and an FR-4.6 invalidation
# trigger. See STACK.md §5 for why the name matters more than the number.
WINDOW_RADIUS = 20
WINDOW_SPEC = "lines-20"

# The surface source's window: the same ±20 lines, anchored on the declaration
# line, under its own name (TASKS_M2.md C-2, STACK.md §5). PRD FR-4.1 says
# surfaces are "traced rather than windowed", so a surface verification is not
# a judgment of this span; the name says what the span is anchored on, and two
# specs are never comparable, so a surface window can never be read as a
# pattern window that happens to cover the same lines.
DECL_WINDOW_SPEC = "decl-20"

# `BRIEF_M1.md` §5: "the matched span with a small margin, truncated to 200
# chars". Cited wrongly as `STACK.md` §5 until M3.5 — §5 there fixes traversal,
# hashing and the window, and says nothing about excerpts. The number was right
# and the attribution was not, which is the quieter half of the F1 finding: a
# citation nobody can follow is one nobody checks.
EXCERPT_MARGIN = 24
EXCERPT_LIMIT = 200

_REDACTED = "[REDACTED]"

# G-3, and deliberately blunt. Two shapes: a value assigned to a key whose name
# says it is a credential, and any long unbroken run of credential-shaped
# characters. Over-redaction costs a reader some context in one excerpt;
# under-redaction copies a live secret into an artifact that gets committed,
# pasted into an issue, and read by people who were never meant to have it.
# The asymmetry decides the polarity.
#
# M3.5 widened this after an external review defeated it three ways, all of
# them the commonest spellings a credential actually has:
#
#   * The key was anchored with `\b`, which cannot match between `_` and `P`.
#     `DB_PASSWORD=` and `OPENAI_API_KEY=` therefore never matched at all. The
#     key now absorbs the identifier it sits inside, on either side.
#   * The separator allowed no closing quote, so `{"password": "..."}` — JSON,
#     the commonest serialised form — went through untouched.
#   * `Authorization: Bearer <token>` redacted the word `Bearer` and left the
#     token, so the scheme is now part of the separator rather than the value.
#
# The two rules were assumed to cover for each other. They do not: none of
# those values is long enough to reach `_LONG_OPAQUE`'s floor, so when the key
# rule missed, nothing caught it.
# A second review widened it again, and the three misses were all the key list
# being a list:
#
#   * `PGPASS=` and `passphrase=` name a credential and matched no alternative.
#     `passphrase` *appeared* to redact, which is worse than an outright miss:
#     `_LONG_OPAQUE` happened to cover `passphrase=correct-horse-battery`
#     because `=` is in its alphabet and the whole string reached 32 characters.
#     One character shorter and it leaked. A rule that passes its own probe by
#     coincidence is the F1 failure in miniature.
#   * `private_key =` likewise, and its value — a 26-character PEM head — sits
#     below `_LONG_OPAQUE`'s floor, so nothing else caught it either.
#
# The value shape was also wrong for a quoted string. `[^\s"',)]` stops at a
# space, so `password='hunter2 with space'` redacted up to the space and printed
# the rest. A quoted value now runs to its closing quote, which is what a quote
# means; an unquoted one keeps the old shape, where a space really does end it.
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<key>  [A-Za-z0-9_.-]*
              (?: token | password | passwd | passphrase | pgpass
                | secret | api[_-]?key | private[_-]?key
                | credential | authorization | bearer )
              [A-Za-z0-9_.-]* )
    (?P<sep>  ["']? \s* [=:] \s* (?: bearer \s+ )? )
    (?: (?P<quote> ["'] ) (?P<quoted> [^"'\n]{4,} )
      | (?P<bare>  [^\s"',)]{4,} ) )
    """
)
_LONG_OPAQUE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])")

# `scheme://user:password@host`, the commonest place a live credential is
# written without a key naming it. `_SECRET_ASSIGNMENT` cannot see it — there is
# no credential word anywhere in `postgres://admin:hunter2@db/app` — and the
# password is usually far too short for `_LONG_OPAQUE`. The user half is kept:
# it is not the secret, and a connection string with both halves gone tells a
# reader nothing about which account was involved.
_URL_CREDENTIAL = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)([^\s:/@]+):([^\s/@]{1,})@")

# The alphabet `_LONG_OPAQUE` measures. An excerpt boundary landing inside a
# run of these is what `_widen_to_run_boundaries` exists to prevent.
_RUN_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-")


@dataclass(frozen=True)
class Hit:
    """One candidate. Field order is BRIEF_M1.md §5's field order, which is
    also the order they are serialised in — a stable key order is part of
    byte-identical output, not a formatting preference."""

    id: str
    file: str
    line: int
    layer: str
    source: str
    rule_id: str
    precision: str
    question: str
    match_excerpt: str
    status: str
    # The version of the ruleset that produced this record: the catalog's on a
    # pattern record, the kinds file's on a surface record (owner decision on
    # Q4, 2026-09-16). One field rather than two, so nothing reading the ledger
    # has to branch on `source` before it can tell whether a verification has
    # expired — which is what FR-4.6 needs of it. The name comes from the PRD's
    # §7 contract and is wrong for half the records it now describes;
    # renaming it is a PRD correction, raised in `.claude/TASKS_M2.md` rather
    # than settled here (BRIEF_M1.md §8: a conflict is raised, not resolved).
    catalog_version: str
    window_spec: str


def to_jsonl(hits: list[Hit]) -> str:
    """The ledger as JSON Lines. One implementation, used by the golden test
    and by `cli.py` alike — a second serialiser is a second byte format, and
    the golden would then be asserting something the tool does not emit.

    `ensure_ascii=False` on purpose: escaping non-ASCII would make the bytes
    depend on nothing useful and would mangle the non-ASCII path the fixture
    tree carries specifically to keep the NFC rule honest (`STACK.md` §9).
    """
    return "".join(json.dumps(asdict(hit), ensure_ascii=False) + "\n" for hit in hits)


def _mask_assignment(match: re.Match[str]) -> str:
    """Replace the value, keep everything that says what the value was.

    The key, the separator and the opening quote are re-emitted so the excerpt
    still reads as an assignment — `password='[REDACTED]'` tells a reviewer what
    was found, where `[REDACTED]` alone tells them only that something was.

    No closing quote is added. A quoted value matches up to but not including
    it, so the original closing quote is still in the text after the span this
    replaces; emitting one here would double it.
    """
    quote = match.group("quote") or ""
    return f"{match.group('key')}{match.group('sep')}{quote}{_REDACTED}"


def redact(text: str) -> str:
    """G-3: anything resembling a credential, before it reaches the ledger.

    URL userinfo first. It is the one shape with no credential word anywhere in
    it, so neither rule below can see it: `postgres://admin:hunter2@db` names no
    key, and the password is far too short for `_LONG_OPAQUE`'s floor.
    """
    text = _URL_CREDENTIAL.sub(lambda m: f"{m.group(1)}{m.group(2)}:{_REDACTED}@", text)
    text = _SECRET_ASSIGNMENT.sub(_mask_assignment, text)
    return _LONG_OPAQUE.sub(_REDACTED, text)


def _widen_to_run_boundaries(line: str, left: int, right: int) -> tuple[int, int]:
    """Push both edges outward until neither sits inside a credential-shaped run.

    A run cut at the boundary is a run the redactor can no longer measure:
    `_LONG_OPAQUE` keys on length, so half a token is not a shorter finding, it
    is no finding. Widening is linear in the line and bounded by it.
    """
    while left > 0 and line[left - 1] in _RUN_CHARS:
        left -= 1
    while right < len(line) and line[right] in _RUN_CHARS:
        right += 1
    return left, right


def excerpt(line: str, start: int, end: int) -> str:
    """The matched span with a small margin, redacted, then truncated to 200.

    **Redaction runs before truncation** — the reverse of what this function
    did until M3.5, and the reverse of what its own docstring claimed. The old
    argument was that "redaction runs last so it cannot be defeated by the
    truncation splitting a secret in half". That has the causality backwards:
    redacting last means redacting text a cut has already shortened, and
    `_LONG_OPAQUE` measures length. A 40-character credential cut to 20 drops
    below the floor and stops being redactable at all. PRD G-3 says a
    credential is "never reproduced", and twenty characters of one is a
    reproduction.

    Two things cut, not one. The 200-character cap is the obvious edge; the
    ±24 margin is the same defect in different clothes, and it bites sooner,
    because a credential sitting just past the margin is clipped to a handful
    of characters before the redactor ever sees it. Both edges are widened
    first, so what reaches `redact` contains whole runs or none.

    Truncating after redaction can clip the `[REDACTED]` marker itself. That
    is cosmetic — the secret is already gone, and a short marker is not one.
    """
    left = max(0, start - EXCERPT_MARGIN)
    right = min(len(line), end + EXCERPT_MARGIN)
    left, right = _widen_to_run_boundaries(line, left, right)
    span = redact(line[left:right].strip())
    if len(span) > EXCERPT_LIMIT:
        span = span[:EXCERPT_LIMIT]
    return span


def window(lines: list[str], index: int) -> str:
    """`lines-20`: ±20 lines around `index`, clamped to the file."""
    low = max(0, index - WINDOW_RADIUS)
    high = min(len(lines), index + WINDOW_RADIUS + 1)
    return "\n".join(lines[low:high])
