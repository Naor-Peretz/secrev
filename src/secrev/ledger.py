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

# §5: "the matched span with a small margin, truncated to 200 chars".
EXCERPT_MARGIN = 24
EXCERPT_LIMIT = 200

_REDACTED = "[REDACTED]"

# G-3, and deliberately blunt. Two shapes: a value assigned to a key whose name
# says it is a credential, and any long unbroken run of credential-shaped
# characters. Over-redaction costs a reader some context in one excerpt;
# under-redaction copies a live secret into an artifact that gets committed,
# pasted into an issue, and read by people who were never meant to have it.
# The asymmetry decides the polarity.
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b (?P<key> token | password | passwd | secret | api[_-]?key
              | credential | authorization | bearer )
    \s* (?P<sep> [=:] \s* ) (?P<quote> ["']? ) (?P<value> [^\s"',)]{4,} )
    """
)
_LONG_OPAQUE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])")


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


def redact(text: str) -> str:
    """G-3: anything resembling a credential, before it reaches the ledger."""
    text = _SECRET_ASSIGNMENT.sub(
        lambda m: f"{m.group('key')}{m.group('sep')}{m.group('quote')}{_REDACTED}", text
    )
    return _LONG_OPAQUE.sub(_REDACTED, text)


def excerpt(line: str, start: int, end: int) -> str:
    """The matched span with a small margin, truncated, then redacted.

    Redaction runs last so it cannot be defeated by the truncation splitting a
    secret in half — a truncated secret is still most of a secret.
    """
    left = max(0, start - EXCERPT_MARGIN)
    right = min(len(line), end + EXCERPT_MARGIN)
    span = line[left:right].strip()
    if len(span) > EXCERPT_LIMIT:
        span = span[:EXCERPT_LIMIT]
    return redact(span)


def window(lines: list[str], index: int) -> str:
    """`lines-20`: ±20 lines around `index`, clamped to the file."""
    low = max(0, index - WINDOW_RADIUS)
    high = min(len(lines), index + WINDOW_RADIUS + 1)
    return "\n".join(lines[low:high])
