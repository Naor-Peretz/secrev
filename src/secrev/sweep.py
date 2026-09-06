"""The pattern candidate source. BRIEF_M1.md §5, FR-3.1.

Nothing here concludes anything. Every record leaves with `status:
"unresolved"` and a `question`, because a pattern is a question and not a
verdict (FR-3.2). If a function in this file ever wants to decide whether a hit
is real, or how severe it is, it belongs to a later milestone.

This module returns records; it does not write them. `cli.py` is the only thing
that touches the filesystem for output, which keeps G-4 — never write inside
the reviewed target — in one checkable place, and lets the golden tests compare
returned values rather than files a test had to create first.

Three rules here decide bytes in every ledger this tool will ever produce, so
they are stated rather than left to be inferred:

  **Line numbers come from the original, content is hashed LF-normalised.**
  `STACK.md` §5 requires both, and they pull in opposite directions. Splitting
  with `str.splitlines()` satisfies them at once: it breaks on CR, LF and CRLF
  alike, so numbering matches what an editor shows, and it discards the
  terminators, so the window text is LF-joined whatever the file used. A
  checkout with `autocrlf` on must not re-identify every candidate in the
  ledger.

  **The window is `lines-20`** — ±20 lines, no tightening to the enclosing
  block, because that needs a parser and `BRIEF_M1.md` §1 defers AST analysis
  to M4. The spec travels on the record so the M4 change to `block-20` is an
  invalidation FR-4.6 detects rather than one that depends on someone
  remembering `STACK.md` §5.

  **Ordering is total before ids are assigned.** Matches are sorted by
  `(line, rule_id, column)` within a file, and files arrive already sorted from
  `inventory.walk`. The ordinal in a candidate id counts within a group of
  byte-identical windows, so an unstable order would hand the same content
  different ids on two runs of the same tree.

Redaction (G-3) applies to `match_excerpt` and stops there. The window that
feeds `window_sha256` is hashed unredacted: a digest is not a reproduction, and
redacting first would make every candidate id depend on the redaction rules, so
tuning them would re-identify candidates whose content never changed.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from secrev.catalog import Catalog, Pattern
from secrev.ids import Match, assign
from secrev.inventory import FileEntry, language_of, walk

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


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """`paths_exclude` glob semantics, fixed here because nothing else fixes
    them.

    Neither stdlib option is right. `fnmatch` lets `*` cross `/`, so
    `**/test_*.py` would not match a top-level `test_x.py` while `tests/*`
    would match `tests/a/b.py`. `PurePath.match` does not treat `**` as
    recursive at all, and `PurePath.full_match` arrived in 3.13 while
    `STACK.md` §1 pins 3.11. So the translation is explicit:

        `**/`  any number of leading directory segments, including none
        `**`   anything, crossing `/`
        `*`    anything within one segment
        `?`    one character within one segment

    which is the semantics a reader of `tests/**` and `**/test_*.py` expects.
    The choice is visible in every golden file, so it is written down rather
    than inherited from whichever helper was reached for.
    """
    out: list[str] = []
    index = 0
    while index < len(glob):
        char = glob[index]
        if glob.startswith("**/", index):
            out.append("(?:[^/]+/)*")
            index += 3
        elif glob.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    return re.compile(f"^{''.join(out)}$")


def applies(pattern: Pattern, relative_path: str) -> bool:
    """Whether a rule runs against a file at all.

    §4: an empty or absent `languages` means "applies to all text". A language
    list is a false-positive reducer, not a prerequisite — which is why an
    unrecognised extension does not silently drop every language-scoped rule
    into "does not apply" without that being the honest answer.
    """
    for glob in pattern.paths_exclude:
        if _glob_to_regex(glob).match(relative_path):
            return False
    if not pattern.languages:
        return True
    return language_of(relative_path) in pattern.languages


def _file_hits(entry: FileEntry, text: str, catalog: Catalog) -> list[Hit]:
    lines = text.splitlines()

    found: list[tuple[int, str, int, int, Pattern]] = []
    for pattern in catalog.patterns:
        if not applies(pattern, entry.path):
            continue
        for index, line in enumerate(lines):
            for match in pattern.regex.finditer(line):
                found.append((index, pattern.id, match.start(), match.end(), pattern))

    # Total order before ids are assigned. Two matches of one rule on one line
    # stay two records (D-6) and are separated by column, never merged.
    found.sort(key=lambda item: (item[0], item[1], item[2]))

    matches = [
        Match(rule_id=rule_id, line=index + 1, window=window(lines, index))
        for index, rule_id, _, _, _ in found
    ]
    identifiers = assign(entry.path, matches)

    hits: list[Hit] = []
    for (index, rule_id, column, end, pattern), identifier in zip(found, identifiers, strict=True):
        hits.append(
            Hit(
                id=identifier,
                file=entry.path,
                line=index + 1,
                layer=pattern.layer[0],
                source="pattern",
                rule_id=rule_id,
                precision=pattern.precision,
                question=" ".join(pattern.question.split()),
                match_excerpt=excerpt(lines[index], column, end),
                status="unresolved",
                catalog_version=catalog.version,
                window_spec=WINDOW_SPEC,
            )
        )
    return hits


def sweep(root: Path, catalog: Catalog) -> list[Hit]:
    """Every candidate in `root`, in a deterministic order.

    Binary files are inventoried but never swept (`STACK.md` §5) — matching a
    regex against decoded binary produces hits that mean nothing and windows
    that hash differently on every platform. Symlinks are never followed; one
    escaping the root is a candidate in its own right, which is a closure
    question and belongs to the surface source in M2.
    """
    hits: list[Hit] = []
    for entry in walk(root):
        if entry.is_binary or entry.is_symlink:
            continue
        # `os_path`, never `path`: the record is NFC, the filesystem may not be.
        raw = (root / entry.os_path).read_bytes()
        hits.extend(_file_hits(entry, raw.decode("utf-8", errors="replace"), catalog))
    return hits
