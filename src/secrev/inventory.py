"""The deterministic file walk. STACK.md §5, implementing NFR-3.

This is the first module in the package on purpose. `recon.py` and `sweep.py`
are both consumers of the walk, so every rule fixed here they inherit, and
every rule got wrong here they would each have to work around. These are also
the decisions that cannot be corrected afterwards: a hash that changes because
a filename was stored in a different normalisation invalidates verifications
recorded months earlier, and nothing about the failure points at Unicode (D-4).

The rules, and what each one is actually defending against:

  Traversal order — collect, then sort on the POSIX path string. `os.walk`
  order is stable on one machine and one filesystem, which is precisely why
  emitting it survives review and then diverges in CI.

  Path normalisation — NFC before use, comparison or hashing. Not because
  "macOS gives NFD": APFS preserves whatever normalisation it was given and is
  merely insensitive on lookup, and it was HFS+ that stored a decomposed form.
  The rule is needed because decomposed names exist and travel — authored on
  HFS+, or by a tool that emits NFD — and survive onto any filesystem. See
  STACK.md §5, which carries the correction and the one divergence normalising
  cannot fix.

  Line endings — CRLF to LF before hashing, line numbers against the original.
  A checkout with autocrlf on must not invalidate the whole ledger.

  Symlinks — recorded, never followed. One pointing outside the root is a
  finding in its own right rather than a file to read (P9).

  Exclusions — applied, and recorded as applied. A reader cannot tell an empty
  `.git/` from a skipped one unless told.

  Binary — a NUL byte in the first 8 KiB, never the extension. Inventoried,
  not swept.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# STACK.md §5. Directory names, matched exactly, at any depth.
#
# Exact names rather than a `.venv*` / `*_cache` pattern: a pattern is a
# denylist over a shape (P3), while a named directory is auditable and is
# reported verbatim in `recon.json`. The tool caches and `.venv-audit` were
# added after the first recon against a real repository reported 1952 files
# and 703,763 lines for this one — see §5, which carries the reasoning.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        ".venv-audit",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".tox",
        ".nox",
        ".eggs",
    }
)

BINARY_SNIFF_BYTES = 8192

# STACK.md §5. A file larger than this is inventoried, recorded as skipped, and
# never read.
#
# Not a defence against superlinear time, which no longer exists: M3.5 made
# `log.sensitive` linear, and the shipped catalog measures linear in every
# shape tried. This bounds what a *hostile file* can cost — 9.6 MB of crafted
# lines measured 14 seconds.
#
# 5 MiB because the bound's own cost is a coverage gap. Real source is rarely
# this large and minified bundles can be, so a tighter cap would hide exactly
# the shipped artifact a reviewer most needs to open. At ~1.7 ms/KiB worst
# case this bounds a hostile file at roughly 8 seconds.
MAX_FILE_BYTES = 5 * 1024 * 1024

# Extension to language. One map, owned here, because two consumers need the
# identical answer and a second copy would drift: `recon.py` reports
# `by_language`, and `sweep.py` decides whether a pattern carrying
# `languages: [python]` applies to a file. If those two disagreed about what
# "python" means, a rule would be reported as covering a file it never ran
# against — a coverage claim with nothing behind it, which is the failure this
# project exists to notice.
#
# Extension only, deliberately. Shebang sniffing would make the answer depend
# on file content and give an extensionless script a language on one machine
# and not another; `recon.json` is a deterministic artifact (NFR-3), so the
# classification has to be a pure function of the path.
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".txt": "text",
    ".cfg": "ini",
    ".ini": "ini",
}


def language_of(path: str) -> str | None:
    """The language for a relative POSIX path, or None when unrecognised.

    None rather than a guess: an unknown extension is a real state, and
    `recon.json` reports it as one. Inventing "text" for everything would make
    the coverage-gap line (FR-3.8) claim reach the tool does not have.
    """
    suffix = path[path.rfind(".") :].lower() if "." in path.rsplit("/", 1)[-1] else ""
    return LANGUAGE_BY_SUFFIX.get(suffix)


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Glob semantics for relative POSIX paths, fixed here because nothing else
    fixes them.

    Here rather than in a candidate source because two sources need the
    identical answer: `paths_exclude` in the catalog and `files` in the surface
    kinds. A second copy would be a second meaning of `**`, and a kind and a
    pattern reading the same glob differently is a coverage claim with nothing
    behind it — the same reason `language_of` lives here.

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


def split_lines(text: str) -> list[str]:
    """`text` split into lines the way an editor counts them: at CRLF, CR and
    LF, and nowhere else. The terminators are discarded.

    One definition for every consumer of the walk, here beside `language_of`
    and `glob_to_regex` for their reason: a pattern's line, a surface's line
    and `recon.json`'s line count must agree, and a second copy would drift.

    Not `str.splitlines`, which also breaks on vertical tab and form feed
    (U+000B, U+000C), U+001C to U+001E, U+0085, U+2028 and U+2029. A form
    feed — `^L`, which Python source does contain — would shift every later
    line number and window against what an editor shows, and `STACK.md` §5
    says line numbers are reported against the original. Found in the
    TASK-M2-007 review; fixed by owner decision.

    Discarding the terminators keeps the other half of §5: a window joined
    with LF is the same bytes whatever the file used, so a checkout with
    `autocrlf` on does not re-identify every candidate.
    """
    parts = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if parts[-1] == "":
        parts.pop()
    return parts


@dataclass(frozen=True, order=True)
class FileEntry:
    """One inventoried path. Frozen so equality is the whole record.

    `path` is relative to the target root, POSIX-separated and NFC-normalised.
    Never absolute: an absolute path in a deterministic output makes the result
    depend on where the target happened to be checked out.
    """

    path: str
    size: int
    is_binary: bool
    is_symlink: bool
    symlink_target: str | None
    escapes_root: bool
    sha256: str | None

    # False when the file is there and the tool was not permitted to read it.
    #
    # Recorded rather than skipped, and rather than raised. Raising was the
    # M3.5 finding: one `chmod 000` file ended the walk, so a target could hide
    # an entire tree behind a single unreadable file. Skipping silently would
    # be worse — "I did not read this file" and "I read it and found nothing"
    # are different states, and collapsing them is the H-1 failure this project
    # exists to notice, turned on the tool instead of on the harness.
    #
    # `sha256` is None and `is_binary` is False on such an entry, because both
    # would otherwise be claims about bytes nobody saw.
    is_readable: bool = True

    # False for a FIFO, socket, device or anything else that is not a regular
    # file. Its own field rather than a second meaning for `is_readable`:
    # "permission denied" and "not a regular file" are different facts, and a
    # reviewer reading `recon.json` needs to tell them apart. M3.5-002's
    # receipt said this case would reuse `is_readable`; that was wrong, and the
    # Definition of done asks specifically for "not-a-regular-file".
    #
    # This is the field that stops a target hanging the review. Opening a FIFO
    # with no writer blocks forever — nothing raised, nothing timed out — so
    # `_file_entry`'s `except OSError` could never reach it. The check has to
    # happen *before* the read, not around it.
    is_regular: bool = True

    # False when the file exceeds the size bound and was therefore not read.
    #
    # Its own field rather than folded into the two above, for the reason
    # M3.5-006 set out when `is_regular` was split from `is_readable`:
    # "permission denied", "not a regular file" and "too large to read" are
    # three different facts, and a reviewer needs to know which one applies
    # before deciding what to do about it. One is a mode they might change,
    # one is a thing with no content, and this one is a threshold they can
    # raise with `--max-file-bytes`.
    #
    # `size` is real on such an entry — it comes from `lstat`, which needs no
    # read — but `sha256` is None, because the bytes were never seen.
    is_within_size_bound: bool = True

    # The name the OS actually reported, native separators, NOT normalised —
    # the only string that will reopen the file.
    #
    # `compare=False` because it is not part of the record. `path` is NFC so
    # that two machines describe one tree identically; `os_path` is whatever
    # bytes that machine's filesystem holds, and two trees differing only in
    # stored normalisation are the same inventory. Including it in equality
    # would make the record machine-dependent, which is the exact property NFC
    # exists to remove.
    #
    # Reopening by `path` instead is a real bug and was one: on ext4 an NFD
    # filename simply does not exist under its NFC spelling, so the read raises
    # — while on APFS, which matches either form, the same code silently works.
    # A defect that fails only on the platform without the forgiving filesystem
    # is the kind cross-platform CI is for.
    os_path: str = field(default="", compare=False)


def normalise_path(value: str) -> str:
    """NFC, and POSIX separators. Applied before comparison, sorting or
    hashing — sorting a decomposed string against a composed one orders them
    differently, so normalising after the sort would not be enough."""
    return unicodedata.normalize("NFC", value.replace(os.sep, "/"))


# Below this, a byte is a C0 control and is non-text unless named below.
_PRINTABLE_FLOOR = 0x20

# C0 controls that occur in ordinary text, and so are not evidence of a binary
# file: tab, newline, vertical tab, form feed, carriage return, escape, and the
# file/group/record separators U+001C-U+001E. A rule counting every control
# byte would call a CRLF file full of tabs binary.
#
# The separators are here because `split_lines` already says so. It
# deliberately does *not* break on U+001C-U+001E, which is a statement that
# they occur inside real text — so if this set disagreed, the line splitter and
# the binary detector would hold two different definitions of "text" and drift
# apart, the failure `glob_to_regex` and `language_of` are centralised to
# prevent. Omitting them was caught by `tests/test_lines.py`, and only by its
# smallest fixture: six bytes carrying one separator is 16.7% non-text, while
# the sibling tests' ~33-byte files were 3% and passed. A proportion rule is
# size-sensitive, and small files are where it bites.
_TEXT_CONTROLS = frozenset({0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1B, 0x1C, 0x1D, 0x1E})

# STACK.md §5. Strictly exceeding, so exactly 5% is text — a threshold written
# as "5%" and implemented as `>=` moves the line silently, and every text file
# in the fixture tree measures 0.00%, so nothing else would notice.
NON_TEXT_LIMIT = 0.05


def is_binary(data: bytes) -> bool:
    """Binary when non-text bytes exceed 5% of the first 8 KiB (STACK.md §5).

    This was `b"\\x00" in data[:8192]` until M3.5, and that was a one-byte
    scope evasion: binary means "not swept and not read by the surface source",
    so a target that put a single NUL in a comment in `install.sh` removed the
    whole file from review. P11 says detection must not decide scope, and one
    byte chosen by the target decided it — after which the review reported
    nothing found there rather than reporting that it had not looked.

    The threshold was measured, not chosen. Every text file in the fixture tree
    is 0.00% non-text; the smallest committed binary is 8.51%; a real PNG
    header run is 90.28%; the crafted `install.sh` is 3.33%. 5% sits in the
    empty gap, which is why no fixture changes classification.

    Still a pure function of the first 8 KiB, so NFR-3 holds: the answer cannot
    vary by machine, and no file's `sha256` changes hands between the text and
    bytes branches of `content_sha256` as a result of this change.
    """
    window = data[:BINARY_SNIFF_BYTES]
    if not window:
        # An empty file is text. It has no content to be binary.
        return False
    non_text = sum(1 for byte in window if byte < _PRINTABLE_FLOOR and byte not in _TEXT_CONTROLS)
    return non_text / len(window) > NON_TEXT_LIMIT


def content_sha256(raw: bytes) -> str:
    """SHA-256 over the NFC-normalised, LF-normalised text.

    Binary content is hashed as bytes: decoding it would be a guess, and the
    question a binary hash answers is only "did these bytes change".
    """
    if is_binary(raw):
        return hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode("utf-8")).hexdigest()


def _escapes(root: Path, link: Path) -> bool:
    """True when a symlink resolves outside the target root.

    The link is never followed to read content; this only asks where it points,
    which is a property of the closure rather than of the file (P9).
    """
    target = link.readlink()
    if not target.is_absolute():
        target = link.parent / target
    try:
        resolved = target.resolve()
    except (OSError, RuntimeError):
        # `RuntimeError` is not a kind of `OSError`. On CPython 3.12 a symlink
        # loop raises `RuntimeError("Symlink loop from ...")`, and
        # `isinstance(that, OSError)` is False — checked against the
        # interpreter, not taken from a report — so `except OSError` alone let
        # it travel to `cli._run`'s generic handler and become exit 3: a fact
        # about the target reported as a bug in this tool (M3.5 C2).
        #
        # The polarity is deliberately unchanged. A link that cannot be
        # resolved is recorded as leaving the tree, which makes it a question
        # rather than a silence (P9); assuming it stays inside would be a guess
        # in the direction that produces no candidate.
        return True
    return not resolved.is_relative_to(root.resolve())


def _symlink_entry(root: Path, link: Path) -> FileEntry:
    return FileEntry(
        path=normalise_path(str(link.relative_to(root))),
        size=link.lstat().st_size,
        is_binary=False,
        is_symlink=True,
        symlink_target=normalise_path(str(link.readlink())),
        escapes_root=_escapes(root, link),
        sha256=None,
        os_path=str(link.relative_to(root)),
    )


def _file_entry(root: Path, path: Path, max_bytes: int | None = None) -> FileEntry:
    relative = str(path.relative_to(root))

    # Tested before the read, never around it. Opening a FIFO with no writer
    # blocks forever: nothing is raised and nothing times out, so no `except`
    # clause can reach it, and one named pipe in a target hangs the review
    # indefinitely. `is_file()` stats, and stat never opens.
    #
    # Symlinks are routed to `_symlink_entry` before this, so on a path that
    # reaches here `is_file()` is exactly `S_ISREG`. It also returns False for
    # a path that cannot be stat'd at all, which folds "cannot stat" into "not
    # a regular file" — said plainly because it is a real conflation, and
    # tolerable only because `os.walk` just listed this entry, so the directory
    # was readable a moment ago.
    #
    # `size` is 0 rather than `lstat().st_size`: a FIFO's size is not a length
    # of content, and reporting one would be a number with nothing behind it.
    if not path.is_file():
        return FileEntry(
            path=normalise_path(relative),
            size=0,
            is_binary=False,
            is_symlink=False,
            symlink_target=None,
            escapes_root=False,
            sha256=None,
            is_regular=False,
            os_path=relative,
        )

    # Before the read, like the regular-file test above it. `lstat` gives the
    # size without opening anything, so an oversized file costs a stat rather
    # than however long reading it would have taken — which is the entire point
    # of the bound.
    size = path.lstat().st_size
    if size > (MAX_FILE_BYTES if max_bytes is None else max_bytes):
        return FileEntry(
            path=normalise_path(relative),
            size=size,
            is_binary=False,
            is_symlink=False,
            symlink_target=None,
            escapes_root=False,
            sha256=None,
            is_within_size_bound=False,
            os_path=relative,
        )

    try:
        raw = path.read_bytes()
    except OSError:
        # The file is there and this process may not read it. Recorded —
        # neither raised nor skipped.
        #
        # Raising was the M3.5 finding: `PermissionError` left `walk()` and
        # ended the review of every other file, so a target could hide an
        # entire tree behind one `chmod 000`. Skipping would report the file as
        # absent, which is the same lie told more quietly.
        #
        # `size` comes from `lstat`, which needs no read. Nothing else is
        # claimed: no hash, and not binary, because either would be an
        # assertion about bytes nobody saw.
        return FileEntry(
            path=normalise_path(relative),
            size=path.lstat().st_size,
            is_binary=False,
            is_symlink=False,
            symlink_target=None,
            escapes_root=False,
            sha256=None,
            is_readable=False,
            os_path=relative,
        )
    return FileEntry(
        path=normalise_path(relative),
        size=len(raw),
        is_binary=is_binary(raw),
        is_symlink=False,
        symlink_target=None,
        escapes_root=False,
        sha256=content_sha256(raw),
        os_path=relative,
    )


def exclusions_applied(root: Path, excluded: frozenset[str] | None = None) -> list[str]:
    """Which excluded directories were actually present, sorted.

    Recorded rather than silent (STACK.md §5): "no findings under node_modules"
    and "node_modules was never read" are different statements, and a report
    that cannot distinguish them is claiming coverage it does not have.

    `excluded` is a parameter rather than a constant read directly, so a caller
    can narrow the set (M3.5 A2). Reporting what was skipped tells a reviewer a
    gap exists; being able to override it is what lets them close it.
    """
    names = EXCLUDED_DIRS if excluded is None else excluded

    found: set[str] = set()
    for current, dirnames, _ in os.walk(root):
        for name in list(dirnames):
            if name in names:
                found.add(f"{name}/")
                dirnames.remove(name)
        del current
    return sorted(found)


class NormalisationCollision(ValueError):
    """Two files whose names differ only by Unicode normalisation.

    A `ValueError` so `cli.py` reports it as exit 2: the tool worked and the
    target cannot be reviewed as it stands, which is a fact about the input.

    Refusing is not conservatism. Both names normalise to one `path`, so the
    two files become one record, and two candidates with identical content then
    derive the *same id* — verified against `tests/test_determinism.py`. Under
    P4 that means resolving one candidate silently resolves the other, and a
    verification recorded against one file is applied to content nobody read.
    A wrong merge losing a question is the failure D-6 exists to prevent; this
    is that, plus a verification transferring to unreviewed bytes.

    It cannot be engineered away either, and that is why this refuses rather
    than disambiguating. APFS will not hold both variants in one directory at
    all, so any scheme that told them apart would produce an inventory that
    exists on Linux and cannot exist on macOS — trading a silent collision for
    a guaranteed cross-platform divergence (`STACK.md` §5).
    """


def walk(
    root: Path,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> list[FileEntry]:
    """Every file under `root`, sorted on the POSIX path string.

    Raises rather than returning an empty list when the root is unusable. An
    empty inventory and an unreadable target must not look the same (H-1).

    `excluded` is a parameter so a caller can narrow the set (M3.5 A2).
    Reporting what was skipped tells a reviewer that a gap exists; being able
    to override it is what lets them close it. `None` means `EXCLUDED_DIRS`,
    which is what `STACK.md` §5 fixes — spelled as `None` rather than as the
    constant so that `sweep`, `surfaces` and `recon` can thread the argument
    through without importing it, since a default naming an unimported constant
    is a `NameError` at definition time.

    Overriding is a decision the caller makes and `recon.json` records, because
    the applied set is reported rather than assumed.
    """
    names = EXCLUDED_DIRS if excluded is None else excluded

    if not root.exists():
        raise FileNotFoundError(f"target root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"target root is not a directory: {root}")

    entries: list[FileEntry] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(current)

        # Mutating dirnames in place is how os.walk is told not to descend.
        # A symlinked directory is recorded and not entered: following it
        # would read outside the closure and could loop.
        for name in list(dirnames):
            if name in names:
                dirnames.remove(name)
            elif (here / name).is_symlink():
                dirnames.remove(name)
                entries.append(_symlink_entry(root, here / name))

        for name in filenames:
            path = here / name
            if path.is_symlink():
                entries.append(_symlink_entry(root, path))
            else:
                entries.append(_file_entry(root, path, max_bytes))

    # Collect, then sort. Never emit in traversal order (STACK.md §5).
    ordered = sorted(entries, key=lambda entry: entry.path)

    # Two names that differ only by normalisation collapse to one `path`, and
    # from there to one candidate id. Checked after sorting so the colliding
    # pair is adjacent and the message can name both spellings.
    seen: dict[str, str] = {}
    for entry in ordered:
        if entry.path in seen and seen[entry.path] != entry.os_path:
            raise NormalisationCollision(
                f"{root}: two files differ only by Unicode normalisation and both "
                f"normalise to {entry.path!r} — on disk they are {seen[entry.path]!r} "
                f"and {entry.os_path!r}.\n"
                "They would share one record and, with equal content, one candidate id, "
                "so resolving one would resolve the other and a verification would apply "
                "to a file nobody read (P4, D-6). macOS cannot hold both in one directory, "
                "so there is no spelling of this inventory that is stable across platforms "
                "(STACK.md §5).\n"
                "Rename one, or review the two directories separately."
            )
        seen[entry.path] = entry.os_path

    return ordered
