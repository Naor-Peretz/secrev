"""Target reconnaissance. BRIEF_M1.md §3, FR-1.1.

Produces the `recon.json` shape and nothing else. It is a peer of `sweep.py`,
not a stage before it: neither imports the other, and both consume
`inventory.walk`. That separation is P11 in the file layout — if recon could
see what the catalog matched, what gets reported as covered would start
depending on what happened to be detected.

Like `sweep.py` this returns data and writes nothing. `cli.py` owns output.

**No subprocess, anywhere.** `STACK.md` §1 permits shelling out to `git`, and
this module does not take that permission. The version and SHA are read
straight out of `.git/` with `pathlib`, which costs about fifteen lines and
buys three things: the codebase keeps the property that it contains no
subprocess call at all, which is the cleanest possible answer when the tool
reviews itself under AC-10; there is no `PATH` lookup, so the result cannot
depend on which `git` is installed; and it cannot block, which matters because
NFR-4 forbids network egress and a misconfigured `git` can reach for one.

It degrades honestly rather than guessing. A tree that is not a checkout, a
worktree file, an unreadable ref: each yields `source: "directory"` and a null
SHA, which is a true statement, instead of an inferred version that would end
up in the workspace path and silently split one target's history in two.

**What `loc_total` counts** is fixed here because nothing else fixes it, and it
is bytes in a deterministic artifact: lines in text files, counted with
`inventory.split_lines` — the same lines the candidate sources number, and the
ones an editor shows — excluding binaries and symlinks. Binaries have no lines, and a
symlink's content is the file it points at, which is counted once at its own
path or lies outside the tree entirely.
"""

from __future__ import annotations

import json
import re
import tomllib
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from secrev.inventory import FileEntry, exclusions_applied, language_of, split_lines, walk

# Files whose name marks them as tests, for `security_process.test_files`.
_TEST_FILE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test)\.[a-z]+$|(^|/)tests?/")

_SAST_CONFIG = (
    ".github/workflows/codeql.yml",
    ".github/workflows/codeql.yaml",
    ".semgrep.yml",
    ".semgrep.yaml",
    ".bandit",
)


@dataclass(frozen=True)
class Recon:
    target: dict[str, Any]
    inventory: dict[str, Any]
    entrypoints: dict[str, Any]
    security_process: dict[str, Any]
    coverage_gaps: list[str]


def slug(name: str) -> str:
    """A target slug: accents folded to ASCII, lowercased, the rest collapsed
    to `-`.

    It becomes a directory name in the workspace (`STACK.md` §6), so it must be
    the same string on every platform and must not carry anything a filesystem
    will reinterpret.

    Decomposing and dropping combining marks — rather than normalising to NFC
    and letting the accented characters fall into the non-alphanumeric bucket —
    makes NFC and NFD inputs converge by construction instead of by both being
    mangled the same way. It is also the difference between `café` slugging to
    `cafe` and to `caf-`, and the slug is what a person reads when they go
    looking for a review in `~/.security-review/`.

    It is a label, not an identity. Any lossy transform collides — `café` and
    `cafe` slug alike here, as `café` and `caf x` did before — and the workspace
    tolerates that because the path is `<slug>/<version>/` and the version is a
    SHA. Nothing downstream may treat the slug as distinguishing two targets.
    """
    folded = unicodedata.normalize("NFKD", name).lower()
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only)).strip("-") or "target"


def _found_paths(entries: list[FileEntry]) -> frozenset[str]:
    """Relative paths the walk itself found, as regular non-symlink files.

    The structural half of the M3.5 D1 fix, and the reason that fix needed a
    second pass. D1 added `and not ...is_symlink()` at each site a review had
    demonstrated — `pyproject.toml`, `package.json`, `.git`, `.git/HEAD` — and
    left `SECURITY.md`, `dependabot.yml`, `dependabot.yaml`, `_SAST_CONFIG` and
    the `.github/workflows` glob reaching by name with no check at all. A second
    review walked through every one of them.

    Patching each site cannot close this class, because the class is *reaching
    by name*: every new field that looks up a file is a new hole, and the check
    has to be remembered rather than inherited. `inventory.walk` has never
    followed a symlink, so a membership test against what it found is contained
    by construction — and a site that forgets to use it fails closed, reporting
    a file as absent rather than reading one outside the tree.

    `is_regular` and not a symlink, deliberately not `is_readable`: a file that
    exists and cannot be read is still *present*, and the fields built from this
    set answer presence. The two that go on to read a file handle their own
    `OSError` already.
    """
    return frozenset(item.os_path for item in entries if item.is_regular and not item.is_symlink)


def _within_real_path(base: Path, relative: str) -> Path | None:
    """`base/relative`, or None when any component of it is a symlink.

    For `.git` only. Everything else is answered by `_found_paths`, but `.git`
    is excluded from the walk, so nothing found it and there is no membership to
    test — the one place a by-name reach is unavoidable.

    Every component, not the last one. `is_symlink()` on the finished path
    lstats only the final element, so `.git/refs -> ../../outside/refs` passed a
    check written on `.git/refs/heads/main`: a foreign repository's SHA was
    reported as this target's version, and `STACK.md` §6 then filed the review
    under it. That is the D1 damage exactly, reached through a component nobody
    was looking at.

    Walked component by component rather than with `resolve()`, for the reason
    `_resolve_ref` gives below: `resolve()` follows links, which is the thing
    being defended against, and it raises `RuntimeError` on a loop.
    """
    current = base
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return None
    return current


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """A ref's SHA from a loose file, then from `packed-refs`.

    **The ref comes from the target's own HEAD**, so it is attacker-chosen
    input to a path join. Until M3.5 it was joined verbatim: a target writing
    `ref: ../../escape` walked straight out of the tree, and if the file it
    landed on held 40 hex characters they were reported as the target's
    version. No symlink needed — the target supplies the path directly. This
    tool ships `path.traversal` as a rule, so being subject to it is the
    self-application failure AC-10 exists to prevent.

    Checked as a string rather than with `resolve()`. `resolve()` follows
    symlinks, which is the thing being defended against, and M3.5-002 already
    established that it raises `RuntimeError` on a symlink loop — a containment
    check that can be hung by the tree it is containing is not a check.
    """
    if ref.startswith("/") or ".." in Path(ref).parts:
        return None

    # Every component checked, not just the last: see `_within_real_path`. The
    # previous form tested `loose.is_symlink()`, which lstats one element and
    # says nothing about the directories above it.
    loose = _within_real_path(git_dir, ref)
    if loose is not None and loose.is_file():
        return loose.read_text(encoding="utf-8").strip() or None

    packed = _within_real_path(git_dir, "packed-refs")
    if packed is not None and packed.is_file():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name.strip() == ref:
                return sha.strip()
    return None


def git_identity(root: Path) -> tuple[str, str | None]:
    """`(source, sha)` for the target tree.

    `("git", "<40 hex>")` for a checkout, `("directory", None)` for anything
    else — including a checkout this cannot read, because "I could not tell"
    and "it is not a repository" are both better answers than a fabricated one.
    """
    git_dir = root / ".git"
    # A symlinked `.git` is refused before anything else. `is_dir()` follows
    # the link, so a target pointing `.git` at another checkout had that
    # repository's HEAD read and its SHA reported as this target's version —
    # and `STACK.md` §6 makes the version a directory in the workspace, so one
    # tree's review would have been filed under another's history (M3.5 D1).
    if git_dir.is_symlink():
        return ("directory", None)
    if git_dir.is_file():
        # A worktree or submodule: `.git` is a file pointing elsewhere. Not
        # followed — the pointer leaves the target tree, and P9 makes that a
        # question rather than a path to chase silently.
        return ("directory", None)
    if not git_dir.is_dir():
        return ("directory", None)

    head = git_dir / "HEAD"
    if head.is_symlink() or not head.is_file():
        return ("directory", None)

    text = head.read_text(encoding="utf-8", errors="replace").strip()
    sha = _resolve_ref(git_dir, text[5:].strip()) if text.startswith("ref: ") else text
    if sha and re.fullmatch(r"[0-9a-f]{40}", sha):
        return ("git", sha)
    return ("directory", None)


def _read_manifest(
    path: Path, parse: Callable[[str], Any], unreadable: list[str]
) -> dict[str, Any]:
    """A target's manifest as a mapping, or `{}` with the reason recorded.

    **Every way this can fail is a fact about the target, never a crash.** Until
    M4's review this caught only the decoder's own error and `OSError`, and four
    measured inputs ended every command with exit 3 — because `recon` runs
    inside every subcommand's `_prepare`, one manifest took `sweep`, `surfaces`
    and `structure` down with it:

    - `package.json` containing `[]` — two bytes, valid JSON, and a list has no
      `.get`. `project = "x"` in `pyproject.toml` is the same shape.
    - deep nesting in either: both decoders recurse, and `RecursionError` is not
      a decode error. `MemoryError` is its sibling at larger depths.
    - invalid UTF-8, which raised out of `read_text` before the decoder ran and
      ended the run with exit 2 over one metadata file.

    The same class as M3.5's C1 and C2 — hostile input reported as a defect in
    the tool, and one file ending the review of all the others — and the same
    answer: catch per file, record it, continue.

    **Recorded, not dropped.** This used to return `{}` in silence, so a
    manifest that could not be read and a manifest declaring no entry points
    produced the same `recon.json`. They are different facts, and only one of
    them means the entry points were looked for.
    """
    try:
        data = parse(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError, MemoryError) as exc:
        # ValueError covers JSONDecodeError, TOMLDecodeError and
        # UnicodeDecodeError, all three of which subclass it.
        unreadable.append(f"{path.name} ({type(exc).__name__})")
        return {}
    if not isinstance(data, dict):
        unreadable.append(f"{path.name} (top level is {type(data).__name__}, not a mapping)")
        return {}
    return data


def _entrypoints(root: Path, found: frozenset[str], unreadable: list[str]) -> dict[str, list[str]]:
    """Declared metadata only. §3: "Deeper enumeration is M2's job; do not
    attempt it here." Reading a manifest is reading a declaration; walking
    imports to find what is reachable is the surface source, and doing it here
    would put M2's semantics in M1's output under M1's field name.

    `unreadable` collects manifests that were present and could not be read,
    so `coverage_gaps` can say so rather than leaving it to be inferred from an
    empty `declared`.
    """
    declared: list[str] = []

    # `is_file()` follows symlinks, so until M3.5 a target shipping either
    # manifest as a link had a file elsewhere on the machine read, parsed, and
    # its declared entry points copied into `recon.json` — a quiet leak, since
    # the entry points simply appear and nothing records where they came from.
    #
    # `inventory.walk` has never followed a symlink. These two files, and the
    # `.git` pair above, are reached *by name* rather than found by the walk,
    # so containment held for every file the tool discovered and failed for
    # every file it went looking for. That is the shape worth remembering: the
    # exception to a rule is wherever the rule is not the thing doing the work.
    if "pyproject.toml" in found:
        data = _read_manifest(root / "pyproject.toml", tomllib.loads, unreadable)
        project = data.get("project")
        scripts = project.get("scripts") if isinstance(project, dict) else None
        if isinstance(scripts, dict):
            declared += [f"{name} = {target}" for name, target in sorted(scripts.items())]

    # The same breach by the other manifest; see the note above `pyproject`.
    if "package.json" in found:
        data = _read_manifest(root / "package.json", json.loads, unreadable)
        binaries = data.get("bin")
        if isinstance(binaries, dict):
            declared += [f"{name} = {target}" for name, target in sorted(binaries.items())]
        elif isinstance(binaries, str):
            declared.append(binaries)

    # From the walk, never from `glob`. `Path.glob` follows a symlinked
    # directory, so a target shipping `.github -> /somewhere/else` had a foreign
    # directory's workflow filenames copied into `recon.json` under this
    # target's name — reported, in a field a reader takes as a statement about
    # the tree in front of them.
    #
    # A consequence worth stating: if `.github` is excluded from the walk, no
    # workflows are reported. That is the honest answer rather than a
    # regression — an excluded directory was not read, and `coverage_gaps` says
    # so on its own line.
    workflows = sorted(
        path
        for path in found
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    )
    return {"declared": sorted(declared), "workflows": workflows}


def _security_process(entries: list[FileEntry], found: frozenset[str]) -> dict[str, Any]:
    """Every field from what the walk found; nothing reached by name.

    All four of these were `is_file()` with no symlink check at all, which
    `is_file()` answers by following the link. `SECURITY.md -> /etc/passwd`
    reported `security_md: true` for a target with no security policy — a claim
    about someone else's filesystem, presented as a property of this tree.
    """
    return {
        "security_md": "SECURITY.md" in found,
        "dependabot": ".github/dependabot.yml" in found or ".github/dependabot.yaml" in found,
        "sast_config": any(candidate in found for candidate in _SAST_CONFIG),
        "test_files": sum(1 for entry in entries if _TEST_FILE.search(entry.path)),
    }


# Formats that hold no entry points of their own, or that the surface kinds
# read only as named manifests. Every other language in the map is code.
_NOT_CODE = frozenset({"ini", "json", "markdown", "text", "toml", "yaml"})

# How many paths a `coverage_gaps` line names before it says "and N more".
# Every ordinary target holds binary assets, so an uncapped list puts every
# image in the tree on one line and the gap stops being readable — the same
# failure as not reporting it, reached from the other side.
GAP_LIST_LIMIT = 5

# Extensions whose files are assets rather than content a reviewer reads. The
# *only* thing that exempts an unread file from `unread_code`.
#
# **This is the inversion, and it replaces a list of names.** The third review
# closed a NUL-in-`SKILL.md` evasion by adding an `_AGENT_ARTIFACTS` set — which
# is a denylist, the polarity P3 refuses, and it was written in the same pass
# that inverted the `os` and `yaml` tables for exactly that reason. A fourth
# review then walked past it three ways in one attempt: `AGENT.md` (singular,
# a real convention for several tools), `prompt.txt`, and `setup` with no
# extension at all. Each cost the attacker a rename.
#
# Naming what may be *skipped* moves the burden here. An unread file is a gap
# unless we have said its extension carries no reviewable content, so the next
# evasion is not a new name — it is a name we chose to exempt.
#
# Still a pure function of the path, which is what lets it cover the oversized
# case the previous pass wrote down as an accepted residue. That residue was
# only ever a statement that padding is free: `setup` at 5 MB never opens, so
# any test needing its bytes could not reach it. This one needs none.
#
# Over-flagging is the deliberate direction (P4, P6): a stripped binary named
# `mytool` with no extension is reported as unread code, and that costs a
# reviewer one line to dismiss. The reverse costs a silent gap.
_BINARY_ASSETS = frozenset(
    {
        # images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".ico",
        ".tiff",
        ".tif",
        # fonts
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        # audio and video
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".mp4",
        ".m4a",
        ".mov",
        ".avi",
        ".webm",
        # archives, and images of filesystems
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".zst",
        ".7z",
        ".rar",
        ".tar",
        ".iso",
        ".img",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        # compiled output and opaque data
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".o",
        ".a",
        ".lib",
        ".class",
        ".jar",
        ".wasm",
        ".pyc",
        ".pyo",
        ".whl",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pdf",
        ".pack",
        ".idx",
    }
)


def _is_code(entry: FileEntry) -> bool:
    """Whether a reviewer should care that this file went unread.

    One test, inverted: **everything counts unless its extension is a known
    asset.** The three predecessors of this function each asked whether the file
    *looked* like code — by extension, then by shebang, then by a list of
    artifact names — and each was defeated by a file that looked like something
    else. A question of the form "is this on my list of dangerous things" has an
    answer the target chooses.

    The basename is lowercased because `STACK.md` §4 makes case a finding class
    rather than portability: `.PNG` and `.png` are one file on macOS and two on
    Linux, and the exemption must not depend on which.

    A file with no extension is not exempt, which is the `setup` and `install`
    case; a dotfile's leading dot is part of its name, so `.env` has the suffix
    `.env` and is not exempt either.
    """
    name = entry.path.rsplit("/", 1)[-1].lower()
    suffix = name[name.rfind(".") :] if "." in name else ""
    return suffix not in _BINARY_ASSETS


# Present in the tree, and not read. One line each rather than one combined
# line, because the remedies differ and a reader sent to the wrong one wastes
# the trip: a permission, a kind of file, a threshold, a classification.
#
# `binary` is here because of the second review. A target put eight NUL bytes in
# a comment — 12% of a 59-byte script, above the 5% threshold — and `install.sh`
# carrying `curl | sh` left the review with `0 candidates, exit 0` and no line
# anywhere naming it. Worse than silence: `coverage_gaps` then read
# "no coverage for: markdown", because a skipped file contributes no language,
# so the one honest-looking line in the artifact described a tree that did not
# exist. M3.5 raised the cost of that evasion from one byte to eight and called
# the class closed; a third review then hid a file with no extension at all, and
# `_is_code` above is where that is answered.
_UNREAD_REASONS = (
    ("unreadable", "could not be read (a permission)"),
    ("not_regular", "not a regular file (a FIFO, socket or device)"),
    ("too_large", "larger than the size bound — raise it with --max-file-bytes"),
    ("binary", "classified binary (over 5% non-text bytes in the first 8 KiB)"),
)

# What the surface source cannot reach, one line each, so a reader sees the
# limit rather than inferring it from a regex. BRIEF_M2.md §4 names the first
# two; the rest are the line-oriented limits accepted in TASKS_M2.md (Q3) on
# the condition that each is named here. Fixed text, not derived from the
# kinds: recon is a peer of the surface source and does not import it (P11).
_STRUCTURE_GAPS = (
    # FR-3.7, and the limit a reader of a structural record most needs. The
    # report has to carry it too; this is the artifact half.
    "structure: reasoning stops at one function body — a value reaching a sink "
    "through an intermediate call is not followed (FR-3.7, v2)",
    "structure: a value bound outside the body it is used in is not followed, so a "
    "collection held in a module constant is not read as a literal one",
    "structure: what counts as validating is a list of names, not a proof — a call "
    "that is named here suppresses a candidate whether or not it confines anything",
    # Not "listed in unread_code", which this line said for one draft and which
    # is false: recon is a peer of the structural source and does not parse
    # anything, so it cannot know. `secrev structure` names the files and exits
    # 2 — the honest split, and the same one M3.5 settled for unread files.
    "structure: a file that fails to parse is not reviewed by this source at all; "
    "`secrev structure` names it and exits 2 rather than reporting no candidates",
)

# What the surface source cannot reach, one line each, so a reader sees the
# limit rather than inferring it from a regex. Prefixed `surface: ` since M4,
# when a second block joined it: with two sets of limits in one list a reader
# has to be able to tell which source each belongs to, and the prefix does that
# in the artifact rather than in a convention someone has to know
# (BRIEF_M4.md §6 Q4).
_SURFACE_GAPS = (
    "surface: HTTP routes are not enumerated (framework-specific; FR-1.3)",
    "surface: IPC handlers are not enumerated (framework-specific; FR-1.3)",
    # This said "(needs AST, M4)" until M4 shipped one. The parser exists now and
    # this is still not enumerated, because it is a *reachability* question and
    # the structural source adds candidates rather than entry points (P11,
    # BRIEF_M4.md §1 refuses `surfaces/` by name). A gap line naming the
    # milestone that was going to close it, in the milestone that did not, is
    # how a reader learns to stop believing gap lines.
    "surface: the argument parser beneath a declared CLI command is not enumerated — "
    "it needs an AST, which exists since M4, but reading it is the surface source's "
    "work and not the structural source's",
    "surface: a package with no `__all__` has no declared public surface to enumerate",
    "surface: an `__all__` built at runtime, and names more than 20 lines below "
    "its declaration, are not seen",
    "surface: a declaration split across lines is missed, and several on one line "
    "enter as one record (line-oriented, no AST in M2)",
    "surface: hooks declared in agent or skill frontmatter, or in other clients' "
    "configs, are not enumerated",
    "surface: CLI commands declared in setup.cfg, setup.py or package.json are not enumerated",
)


def _coverage_gaps(
    languages: dict[str, int],
    applied: list[str] | None = None,
    unread: dict[str, list[str]] | None = None,
    manifests_unreadable: list[str] | None = None,
) -> list[str]:
    """FR-3.8: degrade honestly rather than pass over what is not covered.

    `manifests_unreadable` names the manifests present and not readable. Their
    declared entry points are missing from `entrypoints.declared`, and without
    this line that absence reads the same as a manifest declaring none.

    `applied` names the excluded directories that were actually present, so a
    skipped directory is a *stated* gap rather than one a reader has to infer
    from `inventory.excluded` (M3.5 A2). That is A2's headline made true: a
    target cannot hide code in an excluded directory without it being visible.

    The line disappears when nothing was skipped — including when the set is
    narrowed from the command line — so an override is visible in the artifact
    and not only in the invocation that produced it. Defaulted so that callers
    which do not pass it keep the previous output exactly.

    §3's example reads "structural analysis unavailable for: yaml, markdown",
    which implies structural analysis exists for the other languages. Until M4
    it existed for none of them, and naming two languages would have understated
    the gap by implying the rest were covered.

    **Since M4 it exists for Python and for nothing else**, so the line now says
    which languages are present and unreached — which is §3's shape, arrived at
    once it became true. The previous line said "not implemented (M4)" and would
    have been false the moment the source shipped: a gap that overstates is read
    once and then discounted, exactly like one that understates.

    The surface source exists since M2, so the line saying it did not is gone
    (BRIEF_M2.md §4): a gap that is no longer true misleads as surely as a
    missing one. What replaces it says what the source still cannot reach,
    including the code languages present that no kind reads (STACK.md §7).
    """
    code = sorted(name for name in languages if name not in _NOT_CODE and name != "python")
    others = f"not read for: {', '.join(code)}" if code else "no other code language present"
    # The same set answers both sources' first line: a code language no parser
    # and no kind reads. Computed once from `_NOT_CODE` rather than listed, so a
    # language added to the inventory cannot appear in one line and not the
    # other (STACK.md §7).
    unparsed_languages = (
        f"not implemented for: {', '.join(code)}" if code else "no other code language present"
    )

    # First in the list, because a directory left unread is the largest gap
    # this tool can have and the likeliest place for something to have been
    # put. Everything below it is a limit on how well we read what we did read.
    skipped: list[str] = []
    if applied:
        skipped.append(
            "excluded from review and not read at all: "
            f"{', '.join(applied)} — override the set with --exclude"
        )

    # Beside the excluded directories and for the same reason: a file present
    # and not read is a gap, and one the artifact previously recorded only as a
    # bare path in an `inventory` list that reads as bookkeeping.
    not_read: list[str] = []
    for key, why in _UNREAD_REASONS:
        paths = (unread or {}).get(key) or []
        if not paths:
            continue
        # Capped, and saying so. Every ordinary target holds binary assets, so
        # an uncapped list puts every image in the tree on one line and the gap
        # stops being readable — which is the same failure as not reporting it,
        # reached from the other side. `cli._incomplete` already truncates this
        # way; a truncation that does not say how much it left out would be a
        # third way of reporting a partial answer as a whole one.
        shown = ", ".join(paths[:GAP_LIST_LIMIT])
        if len(paths) > GAP_LIST_LIMIT:
            extra = len(paths) - GAP_LIST_LIMIT
            shown += f", and {extra} more — the full list is inventory.{key}"
        not_read.append(f"present but not read, {why}: {shown}")

    # With the unread files and for the same reason, and never more than two
    # names long, since only two manifests are read by name.
    if manifests_unreadable:
        not_read.append(
            "present but not read, a manifest that could not be parsed — its declared "
            f"entry points are not listed: {', '.join(sorted(manifests_unreadable))}"
        )

    return [
        *skipped,
        *not_read,
        f"structure: rules are read in Python only; {unparsed_languages}",
        *_STRUCTURE_GAPS,
        f"surface: code entry points are read in Python only; {others}",
        *_SURFACE_GAPS,
    ]


def recon(
    root: Path,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> Recon:
    entries = walk(root, excluded, max_bytes)

    # Computed once and used twice — reported in `inventory.excluded` and
    # stated as a gap in `coverage_gaps`. Calling it again for the second use
    # would put a third full walk of the tree in this function.
    applied = exclusions_applied(root, excluded)
    # What the walk actually found, for every field that used to reach a file by
    # name. Computed once here rather than per field, so a site cannot be added
    # later that quietly skips it.
    found = _found_paths(entries)
    # Unreadable files are out of the text set: they have no countable lines
    # and no language we are entitled to claim, since the extension is the only
    # thing we ever saw. They are reported on their own footing below.
    text_entries = [
        item
        for item in entries
        if item.is_readable
        and item.is_regular
        and item.is_within_size_bound
        and not item.is_binary
        and not item.is_symlink
    ]

    languages: dict[str, int] = {}
    loc_total = 0
    for entry in text_entries:
        language = language_of(entry.path)
        if language:
            languages[language] = languages.get(language, 0) + 1
        # `os_path`, never `path`: the record is NFC, the filesystem may not be.
        # The third read of the same file in a run, after `inventory`'s and
        # whichever candidate source runs. `text_entries` above carries every
        # decision the walk made, so nothing is retried — but the same window
        # `sweep.py` names applies, and this is the third place it is open.
        raw = (root / entry.os_path).read_bytes()
        loc_total += len(split_lines(raw.decode("utf-8", errors="replace")))

    # Computed once, then used by the artifact, the gap lines and the exit code
    # alike. Three copies of the same filter is three places for them to drift,
    # and the exit code disagreeing with the artifact it was derived from is the
    # worst of the three outcomes.
    unread = {
        "unreadable": sorted(item.path for item in entries if not item.is_readable),
        "not_regular": sorted(item.path for item in entries if not item.is_regular),
        "too_large": sorted(item.path for item in entries if not item.is_within_size_bound),
        "binary": sorted(item.path for item in entries if item.is_binary),
    }

    # The subset a reviewer has to care about: a file whose *extension* says it
    # is code, that nothing read.
    #
    # This distinction is why the exit code is not simply "anything unread". A
    # PNG is binary in every ordinary target, so exiting 2 on `binary` alone
    # would light the signal on almost every run — and an exit code that is
    # always on is one people stop reading, which is the H-1 habit in a new
    # place. A shell script classified binary is a different statement: the
    # extension says code, so the classification removed something from review
    # that a reviewer expected to be in it (P11).
    unread_paths = {path for paths in unread.values() for path in paths}
    unread_code = sorted(
        item.path for item in entries if item.path in unread_paths and _is_code(item)
    )

    source, sha = git_identity(root)

    manifests_unreadable: list[str] = []
    entrypoints = _entrypoints(root, found, manifests_unreadable)

    return Recon(
        target={
            "root": slug(root.resolve().name),
            # No SHA means no version. `STACK.md` §6 makes `<version>` a
            # directory in the workspace, and inventing one would split a
            # single target's history across two paths that never reconcile.
            "version": sha[:12] if sha else "unversioned",
            "source": source,
            "sha": sha,
        },
        inventory={
            "files_total": len(entries),
            "by_language": {key: languages[key] for key in sorted(languages)},
            "loc_total": loc_total,
            "binary": unread["binary"],
            # Present, and not read. FR-3.8 requires degrading honestly rather
            # than passing over what is not covered: a file absent from every
            # list in this artifact reads as reviewed and clean, which is the
            # one thing it is not.
            "unreadable": unread["unreadable"],
            # Present, and not a regular file: a FIFO, socket or device. Listed
            # separately from `unreadable` because they are different facts —
            # one is a permission the reviewer might be able to change, the
            # other is a thing that has no content to review at all. Reading
            # one of these is what hung the walk indefinitely before M3.5.
            "not_regular": unread["not_regular"],
            # Present, and larger than the size bound, so never read. A third
            # fact rather than a variant of the two above: this one is a
            # threshold the reviewer can raise with `--max-file-bytes`, where
            # the others are a permission and a kind of file (STACK.md §5).
            "too_large": unread["too_large"],
            # The four lists above, filtered to what is *not* a known binary
            # asset. It is what `cli._incomplete` keys the exit code on, and it
            # is in the artifact rather than derived there so that the number a
            # reader sees and the number the exit code was computed from are the
            # same.
            #
            # This said "filtered to what has a code extension" until a fifth
            # reading, which was the rule before `_is_code` was inverted and is
            # the one `AGENT.md` and an extensionless `setup` defeated.
            "unread_code": unread_code,
            "symlinks": [
                {
                    "path": item.path,
                    "target": item.symlink_target,
                    "escapes_root": item.escapes_root,
                }
                for item in sorted(entries, key=lambda item: item.path)
                if item.is_symlink
            ],
            # Recorded as *applied*, never silently, and never as the constant
            # (STACK.md §5). This emitted all fourteen names in EXCLUDED_DIRS
            # until M3.5 — the directories the tool *could* skip rather than
            # the ones it did — so the field answered a question nobody asked
            # and a reader still could not tell a skipped `dist/` from an
            # absent one. That distinction is the entire reason §5 requires
            # exclusions to be recorded, and `dist/` is the sharp case: our
            # build output, and a reviewed target's shipped artifact.
            #
            # `exclusions_applied` has existed and been correct since M1, with
            # a docstring explaining exactly why the distinction matters. It
            # was simply never called.
            "excluded": applied,
        },
        entrypoints=entrypoints,
        security_process=_security_process(entries, found),
        coverage_gaps=_coverage_gaps(languages, applied, unread, manifests_unreadable),
    )


def to_json(result: Recon) -> str:
    """`recon.json`, byte-stable.

    Two-space indent and a trailing newline so a diff of the golden is
    readable; `sort_keys=False` because the key order is §3's order and that is
    part of the contract rather than an accident of insertion.
    """
    document = {
        "target": result.target,
        "inventory": result.inventory,
        "entrypoints": result.entrypoints,
        "security_process": result.security_process,
        "coverage_gaps": result.coverage_gaps,
    }
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
