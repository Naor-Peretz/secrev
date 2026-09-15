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

The record, its serialisation, the window and redaction live in `ledger.py`,
shared with the surface source so that neither source imports the other. What
stays here is what only patterns have: which rules apply to a file, and the
order their matches take before ids are assigned.
"""

from __future__ import annotations

from pathlib import Path

from secrev.catalog import Catalog, Pattern
from secrev.ids import Match, assign
from secrev.inventory import FileEntry, glob_to_regex, language_of, walk
from secrev.ledger import WINDOW_SPEC, Hit, excerpt, window


def applies(pattern: Pattern, relative_path: str) -> bool:
    """Whether a rule runs against a file at all.

    §4: an empty or absent `languages` means "applies to all text". A language
    list is a false-positive reducer, not a prerequisite — which is why an
    unrecognised extension does not silently drop every language-scoped rule
    into "does not apply" without that being the honest answer.
    """
    for glob in pattern.paths_exclude:
        if glob_to_regex(glob).match(relative_path):
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
