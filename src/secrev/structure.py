"""The structural candidate source. `BRIEF_M4.md`, PRD FR-3.5 to FR-3.8, D-11.

The third peer source. A shape found in a parsed body becomes a ledger record,
`source: "structure"`, on its own account — exactly as a pattern hit and a
surface do, and for the same reason: detection must not decide scope (P11).

Nothing here concludes anything. Every record is `unresolved`, and every rule's
`question` asks something a later phase answers (FR-3.2, A3). A structural
record says *this shape is in this body — go and look at it*.

It is a peer of `sweep.py` and `surfaces.py`, not a stage after them. It imports
neither, and neither imports it: what the three share lives in `ledger.py`, and
a source that can see another's module is one refactor from seeing its results
(D-11, TASKS_M2.md Q2).

The rules that decide bytes, stated because they are the ones not to revise:

  **The analysis reads a vocabulary, never a syntax tree.** `parser.py` owns
  everything that knows about Python; nothing in this file imports `ast` and a
  test holds that. A second language implements `Parser` and the four analyses
  below do not change — which is the whole of `STACK.md` §7's requirement, and
  is false the moment one of these functions touches a node type.

  **What a shape *is* comes from data** (NFR-6): `structure/_structure.yaml`,
  loaded by `structure_rules.py`. Each rule names a `shape`, the shape names the
  parameters it needs, and the parameters decide which calls create, which set
  permissions, which are sinks and which validate. A fifth rule of an existing
  shape is a data edit. A new shape is Python, here, and `BRIEF_M4.md` §3 states
  that limit rather than hiding it.

  **The window is `block-20`** — ±20 lines clipped to the enclosing body
  (`ledger.block_window`, `STACK.md` §5). Structural records are new, so nothing
  is re-identified by this; re-windowing the *pattern* source to the same spec
  is a separate migration and explicitly not M4's.

  **Order is total before ids are assigned.** Files arrive sorted from
  `inventory.walk`; within a file, records sort by `(line, rule_id, column)`.
  The ordinal in an id counts over byte-identical windows, and two candidates in
  one body share a window exactly — so an unstable order here would give the
  same content different ids on two runs, which is the one failure NFR-3 cannot
  absorb.

  **A file that will not parse is a gap and an exit code, never a skip.** It is
  not "no candidates here": it is a file this source did not review, and H-1 is
  the rule that the two must never collapse into one answer. `StructureResult`
  carries both halves so `cli.py` can report the gap and set the code from the
  same value.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from secrev.ids import Match, assign
from secrev.inventory import FileEntry, split_lines, walk
from secrev.ledger import BLOCK_WINDOW_SPEC, Hit, block_window, excerpt
from secrev.parser import Function, ParseFailure, Parser, PythonParser, Unit
from secrev.structure_rules import (
    COUNT,
    NAMES,
    ShapeSpec,
    StructureRule,
    StructureRules,
    validate_shape_specs,
)

# --- shapes ---------------------------------------------------------------
#
# The parameter names each analysis reads, declared beside the analysis that
# reads them. `structure_rules.py` validates a rule's data against these in both
# directions, so a parameter renamed here and not in the YAML is exit 2 at load
# rather than a rule that quietly stops firing.

ORDER_OF_OPERATIONS = "order_of_operations"
DECISION_SHAPE = "decision_shape"
UNVALIDATED_REACH = "unvalidated_reach"
SINK_ADJACENCY = "sink_adjacency"

SHAPES: dict[str, ShapeSpec] = {
    ORDER_OF_OPERATIONS: ShapeSpec(
        name=ORDER_OF_OPERATIONS,
        parameters={
            "creating_calls": NAMES,
            "permission_calls": NAMES,
            "fused_keywords": NAMES,
        },
    ),
    DECISION_SHAPE: ShapeSpec(
        name=DECISION_SHAPE,
        parameters={
            "minimum_alternatives": COUNT,
            "validating_name_fragments": NAMES,
        },
    ),
    UNVALIDATED_REACH: ShapeSpec(
        name=UNVALIDATED_REACH,
        parameters={"sink_calls": NAMES, "validating_calls": NAMES},
    ),
    SINK_ADJACENCY: ShapeSpec(
        name=SINK_ADJACENCY,
        parameters={"dangerous_calls": NAMES},
    ),
}


@dataclass(frozen=True)
class Finding:
    """One shape, before it becomes a record. Internal to this module: the line
    and column locate it, and `column` exists only so the order can be total."""

    rule: StructureRule
    line: int
    column: int


@dataclass(frozen=True)
class StructureResult:
    """What one run produced, and what it could not read.

    Two fields rather than a bare list, because "no candidates" and "never
    parsed" are different answers and `cli.py` needs both to set an exit code
    honestly (H-1).
    """

    hits: list[Hit]
    unparsed: list[str]


def _matches(callee: str, names: frozenset[str]) -> bool:
    """Whether a dotted callee is named by one of the rule's names.

    **A name with a dot matches exactly; a bare name matches any receiver.**
    `os.chmod` names only `os.chmod`; `chmod` names `os.chmod`, `path.chmod` and
    a bare `chmod` alike. The choice sits in the data, one name at a time, so
    `_structure.yaml` decides where recall is worth the noise — rather than this
    function deciding once for every rule, which would be a detection policy
    written in the place P11 says it must not be.
    """
    if callee in names:
        return True
    tail = callee.rsplit(".", 1)[-1]
    return any("." not in name and name == tail for name in names)


def _fused(call_keywords: tuple[tuple[str, object], ...], fused: frozenset[str]) -> bool:
    return any(keyword in fused for keyword, _ in call_keywords)


def _order_of_operations(function: Function, rule: StructureRule) -> list[Finding]:
    """A resource created, then given its permissions in a later call.

    The candidate is reported on the **permission** call, not the creation: that
    is the line a reader has to look at to answer the question, and it is where
    the fix goes.

    A creating call carrying one of `fused_keywords` has set the permission at
    creation and is not a candidate — `open(p, mode=0o600)` is the fix, and a
    rule that fires on its own remedy is one people turn off.
    """
    creating = rule.names["creating_calls"]
    permitting = rule.names["permission_calls"]
    fused = rule.names["fused_keywords"]

    created = [
        call
        for call in function.calls
        if _matches(call.callee, creating) and not _fused(call.keywords, fused)
    ]
    if not created:
        return []
    earliest = min((call.line, call.column) for call in created)
    return [
        Finding(rule=rule, line=call.line, column=call.column)
        for call in function.calls
        if _matches(call.callee, permitting) and (call.line, call.column) > earliest
    ]


def _decision_shape(function: Function, rule: StructureRule) -> list[Finding]:
    """A function that decides permission by testing against a literal
    collection.

    Three conditions, and all three are needed. The **name** says the function
    is making a decision; the **literal collection** is what makes it a list
    someone maintains rather than a computation; the **boolean return** is what
    makes it a gate rather than a lookup. Any two of the three fire on ordinary
    code — a dispatch table, a formatter, a parser — and a rule that fires on
    ordinary code is one that gets deleted.

    P3 is why the rule exists: a denylist answers "allowed" for everything its
    author did not think of, and this is its syntactic signature. It is not its
    meaning, which is why the record is a question.

    **A negated test is not a candidate**, and this is the fourth condition. Both
    polarities look identical until you read which way the membership runs:
    `if x in (...)` names what is refused, so anything unlisted passes — the
    defect. `if x not in (...)` names what is permitted, so anything unlisted is
    refused, which fails closed. Without the distinction the rule would put a
    candidate on every allowlist in every codebase, and a rule that fires on the
    remedy is one people turn off — the same reasoning as the fused create in
    the shape above.

    It is in code and not in a parameter because it is what the shape *means*,
    not a threshold someone tunes. Widening it to allowlists later would be a
    new shape, not a data edit.
    """
    fragments = rule.names["validating_name_fragments"]
    minimum = rule.counts["minimum_alternatives"]

    lowered = function.name.lower()
    if not any(fragment in lowered for fragment in fragments):
        return []
    if not _decides_with_booleans(function):
        return []
    return [
        Finding(rule=rule, line=test.line, column=0)
        for test in function.membership_tests
        if test.size >= minimum and not test.negated
    ]


def _decides_with_booleans(function: Function) -> bool:
    """Whether every value this body returns is a boolean literal.

    `literal_type`, not `kind`: a function returning `"no"` is a lookup and one
    returning `False` is a gate, and `kind == "literal"` cannot tell them apart.
    Checking only the kind would have made this rule fire on any function whose
    name contains "filter" and which returns a constant — which is most
    formatters.

    **All** the returns, not any: a function with one boolean return among
    several values is computing something, and the gate reading is a guess.
    A body with no returns at all is not a decision either, which is what the
    empty check does — `all(...)` over an empty list is True, and this is the
    place that trap would have landed.
    """
    values = [item.value for item in function.returns if item.value is not None]
    if not values:
        return False
    return all(value.literal_type == "bool" for value in values)


def _unvalidated_reach(function: Function, rule: StructureRule) -> list[Finding]:
    """A value the body was handed, reaching a sink with nothing validating in
    between.

    "Was handed" is read narrowly and on purpose: a **parameter of this
    function**, reaching the sink directly or through names bound inside the
    body. Anything wider is cross-function dataflow, which FR-3.7 puts in v2 and
    which this milestone must not approximate — an approximation here would
    produce a rule that looks like it works and misses most real instances,
    which is the reasoning `BRIEF_M3.md` used to defer the whole milestone.

    A validating call anywhere inside the argument suppresses the candidate. So
    does a binding whose value came from one, which is what makes
    `safe = validate(p); open(safe)` quiet — the same two lines a reader would
    accept as correct.
    """
    sinks = rule.names["sink_calls"]
    validating = rule.names["validating_calls"]
    if not function.parameters:
        return []

    parameters = frozenset(function.parameters)
    validated: set[str] = set()
    for assignment in function.assignments:
        if any(_matches(callee, validating) for callee in assignment.value.calls):
            validated.update(assignment.targets)

    findings: list[Finding] = []
    for call in function.calls:
        if not _matches(call.callee, sinks):
            continue
        for argument in (*call.args, *(value for _, value in call.keywords)):
            if any(_matches(callee, validating) for callee in argument.calls):
                continue
            reaching = frozenset(argument.names)
            if not (reaching & parameters) or (reaching & validated):
                continue
            findings.append(Finding(rule=rule, line=call.line, column=call.column))
            break
    return findings


def _sink_adjacency(function: Function, rule: StructureRule) -> list[Finding]:
    """A value built in this body, passed straight into a call that executes,
    queries or fetches.

    "Built" is one question with four spellings — an f-string, a `%` format, a
    `.format()` and a `+` over strings — and `parser.py` answers it, so this
    rule sees one kind. Four branches here would be four branches the next
    language's parser has to reproduce.
    """
    dangerous = rule.names["dangerous_calls"]
    findings: list[Finding] = []
    for call in function.calls:
        if not _matches(call.callee, dangerous):
            continue
        values = (*call.args, *(value for _, value in call.keywords))
        if any(value.kind == "interpolated" for value in values):
            findings.append(Finding(rule=rule, line=call.line, column=call.column))
    return findings


_ANALYSES = {
    ORDER_OF_OPERATIONS: _order_of_operations,
    DECISION_SHAPE: _decision_shape,
    UNVALIDATED_REACH: _unvalidated_reach,
    SINK_ADJACENCY: _sink_adjacency,
}


def _findings(unit: Unit, rules: StructureRules) -> list[tuple[Finding, Function]]:
    found: list[tuple[Finding, Function]] = []
    for function in unit.functions:
        for rule in rules.rules:
            for finding in _ANALYSES[rule.shape](function, rule):
                found.append((finding, function))
    # Total order before ids are assigned. Iterating function by function then
    # rule by rule emits in a shape order that is stable within one run and
    # wrong against the rule — the same defect `surfaces.py` records, and the
    # same fix.
    found.sort(key=lambda item: (item[0].line, item[0].rule.id, item[0].column))
    return found


def _file_hits(
    entry: FileEntry, text: str, rules: StructureRules, unit: Unit, version: str
) -> list[Hit]:
    lines = split_lines(text)
    found = _findings(unit, rules)

    # One window per body, shared by every finding in it — the same change
    # `sweep.py` and `surfaces.py` both carry. It matters more here: two
    # candidates in one function have byte-identical windows by construction,
    # so this is the common case rather than the coincidence it is there.
    windows: dict[tuple[int, int], str] = {}
    matches: list[Match] = []
    for finding, function in found:
        span = (function.line, function.end_line)
        text_window = windows.get(span)
        if text_window is None:
            text_window = block_window(lines, finding.line - 1, function.line - 1, span[1] - 1)
            windows[span] = text_window
        matches.append(Match(rule_id=finding.rule.id, line=finding.line, window=text_window))
    identifiers = assign(entry.path, matches)

    hits: list[Hit] = []
    for (finding, _), identifier in zip(found, identifiers, strict=True):
        source_line = lines[finding.line - 1] if finding.line - 1 < len(lines) else ""
        hits.append(
            Hit(
                id=identifier,
                file=entry.path,
                line=finding.line,
                layer=finding.rule.layer,
                source="structure",
                rule_id=finding.rule.id,
                precision=finding.rule.precision,
                question=" ".join(finding.rule.question.split()),
                match_excerpt=excerpt(source_line, 0, len(source_line)),
                status="unresolved",
                catalog_version=version,
                window_spec=BLOCK_WINDOW_SPEC,
            )
        )
    return hits


def structure(
    root: Path,
    rules: StructureRules,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
    parser: Parser | None = None,
) -> StructureResult:
    """Every structural candidate in `root`, and every file that would not parse.

    `excluded` is threaded to `inventory.walk`; `None` means the default set
    (M3.5 A2). A peer source must skip exactly what the other two skip, or an
    override changes scope for one and not the others.

    Binary files are inventoried but never read, and symlinks are never followed
    (`STACK.md` §5) — the same decisions, carried forward from the walk rather
    than made again here.
    """
    validate_shape_specs(SHAPES)
    reader: Parser = PythonParser() if parser is None else parser

    hits: list[Hit] = []
    unparsed: list[str] = []
    for entry in walk(root, excluded, max_bytes):
        if (
            entry.is_binary
            or entry.is_symlink
            or not entry.is_readable
            or not entry.is_regular
            or not entry.is_within_size_bound
        ):
            continue
        if not reader.applies(entry.path):
            continue
        # `os_path`, never `path`: the record is NFC, the filesystem may not be.
        raw = (root / entry.os_path).read_bytes()
        text = raw.decode("utf-8", errors="replace")
        try:
            unit = reader.parse(text, entry.path)
        except ParseFailure:
            # Recorded and continued, never raised out of the run. A hostile or
            # merely broken file must not be able to end the review — that was
            # M3.5's whole subject — and it must not pass for a clean one
            # either, which is what `unparsed` is for.
            unparsed.append(entry.path)
            continue
        hits.extend(_file_hits(entry, text, rules, unit, rules.version))
    return StructureResult(hits=hits, unparsed=sorted(unparsed))
