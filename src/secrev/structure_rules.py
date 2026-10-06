"""Structural rules: loading and strict validation. `BRIEF_M4.md` §3, NFR-6.

A structural rule names a shape in a function body and the parameters that
decide what counts as that shape — which calls create a resource, which set a
permission, which are sinks, which functions validate. The analysis is code; the
questions and the parameters are data, which is the hybrid `BRIEF_M4.md` §3
records as an owner decision.

**The `shape` field is what makes NFR-6's test pass**, and it is the one piece of
schema worth arguing for. If the loader knew which parameters each *rule id*
required, adding a fifth rule would mean editing Python to teach it — and B1 says
"adding a fifth rule of an existing shape is a data edit only", so the
requirement would be met in name and broken in fact. Instead each rule names its
shape, the code declares the parameters *per shape*, and a fifth rule of an
existing shape is `_structure.yaml` and nothing else. A genuinely new shape needs
Python, which §3 states as the limit rather than hiding it.

That also keeps this module free of any rule's logic: it is handed the shape
specifications and validates against them, exactly as `catalog.py` validates
patterns without knowing what any pattern means.

**Refuses rather than repairs**, for the reason `catalog.py` and `kinds.py` both
give: a rule that loads with a misspelled parameter is a structural check that
silently stops firing while the run still reports success. A misspelled
*parameter* is the dangerous case here and the one a generic "is this a mapping"
check would miss — which is why the spec is exact in both directions, unknown
names and missing ones alike. Every message names the rule.

`StructureRuleError` is a `ValueError`, which `cli.py` already reports as exit 2:
the input is wrong, the tool is not broken (`STACK.md` §3).

Loading uses `yaml.safe_load`, as the other two loaders do and for the same
reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

from secrev.ledger import LAYERS, PRECISIONS

# Every rule id is `structure.<name>`. The catalog refuses this namespace and so
# does `kinds.py`, so a `rule_id` in `hits.jsonl` names exactly one question
# whichever source produced it.
NAMESPACE = "structure"
_ID_RE = re.compile(r"^structure\.[a-z][a-z0-9_]*$")

_REQUIRED = frozenset({"id", "shape", "layer", "precision", "question", "parameters"})
_OPTIONAL = frozenset({"references"})
_KNOWN = _REQUIRED | _OPTIONAL
_TOP_LEVEL = frozenset({"version", "rules"})

# The two parameter types a shape may ask for. Deliberately two and not
# arbitrary YAML: a parameter is either a set of names to compare against or a
# threshold to compare with, and anything richer would be the description
# language §3 refuses.
NAMES = "names"
COUNT = "count"
_PARAMETER_TYPES = frozenset({NAMES, COUNT})


class StructureRuleError(ValueError):
    """A schema violation in the structural rules. Exit 2, like a catalog error."""


@dataclass(frozen=True)
class ShapeSpec:
    """What one analysis shape requires of a rule's data.

    Declared beside the analysis that reads it (`structure.py`) rather than
    here, so a parameter cannot be renamed in one place and read from the other.
    """

    name: str
    parameters: dict[str, str]


@dataclass(frozen=True)
class StructureRule:
    """One structural question. Frozen for the catalog's reason: data mutated
    after validation is data that was not validated."""

    id: str
    shape: str
    layer: str
    precision: str
    question: str
    references: tuple[str, ...]
    names: dict[str, frozenset[str]]
    counts: dict[str, int]


@dataclass(frozen=True)
class StructureRules:
    version: str
    rules: tuple[StructureRule, ...]


def _fail(message: str, *, rule_id: str | None = None) -> NoReturn:
    where = f"structural rule {rule_id}: " if rule_id else ""
    raise StructureRuleError(f"{where}{message}")


def _require_str(value: Any, field: str, rule_id: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"`{field}` must be a non-empty string", rule_id=rule_id)
    return str(value)


def _require_str_list(value: Any, field: str, rule_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"`{field}` must be a list of strings", rule_id=rule_id)
    return tuple(str(item) for item in value)


def _layer(raw: Any, rule_id: str) -> str:
    """Always a list, as in the catalog and the kinds, and one element, because
    the ledger record carries `layer` as a scalar."""
    layer = _require_str_list(raw, "layer", rule_id)
    if len(layer) != 1:
        _fail("`layer` must be a list of exactly one value", rule_id=rule_id)
    if layer[0] not in LAYERS:
        known = ", ".join(sorted(LAYERS))
        _fail(f"`layer` value `{layer[0]}` is not one of: {known}", rule_id=rule_id)
    return layer[0]


def _parameters(
    raw: Any, spec: ShapeSpec, rule_id: str
) -> tuple[dict[str, frozenset[str]], dict[str, int]]:
    """The rule's parameters, checked against its shape in both directions.

    Both directions, because the two failures are different and only one of them
    is loud. A *missing* parameter would raise a `KeyError` in the analysis, and
    someone would notice. An *unknown* one — `permision_calls` — leaves the
    analysis reading a parameter that is not there, which is a structural check
    that quietly stops firing while the gate stays green. That is the failure
    this project keeps finding, so the check refuses a name the shape did not
    ask for rather than ignoring it.
    """
    if not isinstance(raw, dict):
        _fail("`parameters` must be a mapping", rule_id=rule_id)
    given: dict[str, Any] = raw

    unknown = sorted(set(given) - set(spec.parameters))
    if unknown:
        expected = ", ".join(sorted(spec.parameters))
        _fail(
            f"shape `{spec.name}` does not take parameter(s) "
            f"{', '.join(unknown)} — it takes: {expected}",
            rule_id=rule_id,
        )
    missing = sorted(set(spec.parameters) - set(given))
    if missing:
        _fail(
            f"shape `{spec.name}` requires parameter(s): {', '.join(missing)}",
            rule_id=rule_id,
        )

    names: dict[str, frozenset[str]] = {}
    counts: dict[str, int] = {}
    for parameter, kind in sorted(spec.parameters.items()):
        value = given[parameter]
        if kind == NAMES:
            listed = _require_str_list(value, f"parameters.{parameter}", rule_id)
            if not listed or any(not item.strip() for item in listed):
                _fail(
                    f"`parameters.{parameter}` must list at least one non-empty name",
                    rule_id=rule_id,
                )
            names[parameter] = frozenset(listed)
        else:
            # `bool` before `int`: in Python `True` is an `int`, so a YAML
            # `true` would pass an isinstance check and arrive as the threshold
            # 1. A threshold that came from a typo'd boolean is a rule firing on
            # everything.
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _fail(
                    f"`parameters.{parameter}` must be a non-negative integer",
                    rule_id=rule_id,
                )
            counts[parameter] = int(value)
    return names, counts


def _rule(raw: Any, index: int, shapes: dict[str, ShapeSpec]) -> StructureRule:
    if not isinstance(raw, dict):
        _fail(f"entry {index} in `rules` is not a mapping")
    entry: dict[str, Any] = raw

    # The id first, so every later message can name it.
    if "id" not in entry:
        _fail(f"entry {index} in `rules` has no `id`")
    rule_id = _require_str(entry["id"], "id", None)
    if not _ID_RE.match(rule_id):
        _fail(
            f"`{rule_id}` is not `{NAMESPACE}.<name>` — the namespace keeps structural "
            "rule ids apart from pattern and surface ids in the one ledger"
        )

    unknown = sorted(set(entry) - _KNOWN)
    if unknown:
        if "regex" in unknown:
            _fail(
                "`regex` is not a field. A structural rule asks about a shape in a "
                "parsed body; a rule that wants a regex is a pattern, and belongs in "
                "the catalog (D-11)",
                rule_id=rule_id,
            )
        _fail(f"unknown field(s): {', '.join(unknown)}", rule_id=rule_id)

    missing = sorted(_REQUIRED - set(entry))
    if missing:
        _fail(f"missing required field(s): {', '.join(missing)}", rule_id=rule_id)

    shape = _require_str(entry["shape"], "shape", rule_id)
    if shape not in shapes:
        known = ", ".join(sorted(shapes))
        _fail(
            f"`shape` value `{shape}` is not one this tool implements ({known}). "
            "A new shape needs Python — that is the stated limit of the hybrid "
            "split (BRIEF_M4.md §3), not something to work around in data",
            rule_id=rule_id,
        )

    precision = _require_str(entry["precision"], "precision", rule_id)
    if precision not in PRECISIONS:
        known = ", ".join(sorted(PRECISIONS))
        _fail(f"`precision` must be one of: {known}", rule_id=rule_id)

    names, counts = _parameters(entry["parameters"], shapes[shape], rule_id)

    return StructureRule(
        id=rule_id,
        shape=shape,
        layer=_layer(entry["layer"], rule_id),
        precision=precision,
        question=_require_str(entry["question"], "question", rule_id),
        references=_require_str_list(entry.get("references", []), "references", rule_id),
        names=names,
        counts=counts,
    )


def load_file(path: Path, shapes: dict[str, ShapeSpec]) -> StructureRules:
    """The structural rules, fully validated, sorted by id.

    Sorted for NFR-3: the order entries happen to be written in must not decide
    the order of records in `hits.jsonl`.

    `shapes` is passed in rather than imported, so this module holds no rule
    logic and no rule name — the same separation `catalog.py` keeps from what a
    pattern means.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StructureRuleError(f"cannot read structural rules {path.name}: {exc}") from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StructureRuleError(f"{path.name} is not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise StructureRuleError(
            f"{path.name}: the top level must be a mapping of version and rules"
        )
    unknown = sorted(set(document) - _TOP_LEVEL)
    if unknown:
        raise StructureRuleError(f"{path.name}: unknown top-level key(s): {', '.join(unknown)}")

    if "version" not in document:
        raise StructureRuleError(
            f"{path.name}: no `version`. A change to a rule has to be detectable later, "
            "the way FR-3.12 makes a catalog change detectable"
        )
    version = _require_str(document["version"], "version", None)

    raw_rules = document.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise StructureRuleError(f"{path.name}: `rules` must be a non-empty list")

    rules: dict[str, StructureRule] = {}
    for index, raw in enumerate(raw_rules):
        rule = _rule(raw, index, shapes)
        if rule.id in rules:
            _fail(
                "duplicate id — two rules sharing one id would merge two questions into one record",
                rule_id=rule.id,
            )
        rules[rule.id] = rule

    return StructureRules(version=version, rules=tuple(rules[key] for key in sorted(rules)))


def validate_shape_specs(shapes: dict[str, ShapeSpec]) -> None:
    """Every shape declares parameter types this loader understands.

    Called at load rather than trusted, because a shape specification with a
    typo'd *type* — `name` for `names` — would make `_parameters` fall to the
    count branch and reject a perfectly good list, which reads as a data error
    in a file that is correct.
    """
    for name, spec in sorted(shapes.items()):
        if name != spec.name:
            raise StructureRuleError(f"shape `{name}` is registered under the wrong name")
        for parameter, kind in sorted(spec.parameters.items()):
            if kind not in _PARAMETER_TYPES:
                known = ", ".join(sorted(_PARAMETER_TYPES))
                raise StructureRuleError(
                    f"shape `{name}`: parameter `{parameter}` has type `{kind}`, not one of {known}"
                )
