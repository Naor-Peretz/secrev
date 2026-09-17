"""Candidate identity. STACK.md §5, serving PRD FR-4.5 and FR-4.6.

The id is the thread a verification hangs on between reviews. FR-4.6 matches
this run's candidates against the last run's by id: one that moved reads as a
`vanished` hit, whose adjudication is thrown away, plus a new `unresolved` one
demanding fresh work — for code nobody touched. So every component here earns
its place by answering a question that must change the identity, and nothing
else is allowed in.

  `relative_path`   identity is per location; two files with identical content
                    hold two findings, and resolving one says nothing about
                    the other.
  `rule_id`         D-6: two patterns matching one line are two hits, and two
                    findings if both are real.
  `window_sha256`   "did this content change" — the question FR-4.6
                    invalidates on. Inside the id, so that is structural
                    rather than a separate check someone can forget.
  `ordinal`         only because D-6 requires two byte-identical matches in
                    one file to stay two candidates, and nothing in their
                    content can tell them apart.

`line` is deliberately absent, and `derive()` rejects it rather than ignoring
it — a caller passing it has the old model in mind, and silently dropping the
argument would let that belief survive. FR-4.5: a verification "anchored only
to a line number is lost the moment the content moves", and one added import
shifts every line below it.

The `ordinal` ranges over byte-identical windows only, never over every match
of the rule in the file. A file-wide counter moves when an unrelated match of
the same rule is added or deleted; a counter within an identical-window group
moves only when a genuinely indistinguishable twin is added or deleted, which
is the irreducible residue recorded in STACK.md §5.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

ID_LENGTH = 16


@dataclass(frozen=True)
class Match:
    """One pattern hit, before it has an identity.

    `line` is carried for a reader locating the hit and takes no part in the
    id. It is on the record because a candidate a human cannot find is not
    useful; it is out of the identity because it moves for reasons that have
    nothing to do with the candidate.
    """

    rule_id: str
    line: int
    window: str


def window_sha256(window: str) -> str:
    """SHA-256 over the NFC-normalised, LF-normalised window text.

    No filename, no line number, no timestamp in the input (STACK.md §5): the
    hash answers "did this content change", and must not fire when the content
    merely moved. That is also why it can sit inside the id.
    """
    text = window.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode("utf-8")).hexdigest()


def derive(*, relative_path: str, rule_id: str, window: str, ordinal: int) -> str:
    """The id for one candidate.

    Keyword-only and without defaults on the identifying components: silently
    defaulting one collapses two candidates onto a single id, which loses a
    finding rather than duplicating one (H-1). There is no `line` parameter,
    and adding one would be a STACK.md §5 amendment rather than a convenience.

    The separator is NUL because it cannot occur in any of the components, so
    no pair of distinct inputs can produce one string.
    """
    return _id_from_digest(
        relative_path=relative_path,
        rule_id=rule_id,
        window_digest=window_sha256(window),
        ordinal=ordinal,
    )


def _id_from_digest(*, relative_path: str, rule_id: str, window_digest: str, ordinal: int) -> str:
    """`derive()` with the window already hashed.

    Split out so `assign` can hash a window **once** and use the result twice:
    for the ordinal's group key and for the id. It used to hash the same window
    in both places, and `window()` rebuilt that window per match on top of that
    — three passes over the same text, per candidate.

    That is invisible in ordinary files and quadratic on a crafted one. A single
    200 KB line matching 20,000 times is 20,000 windows of ~200 KB each, built
    and hashed twice apiece. The catalog was made linear in the previous pass
    and the cost simply moved here, where a regex timing test cannot see it.

    **No identity changes.** The bytes fed to SHA-256 are the same four
    components in the same order with the same separator; only the number of
    times the window digest is computed differs.
    """
    parts = (relative_path, rule_id, window_digest, str(ordinal))
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return digest[:ID_LENGTH]


def assign(relative_path: str, matches: list[Match]) -> list[str]:
    """Ids for every match in one file, in the order given.

    The ordinal is computed here rather than supplied, and it counts within a
    group of byte-identical windows. A match whose window is unique in the
    file is always ordinal 0, so another match of the same rule appearing or
    vanishing elsewhere cannot disturb it.

    Each distinct window is hashed once. The sources hand every match on one
    line the *same* string object, so this cache is keyed on a string whose hash
    Python has already computed and stored — the lookup does not re-read the
    text. Without that sharing the cache would still be correct and would cost
    what it saves, which is why the memoisation here and in the two sources is
    one change rather than two.
    """
    seen: dict[tuple[str, str], int] = {}
    digests: dict[str, str] = {}
    assigned: list[str] = []
    for item in matches:
        digest = digests.get(item.window)
        if digest is None:
            digest = window_sha256(item.window)
            digests[item.window] = digest
        group = (item.rule_id, digest)
        ordinal = seen.get(group, 0)
        seen[group] = ordinal + 1
        assigned.append(
            _id_from_digest(
                relative_path=relative_path,
                rule_id=item.rule_id,
                window_digest=digest,
                ordinal=ordinal,
            )
        )
    return assigned
