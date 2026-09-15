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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from secrev.inventory import EXCLUDED_DIRS, FileEntry, language_of, split_lines, walk

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


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    """A ref's SHA from a loose file, then from `packed-refs`."""
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip() or None

    packed = git_dir / "packed-refs"
    if packed.is_file():
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
    if git_dir.is_file():
        # A worktree or submodule: `.git` is a file pointing elsewhere. Not
        # followed — the pointer leaves the target tree, and P9 makes that a
        # question rather than a path to chase silently.
        return ("directory", None)
    if not git_dir.is_dir():
        return ("directory", None)

    head = git_dir / "HEAD"
    if not head.is_file():
        return ("directory", None)

    text = head.read_text(encoding="utf-8", errors="replace").strip()
    sha = _resolve_ref(git_dir, text[5:].strip()) if text.startswith("ref: ") else text
    if sha and re.fullmatch(r"[0-9a-f]{40}", sha):
        return ("git", sha)
    return ("directory", None)


def _entrypoints(root: Path) -> dict[str, list[str]]:
    """Declared metadata only. §3: "Deeper enumeration is M2's job; do not
    attempt it here." Reading a manifest is reading a declaration; walking
    imports to find what is reachable is the surface source, and doing it here
    would put M2's semantics in M1's output under M1's field name.
    """
    declared: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        scripts = data.get("project", {}).get("scripts", {})
        if isinstance(scripts, dict):
            declared += [f"{name} = {target}" for name, target in sorted(scripts.items())]

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        binaries = data.get("bin")
        if isinstance(binaries, dict):
            declared += [f"{name} = {target}" for name, target in sorted(binaries.items())]
        elif isinstance(binaries, str):
            declared.append(binaries)

    workflows = sorted(
        f".github/workflows/{item.name}"
        for item in (root / ".github" / "workflows").glob("*")
        if item.is_file() and item.suffix in {".yml", ".yaml"}
    )
    return {"declared": sorted(declared), "workflows": workflows}


def _security_process(root: Path, entries: list[FileEntry]) -> dict[str, Any]:
    return {
        "security_md": (root / "SECURITY.md").is_file(),
        "dependabot": (root / ".github" / "dependabot.yml").is_file()
        or (root / ".github" / "dependabot.yaml").is_file(),
        "sast_config": any((root / candidate).is_file() for candidate in _SAST_CONFIG),
        "test_files": sum(1 for entry in entries if _TEST_FILE.search(entry.path)),
    }


# Formats that hold no entry points of their own, or that the surface kinds
# read only as named manifests. Every other language in the map is code.
_NOT_CODE = frozenset({"ini", "json", "markdown", "text", "toml", "yaml"})

# What the surface source cannot reach, one line each, so a reader sees the
# limit rather than inferring it from a regex. BRIEF_M2.md §4 names the first
# two; the rest are the line-oriented limits accepted in TASKS_M2.md (Q3) on
# the condition that each is named here. Fixed text, not derived from the
# kinds: recon is a peer of the surface source and does not import it (P11).
_SURFACE_GAPS = (
    "surface: HTTP routes are not enumerated (framework-specific; FR-1.3)",
    "surface: IPC handlers are not enumerated (framework-specific; FR-1.3)",
    "surface: the argument parser beneath a declared CLI command is not enumerated (needs AST, M4)",
    "surface: a package with no `__all__` has no declared public surface to enumerate",
    "surface: an `__all__` built at runtime, and names more than 20 lines below "
    "its declaration, are not seen",
    "surface: a declaration split across lines is missed, and several on one line "
    "enter as one record (line-oriented, no AST in M2)",
    "surface: hooks declared in agent or skill frontmatter, or in other clients' "
    "configs, are not enumerated",
    "surface: CLI commands declared in setup.cfg, setup.py or package.json are not enumerated",
)


def _coverage_gaps(languages: dict[str, int]) -> list[str]:
    """FR-3.8: degrade honestly rather than pass over what is not covered.

    §3's example reads "structural analysis unavailable for: yaml, markdown",
    which implies structural analysis exists for the other languages. It exists
    for none of them until M4, and naming two languages would understate the
    gap by implying the rest were covered.

    The surface source exists since M2, so the line saying it did not is gone
    (BRIEF_M2.md §4): a gap that is no longer true misleads as surely as a
    missing one. What replaces it says what the source still cannot reach,
    including the code languages present that no kind reads (STACK.md §7).
    """
    present = ", ".join(sorted(languages)) if languages else "none detected"
    code = sorted(name for name in languages if name not in _NOT_CODE and name != "python")
    others = f"not read for: {', '.join(code)}" if code else "no other code language present"
    return [
        f"structural analysis not implemented (M4); no coverage for: {present}",
        f"surface: code entry points are read in Python only; {others}",
        *_SURFACE_GAPS,
    ]


def recon(root: Path) -> Recon:
    entries = walk(root)
    text_entries = [item for item in entries if not item.is_binary and not item.is_symlink]

    languages: dict[str, int] = {}
    loc_total = 0
    for entry in text_entries:
        language = language_of(entry.path)
        if language:
            languages[language] = languages.get(language, 0) + 1
        # `os_path`, never `path`: the record is NFC, the filesystem may not be.
        raw = (root / entry.os_path).read_bytes()
        loc_total += len(split_lines(raw.decode("utf-8", errors="replace")))

    source, sha = git_identity(root)

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
            "binary": sorted(item.path for item in entries if item.is_binary),
            "symlinks": [
                {
                    "path": item.path,
                    "target": item.symlink_target,
                    "escapes_root": item.escapes_root,
                }
                for item in sorted(entries, key=lambda item: item.path)
                if item.is_symlink
            ],
            # Recorded as applied, never silently (STACK.md §5). A reader
            # cannot tell an empty `.git/` from a skipped one unless told.
            "excluded": [f"{name}/" for name in sorted(EXCLUDED_DIRS)],
        },
        entrypoints=_entrypoints(root),
        security_process=_security_process(root, entries),
        coverage_gaps=_coverage_gaps(languages),
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
