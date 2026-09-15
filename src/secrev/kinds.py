"""Surface kinds: loading and strict validation. TASKS_M2.md C-1, PRD NFR-6.

A surface kind names a class of externally reachable entry point and says where
its declaration is written. The surface source reads these and enters every
declaration it finds into the ledger, whether or not anything matched there
(P11, FR-3.9). So the kinds decide which entry points the review reads at all,
which is why they are held to the catalog's discipline rather than a looser one.

**Data, not code** (NFR-6: "new pattern, new archetype, or new reachability
class = new or edited data file"). Detection is in the data too — which files a
kind looks in and which line declares it — or a new kind would still need a
code change and the requirement would be met in name only. The file lives in
`surfaces/`, beside the catalog and protected like it (STACK.md §8 H-4).

**Line-oriented** (TASKS_M2.md Q3: no AST in M2). A declaration that spans lines
is a recorded coverage gap, not something approximated here.

**Refuses rather than repairs**, for the reason `catalog.py` gives: a kind that
loads with a misspelled field is an entry-point class that silently stops being
enumerated, and the run looks exactly like a clean one. Every message names the
kind. `SurfaceKindError` is a `ValueError`, which `cli.py` already reports as
exit 2 — the input is wrong, the tool is not broken (STACK.md §3).

Loading uses `yaml.safe_load`, as the catalog does and for the same reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

from secrev.inventory import glob_to_regex
from secrev.ledger import LAYERS, PRECISIONS

# Every kind id is `surface.<name>`, and the catalog refuses that namespace for
# patterns. A pattern record and a surface record sharing a `rule_id` would be
# two different questions under one name in one ledger.
NAMESPACE = "surface"
_ID_RE = re.compile(r"^surface\.[a-z][a-z0-9_]*$")

# The catalog's subset, for the same reason: `s` and `m` would let a
# line-oriented declaration reason across lines.
ALLOWED_FLAGS = frozenset({"i"})
_FLAG_BITS = {"i": re.IGNORECASE}

_REQUIRED = frozenset({"id", "layer", "files", "declaration", "precision", "question"})
_OPTIONAL = frozenset({"flags"})
_KNOWN = _REQUIRED | _OPTIONAL
_TOP_LEVEL = frozenset({"version", "kinds"})


class SurfaceKindError(ValueError):
    """A schema violation in the surface kinds. Exit 2, like a catalog error."""


@dataclass(frozen=True)
class Kind:
    """One class of entry point. Frozen for the catalog's reason: data mutated
    after validation is data that was not validated."""

    id: str
    layer: str
    files: tuple[str, ...]
    declaration: re.Pattern[str]
    precision: str
    question: str
    _file_patterns: tuple[re.Pattern[str], ...]

    def applies(self, relative_path: str) -> bool:
        """Whether this kind looks in a file at all."""
        return any(pattern.match(relative_path) for pattern in self._file_patterns)


@dataclass(frozen=True)
class Kinds:
    version: str
    kinds: tuple[Kind, ...]


def _fail(message: str, *, kind_id: str | None = None) -> NoReturn:
    where = f"surface kind {kind_id}: " if kind_id else ""
    raise SurfaceKindError(f"{where}{message}")


def _require_str(value: Any, field: str, kind_id: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"`{field}` must be a non-empty string", kind_id=kind_id)
    return str(value)


def _require_str_list(value: Any, field: str, kind_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"`{field}` must be a list of strings", kind_id=kind_id)
    return tuple(str(item) for item in value)


def _layer(raw: Any, kind_id: str) -> str:
    """Always a list, as in the catalog, and one element, for the catalog's
    reason: the ledger record carries `layer` as a scalar."""
    layer = _require_str_list(raw, "layer", kind_id)
    if len(layer) != 1:
        _fail("`layer` must be a list of exactly one value", kind_id=kind_id)
    if layer[0] not in LAYERS:
        known = ", ".join(sorted(LAYERS))
        _fail(f"`layer` value `{layer[0]}` is not one of: {known}", kind_id=kind_id)
    return layer[0]


def _declaration(raw: str, flags: tuple[str, ...], kind_id: str) -> re.Pattern[str]:
    """Compiled at load, so a malformed regex is exit 2 before any file is read."""
    bits = 0
    for flag in flags:
        if flag not in ALLOWED_FLAGS:
            allowed = ", ".join(sorted(ALLOWED_FLAGS))
            _fail(f"flag `{flag}` is not in the permitted subset ({allowed})", kind_id=kind_id)
        bits |= _FLAG_BITS[flag]
    try:
        return re.compile(raw, bits)
    except re.error as exc:
        _fail(f"`declaration` does not compile: {exc}", kind_id=kind_id)


def _file_pattern(glob: str) -> re.Pattern[str]:
    """A kind's `files` glob, matched without regard to case.

    macOS and Windows filesystems resolve `.Claude/settings.json` when an agent
    asks for `.claude/settings.json`, so a kind that matched the name exactly
    would miss an entry point the agent loads — case sensitivity is a finding
    class here, not portability. Deterministic all the same: the answer depends
    on the name, never on the filesystem the tool happens to run on (NFR-3).

    The path only. A declaration is matched as written, because the keys and
    names it looks for are case-sensitive to whatever reads them; a kind whose
    language is not opts in with the `i` flag.

    Here, not in `glob_to_regex`: that also serves the catalog's
    `paths_exclude`, where ignoring case would exclude *more* files from
    review — the direction that fails open. The record keeps the path as it is
    on disk; the id derives from it (`ids.py`). The glob's own flags are kept,
    so a flag `glob_to_regex` gains later reaches kinds and `paths_exclude`
    alike rather than splitting one glob into two meanings.

    Unicode case folding comes with it: U+017F (long s) matches `s` and U+212A
    (Kelvin sign) matches `k`, so a long-s `skill.md` is a `SKILL.md`. That
    only adds candidates, and it is the same on every platform on one Python
    (the `re` tables are CPython's own).
    """
    pattern = glob_to_regex(glob)
    return re.compile(pattern.pattern, pattern.flags | re.IGNORECASE)


def _kind(raw: Any, index: int) -> Kind:
    if not isinstance(raw, dict):
        _fail(f"entry {index} in `kinds` is not a mapping")
    entry: dict[str, Any] = raw

    # The id first, so every later message can name it.
    if "id" not in entry:
        _fail(f"entry {index} in `kinds` has no `id`")
    kind_id = _require_str(entry["id"], "id", None)
    if not _ID_RE.match(kind_id):
        _fail(
            f"`{kind_id}` is not `{NAMESPACE}.<name>` — the namespace keeps surface "
            "rule ids apart from catalog pattern ids in the one ledger"
        )

    unknown = sorted(set(entry) - _KNOWN)
    if unknown:
        if "multiline" in unknown:
            _fail(
                "`multiline` is not a field. Declarations are line-oriented in M2 "
                "(TASKS_M2.md Q3); one that spans lines is a coverage gap",
                kind_id=kind_id,
            )
        _fail(f"unknown field(s): {', '.join(unknown)}", kind_id=kind_id)

    missing = sorted(_REQUIRED - set(entry))
    if missing:
        _fail(f"missing required field(s): {', '.join(missing)}", kind_id=kind_id)

    precision = _require_str(entry["precision"], "precision", kind_id)
    if precision not in PRECISIONS:
        known = ", ".join(sorted(PRECISIONS))
        _fail(f"`precision` must be one of: {known}", kind_id=kind_id)

    files = _require_str_list(entry["files"], "files", kind_id)
    if not files or any(not glob.strip() for glob in files):
        _fail("`files` must list at least one non-empty glob", kind_id=kind_id)

    flags = _require_str_list(entry.get("flags", []), "flags", kind_id)

    return Kind(
        id=kind_id,
        layer=_layer(entry["layer"], kind_id),
        files=files,
        declaration=_declaration(
            _require_str(entry["declaration"], "declaration", kind_id), flags, kind_id
        ),
        precision=precision,
        question=_require_str(entry["question"], "question", kind_id),
        _file_patterns=tuple(_file_pattern(glob) for glob in files),
    )


def load_file(path: Path) -> Kinds:
    """The surface kinds, fully validated, sorted by id.

    Sorted for NFR-3: the order entries happen to be written in must not decide
    the order of records in `hits.jsonl`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SurfaceKindError(f"cannot read surface kinds {path.name}: {exc}") from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SurfaceKindError(f"{path.name} is not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise SurfaceKindError(f"{path.name}: the top level must be a mapping of version and kinds")
    unknown = sorted(set(document) - _TOP_LEVEL)
    if unknown:
        raise SurfaceKindError(f"{path.name}: unknown top-level key(s): {', '.join(unknown)}")

    if "version" not in document:
        raise SurfaceKindError(
            f"{path.name}: no `version`. A change to a kind has to be detectable later, "
            "the way FR-3.12 makes a catalog change detectable"
        )
    version = _require_str(document["version"], "version", None)

    raw_kinds = document.get("kinds")
    if not isinstance(raw_kinds, list) or not raw_kinds:
        raise SurfaceKindError(f"{path.name}: `kinds` must be a non-empty list")

    kinds: dict[str, Kind] = {}
    for index, raw in enumerate(raw_kinds):
        kind = _kind(raw, index)
        if kind.id in kinds:
            _fail(
                "duplicate id — two kinds sharing one id would merge two classes of "
                "entry point into one question",
                kind_id=kind.id,
            )
        kinds[kind.id] = kind

    return Kinds(version=version, kinds=tuple(kinds[key] for key in sorted(kinds)))
