"""The surface candidate source. BRIEF_M2.md, PRD P11, FR-3.9 to FR-3.11, D-11.

Every declaration a surface kind finds becomes a ledger record, `source:
"surface"`, whether or not any pattern or structural rule matched it. That is
the whole point of the source: detection must not decide scope (P11). Where
patterns alone decide what gets read, logic with no syntactic signature is never
examined and the catalog silently sets the boundary of the review (FR-3.10).
A surface record says *this entry point is reachable — trace it to its sinks*.

Nothing here concludes anything. Every record is `unresolved`, and "nothing
matched here" does not resolve it (FR-3.11). Like `sweep.py` this returns
records and writes nothing; `cli.py` owns output (G-4).

It is a peer of `sweep.py`, not a stage after it. It imports neither the
pattern source nor the catalog: what the two share lives in `ledger.py`, and a
source that can see another source's module is one refactor away from seeing
its results (TASKS_M2.md Q2).

The rules that decide bytes, stated because they are the ones not to revise:

  **What a surface is comes from data.** `surfaces/_surfaces.yaml`, loaded by
  `kinds.py`: which files a kind looks in and which line declares it (NFR-6).
  This module holds no knowledge of any particular kind.

  **Line-oriented** (TASKS_M2.md Q3). One declaration line is one surface for
  a kind; two kinds on one line are two records (D-6). A declaration spanning
  lines is a recorded coverage gap.

  **The excerpt is the declaration line**, redacted (G-3). Nothing matched, so
  there is no matched span; the line is what makes the entry point reachable
  (BRIEF_M2.md §3).

  **The window is `decl-20`** — `lines-20`'s span under a name of its own
  (STACK.md §5, TASKS_M2.md C-2).

  **Order is total before ids are assigned**: files arrive sorted from
  `inventory.walk`, and within a file records sort by `(line, rule_id)`. The
  ordinal inside an id counts over byte-identical windows, so an unstable order
  would give the same content different ids on two runs.

  **`catalog_version` carries the kinds file's `version`** — decided, not
  defaulted (Q4, owner, 2026-09-16). The field holds the version of whichever
  ruleset produced the record, so a change to a kind expires the verifications
  made against it exactly as FR-3.12 does for a pattern, and nothing reading
  the ledger has to branch on `source` first. The name is the PRD's and fits
  half the records; renaming it is a PRD correction, raised in TASKS_M2.md.
"""

from __future__ import annotations

from pathlib import Path

from secrev.ids import Match, assign
from secrev.inventory import FileEntry, split_lines, walk
from secrev.kinds import Kind, Kinds
from secrev.ledger import DECL_WINDOW_SPEC, Hit, excerpt, window


def _file_hits(entry: FileEntry, text: str, kinds: tuple[Kind, ...], version: str) -> list[Hit]:
    lines = split_lines(text)

    found: list[tuple[int, str, Kind]] = []
    for kind in kinds:
        for index, line in enumerate(lines):
            if kind.declaration.search(line):
                found.append((index, kind.id, kind))

    # Total order before ids are assigned: by line, then rule id. Iterating
    # kind by kind emits in kind order, which is stable within one run and
    # wrong against the rule — `tests/test_surfaces.py` asserts the order itself.
    found.sort(key=lambda item: (item[0], item[1]))

    # One window per line, shared by every match on it — the same change
    # `sweep.py` carries, and for the same reason. A peer source pays the same
    # cost, so it gets the same fix rather than waiting to be measured
    # separately.
    windows: dict[int, str] = {}
    matches: list[Match] = []
    for index, rule_id, _ in found:
        text_window = windows.get(index)
        if text_window is None:
            text_window = window(lines, index)
            windows[index] = text_window
        matches.append(Match(rule_id=rule_id, line=index + 1, window=text_window))
    identifiers = assign(entry.path, matches)

    hits: list[Hit] = []
    for (index, rule_id, kind), identifier in zip(found, identifiers, strict=True):
        declaration = lines[index]
        hits.append(
            Hit(
                id=identifier,
                file=entry.path,
                line=index + 1,
                layer=kind.layer,
                source="surface",
                rule_id=rule_id,
                precision=kind.precision,
                question=" ".join(kind.question.split()),
                match_excerpt=excerpt(declaration, 0, len(declaration)),
                status="unresolved",
                catalog_version=version,
                window_spec=DECL_WINDOW_SPEC,
            )
        )
    return hits


def surfaces(
    root: Path,
    kinds: Kinds,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> list[Hit]:
    """Every surface candidate in `root`, in a deterministic order.

    `excluded` is threaded to `inventory.walk`; `None` means the default set
    (M3.5 A2). A peer source must skip exactly what the pattern source skips,
    or an override would change scope for one and not the other.

    Binary files are inventoried but never read, and symlinks are never
    followed (`STACK.md` §5) — exactly as in the pattern source. A symlink
    escaping the root is a closure question, not a surface (TASKS_M2.md Q7).
    """
    hits: list[Hit] = []
    for entry in walk(root, excluded, max_bytes):
        # `inventory` already tried; this does not try again (M3.5 C2 — the
        # second read is what raised out of the run). A peer source must skip
        # exactly what the pattern source skips, or the two disagree about
        # scope and only one of them says so.
        #
        # The same carried-forward window `sweep.py` describes applies here, and
        # for the same reason: what is carried forward is the decision, not the
        # read. See the note there; a peer source inherits the limit as well as
        # the rule.
        if (
            entry.is_binary
            or entry.is_symlink
            or not entry.is_readable
            or not entry.is_regular
            or not entry.is_within_size_bound
        ):
            continue
        applicable = tuple(kind for kind in kinds.kinds if kind.applies(entry.path))
        if not applicable:
            continue
        # `os_path`, never `path`: the record is NFC, the filesystem may not be.
        raw = (root / entry.os_path).read_bytes()
        text = raw.decode("utf-8", errors="replace")
        hits.extend(_file_hits(entry, text, applicable, kinds.version))
    return hits
