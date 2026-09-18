"""Catalog loading and strict validation. BRIEF_M1.md §4.

The catalog is data, not code (FR-3.3): adding a pattern must never require
editing a script. That is also why the seed regexes can contain the very
constructs `STACK.md` §2.1 forbids in this codebase — they live in YAML, where
they are strings. In a `.py` file the same text would trip both the
`PreToolUse` guard and `self_check.py`, correctly.

Everything here refuses rather than repairs. §4's reason is worth restating
because it is the whole design: "a silently ignored typo in a pattern file is a
missing check that nobody sees." A catalog that loads with a misspelled field
produces a run that looks exactly like a clean one — same exit code, same
report shape, one fewer question asked. So unknown keys are an error, not a
warning; every message names the offending pattern id, because "invalid
catalog" sends a reader to a file that will eventually hold two hundred
entries with no indication of which one is wrong.

Validation is deliberately positional in one respect: the pattern's `id` is
read and checked first, so every subsequent failure can name it.

**Loading is `safe_load`.** The unsafe loader constructs arbitrary Python
objects from tags in the input, and this module reads a file path a caller
supplies. A tool that flags that construct in other people's code and then
performs it is not credible (`STACK.md` §2.1), so `tests/test_catalog.py`
asserts a tagged document is refused rather than acted on.

**A catalog regex is untrusted input to the engine**, and until M3.5 this
paragraph described that risk wrongly in the two ways that mattered.

It said superlinear time required "a pattern written with nested quantifiers".
It does not. `log.sensitive` had a single `*` and no nesting, and was quadratic
anyway, because the cost is not inner backtracking but the **outer scan**:
`re.search` retries the whole pattern from every position, so a line offering K
matching start positions, each consuming N characters, costs O(N*K). Naming
nested quantifiers as the precondition is why reading the shipped pack did not
catch it — reviewers were looking for the wrong shape.

It also scoped the exposure to "a caller who points `--catalog` at something
they did not write". The quadratic pattern was in the pack this tool ships, so
the exposure was every caller's, and that sentence is what made the shipped
catalog look like the safe side of the boundary.

Measured before being rewritten: 185.72 ms on a 9,600-byte crafted line, 11.4 s
on 76,800, extrapolating to roughly 48 minutes on 1 MB. `log.sensitive` now
bounds its repetition, which makes it linear; `patterns/_base.yaml` carries the
measurements and the two candidate fixes that were rejected for losing findings.

**What remains unmitigated is the general case.** Nothing here bounds
backtracking, and stdlib `re` offers no timeout, so an arbitrary `--catalog`
can still be made to take superlinear time. It stays recorded rather than
half-fixed: the obvious mitigation is a denylist over regex shapes, and P3 says
a denylist is a finding until proven otherwise. The real answers are a bounded
engine, a subprocess timeout, or input bounds on what is scanned — the last of
these is a `STACK.md` §5 amendment raised in `BRIEF_M3.5.md` §6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

# The ledger's vocabulary is shared with every other candidate source, so it is
# defined once in `ledger.py` and validated against here rather than copied.
from secrev.ledger import LAYERS, PRECISIONS

# §4: a fixed subset, never arbitrary passthrough. `s` and `m` are absent
# deliberately rather than by omission — either would let a line-oriented rule
# reason across lines, which §4 says makes it a structural rule by definition.
ALLOWED_FLAGS = frozenset({"i"})
_FLAG_BITS = {"i": re.IGNORECASE}

SEVERITY_HINTS = frozenset({"high", "medium", "low", "observation", "informational"})

# `namespace.name`. The hierarchy has to hold at 200 patterns and cannot be
# imposed retroactively without re-identifying every candidate ever recorded.
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

_REQUIRED = frozenset({"id", "layer", "regex", "precision", "question", "default_severity_hint"})
_OPTIONAL = frozenset({"languages", "paths_exclude", "flags", "owasp", "references"})
_KNOWN = _REQUIRED | _OPTIONAL

_TOP_LEVEL = frozenset({"version", "patterns"})


class CatalogError(Exception):
    """A schema violation. The CLI turns this into exit 2.

    Not an internal error (exit 3): the tool worked and the configuration is
    wrong, and `STACK.md` §3 keeps those apart so a hook can tell "the tool
    broke" from "the input was bad".
    """


@dataclass(frozen=True)
class Pattern:
    """One rule. Frozen because a catalog mutated after validation is a
    catalog that was not validated."""

    id: str
    layer: tuple[str, ...]
    regex: re.Pattern[str]
    precision: str
    question: str
    default_severity_hint: str
    languages: tuple[str, ...]
    paths_exclude: tuple[str, ...]
    owasp: str | None
    references: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    version: str
    patterns: tuple[Pattern, ...]


def _fail(message: str, *, pattern_id: str | None = None) -> NoReturn:
    """Declared `NoReturn` so callers narrow correctly after it and no branch
    has to pretend there is a value to return."""
    where = f"pattern {pattern_id}: " if pattern_id else ""
    raise CatalogError(f"{where}{message}")


def _require_str(value: Any, field: str, pattern_id: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"`{field}` must be a non-empty string", pattern_id=pattern_id)
    return str(value)


def _require_str_list(value: Any, field: str, pattern_id: str | None) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"`{field}` must be a list of strings", pattern_id=pattern_id)
    return tuple(str(item) for item in value)


def _compile(raw: str, flags: tuple[str, ...], pattern_id: str) -> re.Pattern[str]:
    """Compile at load, so a malformed regex is a catalog error rather than a
    crash partway through a sweep with some files already reported."""
    bits = 0
    for flag in flags:
        if flag not in ALLOWED_FLAGS:
            allowed = ", ".join(sorted(ALLOWED_FLAGS))
            _fail(
                f"flag `{flag}` is not in the permitted subset ({allowed})",
                pattern_id=pattern_id,
            )
        bits |= _FLAG_BITS[flag]
    try:
        return re.compile(raw, bits)
    except re.error as exc:
        _fail(f"regex does not compile: {exc}", pattern_id=pattern_id)


def _layer(raw: Any, pattern_id: str) -> tuple[str, ...]:
    """§4: always a list, even with one element. M1 refuses more than one."""
    layer = _require_str_list(raw, "layer", pattern_id)
    if not layer:
        _fail("`layer` must have at least one element", pattern_id=pattern_id)
    for value in layer:
        if value not in LAYERS:
            known = ", ".join(sorted(LAYERS))
            _fail(f"`layer` value `{value}` is not one of: {known}", pattern_id=pattern_id)
    if len(layer) > 1:
        _fail(
            "a multi-element `layer` is refused in M1: the ledger representation is "
            "undecided — §5's record carries `layer` as a scalar, so emitting this "
            "pattern would drop a layer with no trace. Accepting a catalog we cannot "
            "emit is worse than refusing one we can read",
            pattern_id=pattern_id,
        )
    return layer


def _pattern(raw: Any, index: int) -> Pattern:
    if not isinstance(raw, dict):
        _fail(f"entry {index} in `patterns` is not a mapping")
    entry: dict[str, Any] = raw

    # The id first, so every later message can name it.
    if "id" not in entry:
        _fail(f"entry {index} in `patterns` has no `id`")
    pattern_id = _require_str(entry["id"], "id", None)
    if not _ID_RE.match(pattern_id):
        _fail(f"`{pattern_id}` is not `namespace.name` — the hierarchy has to hold at 200 patterns")
    if pattern_id.split(".", 1)[0] == "surface":
        # The namespace belongs to the surface kinds (kinds.py). A pattern here
        # would share a `rule_id` with surface records in the one ledger: two
        # different questions under one name.
        _fail(f"`{pattern_id}` is in the `surface` namespace, which is reserved for surface kinds")

    unknown = sorted(set(entry) - _KNOWN)
    if unknown:
        if "multiline" in unknown:
            _fail(
                "`multiline` is not a field and will not become one. §4: matching is "
                "line-oriented in M1, and anything needing cross-line reasoning is a "
                "structural rule (M4) by definition",
                pattern_id=pattern_id,
            )
        _fail(f"unknown field(s): {', '.join(unknown)}", pattern_id=pattern_id)

    missing = sorted(_REQUIRED - set(entry))
    if missing:
        _fail(f"missing required field(s): {', '.join(missing)}", pattern_id=pattern_id)

    layer = _layer(entry["layer"], pattern_id)

    precision = _require_str(entry["precision"], "precision", pattern_id)
    if precision not in PRECISIONS:
        known = ", ".join(sorted(PRECISIONS))
        _fail(f"`precision` must be one of: {known}", pattern_id=pattern_id)

    hint = _require_str(entry["default_severity_hint"], "default_severity_hint", pattern_id)
    if hint not in SEVERITY_HINTS:
        known = ", ".join(sorted(SEVERITY_HINTS))
        _fail(f"`default_severity_hint` must be one of: {known}", pattern_id=pattern_id)

    flags = _require_str_list(entry.get("flags", []), "flags", pattern_id)
    owasp = entry.get("owasp")
    if owasp is not None:
        owasp = _require_str(owasp, "owasp", pattern_id)

    return Pattern(
        id=pattern_id,
        layer=layer,
        regex=_compile(_require_str(entry["regex"], "regex", pattern_id), flags, pattern_id),
        precision=precision,
        question=_require_str(entry["question"], "question", pattern_id),
        default_severity_hint=hint,
        languages=_require_str_list(entry.get("languages", []), "languages", pattern_id),
        paths_exclude=_require_str_list(
            entry.get("paths_exclude", []), "paths_exclude", pattern_id
        ),
        owasp=owasp,
        references=_require_str_list(entry.get("references", []), "references", pattern_id),
    )


def _document(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        # A CatalogError rather than the OSError: the argument was wrong, which
        # is exit 2, and letting an OSError escape would report exit 3 and say
        # the tool broke.
        raise CatalogError(f"cannot read catalog {path.name}: {exc}") from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path.name} is not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise CatalogError(f"{path.name}: the top level must be a mapping of version and patterns")

    unknown = sorted(set(document) - _TOP_LEVEL)
    if unknown:
        raise CatalogError(f"{path.name}: unknown top-level key(s): {', '.join(unknown)}")
    return document


def load_file(path: Path) -> Catalog:
    """One catalog file, fully validated."""
    document = _document(path)

    if "version" not in document:
        raise CatalogError(
            f"{path.name}: no `version`. FR-3.12 requires every run to record the "
            "catalog version it ran under; without it FR-4.6 cannot invalidate anything"
        )
    version = _require_str(document["version"], "version", None)

    raw_patterns = document.get("patterns")
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise CatalogError(f"{path.name}: `patterns` must be a non-empty list")

    patterns: list[Pattern] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_patterns):
        pattern = _pattern(raw, index)
        if pattern.id in seen:
            _fail(
                "duplicate id — two patterns sharing one id collapse two questions "
                "into one, and D-6 is explicit that two questions earn two answers",
                pattern_id=pattern.id,
            )
        seen.add(pattern.id)
        patterns.append(pattern)

    return Catalog(version=version, patterns=tuple(patterns))


def load(paths: list[Path]) -> Catalog:
    """Several catalog files as one catalog.

    Every file must carry the same `version`. The version is a property of the
    catalog a run executed against, not of one pack within it: two packs
    disagreeing would make `catalog_version` on a hit ambiguous, and FR-4.6
    invalidates verifications on exactly that field.

    Patterns are sorted by id. Determinism is the reason (NFR-3) — the order
    files arrive in is an argument-order accident, and it would otherwise
    decide the order of records in `hits.jsonl`.
    """
    if not paths:
        raise CatalogError("no catalog files given")

    version: str | None = None
    version_source = ""
    merged: dict[str, Pattern] = {}

    for path in sorted(paths, key=lambda item: item.name):
        catalog = load_file(path)
        if version is None:
            version, version_source = catalog.version, path.name
        elif catalog.version != version:
            raise CatalogError(
                f"catalog version mismatch: {version_source} declares {version}, "
                f"{path.name} declares {catalog.version}. One run has one catalog_version"
            )
        for pattern in catalog.patterns:
            if pattern.id in merged:
                _fail("duplicate id, also defined in another pack", pattern_id=pattern.id)
            merged[pattern.id] = pattern

    if version is None:  # pragma: no cover - the empty-paths guard above precludes it
        raise CatalogError("no catalog files given")
    return Catalog(version=version, patterns=tuple(merged[key] for key in sorted(merged)))
