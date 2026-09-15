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


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:BINARY_SNIFF_BYTES]


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
    except OSError:
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


def _file_entry(root: Path, path: Path) -> FileEntry:
    raw = path.read_bytes()
    relative = str(path.relative_to(root))
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


def exclusions_applied(root: Path) -> list[str]:
    """Which excluded directories were actually present, sorted.

    Recorded rather than silent (STACK.md §5): "no findings under node_modules"
    and "node_modules was never read" are different statements, and a report
    that cannot distinguish them is claiming coverage it does not have.
    """
    found: set[str] = set()
    for current, dirnames, _ in os.walk(root):
        for name in list(dirnames):
            if name in EXCLUDED_DIRS:
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


def walk(root: Path) -> list[FileEntry]:
    """Every file under `root`, sorted on the POSIX path string.

    Raises rather than returning an empty list when the root is unusable. An
    empty inventory and an unreadable target must not look the same (H-1).
    """
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
            if name in EXCLUDED_DIRS:
                dirnames.remove(name)
            elif (here / name).is_symlink():
                dirnames.remove(name)
                entries.append(_symlink_entry(root, here / name))

        for name in filenames:
            path = here / name
            if path.is_symlink():
                entries.append(_symlink_entry(root, path))
            else:
                entries.append(_file_entry(root, path))

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
