"""The parser seam. `STACK.md` §7, `BRIEF_M4.md` §2 and §6 Q3.

§7 requires structural analysis to sit behind a `Parser` interface with `ast` as
the first implementation, and forbids tree-sitter in v1. Q3 put the interface in
a module of its own: an interface living inside its only consumer can be reached
around without anyone noticing, and the reaching-around is the failure it exists
to prevent.

**What this module returns is a vocabulary, not a syntax tree, and that is the
decision this file exists to record.** `parse()` could have returned an
`ast.Module` and let the rules walk it. They would then be written against
CPython's node types, and the honest answer to Q3's own premise — *adding
tree-sitter later must not require touching rule logic* — would be "it would
require rewriting all of it". The interface would satisfy §7 by name and by
nothing else.

So the seam carries `Unit` -> `Function` -> `Call` / `Assignment` /
`MembershipTest` / `Return`, described in terms every language has. A second
implementation populates the same shapes from its own tree and the four rules do
not change.

**This is not the "AST description language" `BRIEF_M4.md` §3 refuses to
invent**, and the difference is worth stating because the two look alike. §3
refuses to put *rule logic* in data — a language in which a new rule shape can be
described without code — on the grounds that it would be designed around the
four rules we already have, which is P11 in the small. This is a fixed
vocabulary in code, scoped to exactly what those four rules ask about, with no
ambition to describe a fifth shape. A genuinely new shape needs Python here, and
§3 says so.

The rules that decide bytes, since this module is in `is_nfr3_path`:

  **Source order, made explicit.** `ast.walk` is breadth-first and its order is
  not source order, so nothing here uses it. Everything is collected by an
  explicit descent and then sorted by `(lineno, col_offset)`, which is source
  order and is a property of the input rather than of the traversal.

  **A function owns what is lexically inside it and not inside a nested
  function.** A helper defined inside another function is its own `Function`,
  and its calls are not attributed to the parent. Without this, a sink inside a
  nested helper would be reported against the enclosing function's body, which
  is a location a reader cannot find.

  **Module-level code is a `Function` too**, named `<module>`. FR-3.7 scopes the
  rules to a function body, and taken literally that would exempt every
  top-level script — which is most of what an agentic artifact actually is. The
  synthetic unit keeps the containment rule ("one body, no cross-function
  reasoning") while refusing the gap. It is named rather than hidden so a reader
  of a record can tell which it was.

  **A parse failure is raised, never swallowed.** `ParseFailure` reaches
  `structure.py`, which records a coverage gap and makes the run exit 2. A file
  that will not parse is not "no candidates here" — it is a file this source did
  not review, and H-1 says the two must not collapse.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Protocol

# The synthetic function that holds top-level code. Angle brackets because no
# Python identifier can collide with it, so a record naming it is unambiguous.
MODULE_SCOPE = "<module>"


class ParseFailure(Exception):
    """A source file this parser could not read.

    Not a `ValueError` and not exit 2 by itself: `structure.py` decides what a
    failure means for the run, because the artifact has to record *which* file
    went unreviewed before the exit code is worth anything.
    """


@dataclass(frozen=True)
class Argument:
    """One value at a call site or in an assignment, described rather than
    reproduced.

    The rules never see an expression. They ask four things of a value — is it a
    literal, does it come out of a call, is it built by interpolation or
    concatenation, and which names went into it — and those four are what this
    carries. A second parser can answer all four.
    """

    # "literal" | "name" | "call" | "interpolated" | "other". `interpolated`
    # covers an f-string, a `%` format, a `.format()` call and a `+` over
    # strings: rule 4 asks whether a value was *built*, and the four spellings
    # are one question. Distinguishing them here would push that decision into
    # the rules, where it would be four branches that must each be repeated by
    # the next language.
    kind: str
    # The dotted name for `name` and `call`, empty otherwise. `os.path.join`,
    # not `join` — a rule matching bare `join` would fire on any object's.
    name: str
    # For `literal`, what kind of literal: "bool", "string", "number", "bytes"
    # or "none"; empty for everything else. Rule 2 needs it and `kind` alone
    # cannot answer it — a function returning `"no"` is a lookup and one
    # returning `False` is a gate, and telling them apart is the difference
    # between that rule meaning what its docstring says and firing on any
    # function that returns a constant.
    literal_type: str
    # Every identifier appearing anywhere inside the value, in source order.
    # Rule 3 needs this: "does this path argument derive from a parameter" is a
    # question about names, not about the shape they are wrapped in.
    names: tuple[str, ...]
    # Every dotted callee invoked anywhere inside the value. Rule 3 asks whether
    # a validator was among them.
    calls: tuple[str, ...]


@dataclass(frozen=True)
class Call:
    """One call site."""

    callee: str
    line: int
    # The column, carried only so the order below can be total. `(line, callee)`
    # ties whenever one line holds two calls to the same name — `a(1); a(2)` —
    # and a stable sort then falls back to visit order, which is exactly the
    # traversal property this module claims not to depend on. A column is source
    # position, which every language has, so it costs the seam nothing.
    column: int
    args: tuple[Argument, ...]
    # Keyword arguments, sorted by keyword. Sorted rather than source-ordered on
    # purpose: `chmod(path, mode=0o600)` and `chmod(mode=0o600, path=p)` are the
    # same call, and a rule that read them differently would report a finding
    # that depends on typing order.
    keywords: tuple[tuple[str, Argument], ...]


@dataclass(frozen=True)
class Assignment:
    """One binding. Rule 1 uses these to tell whether two calls name the same
    resource through an intermediate variable."""

    targets: tuple[str, ...]
    value: Argument
    line: int


@dataclass(frozen=True)
class MembershipTest:
    """A test of one value against a literal collection — `x in ("a", "b")`,
    `x not in {...}`, or a chain of `==` against literals.

    Rule 2's syntactic signature of a denylist. `size` is what makes it a
    signature rather than a guess: a membership test over two literals is a
    branch, and one over twenty is a list somebody is maintaining.
    """

    line: int
    size: int
    negated: bool


@dataclass(frozen=True)
class Return:
    """A return, with its value described. Rule 2 asks whether a function's
    returns are boolean literals."""

    line: int
    value: Argument | None


@dataclass(frozen=True)
class Function:
    """One body the rules reason within. FR-3.7: no reasoning crosses this
    boundary in v1, and the report says so."""

    name: str
    line: int
    end_line: int
    parameters: tuple[str, ...]
    calls: tuple[Call, ...]
    assignments: tuple[Assignment, ...]
    membership_tests: tuple[MembershipTest, ...]
    returns: tuple[Return, ...]


@dataclass(frozen=True)
class Unit:
    """One parsed file."""

    language: str
    functions: tuple[Function, ...]


class Parser(Protocol):
    """What a language implementation must provide.

    Three members and no tree: `language` names what goes in a coverage-gap line
    and in `recon.json`, `applies` decides which files this parser claims, and
    `parse` produces the vocabulary above. Nothing here exposes a node type, so
    nothing above it can depend on one.
    """

    language: str

    def applies(self, relative_path: str) -> bool:
        """Whether this parser claims the file. Extension-based, and case-folded
        by the implementation: `.PY` is a Python file on a case-insensitive
        filesystem and must not become a silent coverage gap."""
        ...

    def parse(self, text: str, relative_path: str) -> Unit:
        """The file's vocabulary, or `ParseFailure`."""
        ...


def _dotted(node: ast.expr) -> str:
    """`os.path.join` for an attribute chain, `open` for a bare name, `""` for
    anything else.

    Empty rather than a placeholder: a rule comparing against `""` matches
    nothing, which is the safe direction. A placeholder like `<expr>` would be a
    string a rule could match by accident.
    """
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    parts.append(current.id)
    return ".".join(reversed(parts))


def _names_in(node: ast.AST) -> tuple[str, ...]:
    """Every identifier inside, in source order, without duplicates.

    Deduplicated because the rules ask membership questions, and a name
    appearing twice would otherwise make one value look different from an
    identical one — which reaches `window_sha256` through nothing, but reaches a
    reader's confidence directly.
    """
    found: list[tuple[int, int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.append((child.lineno, child.col_offset, child.id))
        elif isinstance(child, ast.Attribute):
            dotted = _dotted(child)
            if dotted:
                found.append((child.lineno, child.col_offset, dotted))
    seen: set[str] = set()
    ordered: list[str] = []
    for _, _, name in sorted(found):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def _calls_in(node: ast.AST) -> tuple[str, ...]:
    """Every dotted callee invoked inside, in source order, without
    duplicates."""
    found: list[tuple[int, int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            callee = _dotted(child.func)
            if callee:
                found.append((child.lineno, child.col_offset, callee))
    seen: set[str] = set()
    ordered: list[str] = []
    for _, _, name in sorted(found):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


# The four spellings of "this value was built rather than given". One question,
# so one kind — see `Argument.kind`.
_STRING_FORMAT_METHODS = frozenset({"format", "format_map"})


def _is_interpolated(node: ast.expr) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod | ast.Add):
        # `%` over a string, or `+` joining one. The left side decides: `a % b`
        # where a is a literal string is a format, and `path + name` is a join.
        # A non-string `+` (two integers) is not interpolation and does not
        # reach rule 4.
        return _looks_stringy(node.left) or _looks_stringy(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in _STRING_FORMAT_METHODS
    return False


def _looks_stringy(node: ast.expr) -> bool:
    """Whether a node is a string literal, an f-string, or built from one.

    Deliberately syntactic. Deciding whether a *variable* holds a string is
    dataflow, which FR-3.7 puts in v2, and guessing here would produce a rule
    that appears to work.
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp):
        return _looks_stringy(node.left) or _looks_stringy(node.right)
    return False


def _literal_type(value: object) -> str:
    """What kind of literal, in words every language has.

    `bool` is tested before `int` because in Python `True` is an `int`, and a
    boolean reported as a number would make rule 2 — which asks whether a
    function's returns are booleans — silently never fire.
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, int | float | complex):
        return "number"
    if value is None:
        return "none"
    return "other"


def _argument(node: ast.expr) -> Argument:
    literal_type = ""
    if _is_interpolated(node):
        kind = "interpolated"
        name = ""
    elif isinstance(node, ast.Constant):
        kind = "literal"
        name = ""
        literal_type = _literal_type(node.value)
    elif isinstance(node, ast.Call):
        kind = "call"
        name = _dotted(node.func)
    elif isinstance(node, ast.Name | ast.Attribute):
        kind = "name"
        name = _dotted(node)
    else:
        kind = "other"
        name = ""
    return Argument(
        kind=kind,
        name=name,
        literal_type=literal_type,
        names=_names_in(node),
        calls=_calls_in(node),
    )


def _literal_collection_size(node: ast.expr) -> int | None:
    """The element count of a literal list, tuple or set, or `None` if the node
    is not one.

    `None` rather than `0`: an empty literal collection is a real thing to write
    and a real thing for rule 2 to see, and collapsing it with "not a
    collection" would make the one case that is obviously a bug invisible.
    """
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return len(node.elts)
    if isinstance(node, ast.Dict):
        return len(node.keys)
    return None


class _BodyCollector(ast.NodeVisitor):
    """Everything lexically inside one body, stopping at a nested function.

    The stop is the point. Recursing into a nested `def` would attribute its
    calls to the enclosing function, and a record pointing at a body that does
    not contain the call is worse than no record.
    """

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.assignments: list[Assignment] = []
        self.membership_tests: list[MembershipTest] = []
        self.returns: list[Return] = []

    # Nested definitions are their own bodies and are collected separately by
    # `_definitions`. Not visiting them here is what keeps the two from
    # double-counting. The argument is named `_node` in each: these four exist
    # to *not* descend, so the unused parameter is the behaviour rather than an
    # oversight, and `ast.NodeVisitor` dispatches positionally so the name is
    # free. `ruff` would otherwise report ARG002 and be right to.
    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        # A class body is not a function body, and its methods are collected as
        # their own functions. Descending would put a method's calls in the
        # module scope.
        return

    def visit_Call(self, node: ast.Call) -> None:
        callee = _dotted(node.func)
        if callee:
            self.calls.append(
                Call(
                    callee=callee,
                    line=node.lineno,
                    column=node.col_offset,
                    args=tuple(_argument(arg) for arg in node.args),
                    keywords=tuple(
                        sorted(
                            (
                                (keyword.arg, _argument(keyword.value))
                                for keyword in node.keywords
                                if keyword.arg is not None
                            ),
                            key=lambda item: item[0],
                        )
                    ),
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        targets = tuple(name for name in (_dotted(target) for target in node.targets) if name)
        if targets:
            self.assignments.append(
                Assignment(targets=targets, value=_argument(node.value), line=node.lineno)
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if not isinstance(operator, ast.In | ast.NotIn):
                continue
            size = _literal_collection_size(comparator)
            if size is None:
                continue
            self.membership_tests.append(
                MembershipTest(line=node.lineno, size=size, negated=isinstance(operator, ast.NotIn))
            )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.returns.append(
            Return(line=node.lineno, value=_argument(node.value) if node.value else None)
        )
        self.generic_visit(node)


_Definition = ast.FunctionDef | ast.AsyncFunctionDef


def _parameters(node: _Definition) -> tuple[str, ...]:
    spec = node.args
    ordered = [*spec.posonlyargs, *spec.args, *spec.kwonlyargs]
    if spec.vararg:
        ordered.append(spec.vararg)
    if spec.kwarg:
        ordered.append(spec.kwarg)
    return tuple(argument.arg for argument in ordered)


def _collect(body: list[ast.stmt]) -> _BodyCollector:
    collector = _BodyCollector()
    for statement in body:
        collector.visit(statement)
    return collector


def _sorted_calls(calls: list[Call]) -> tuple[Call, ...]:
    """Source order, stated rather than inherited.

    The collector appends in visit order, which is source order today. Sorting
    makes that a property of the output instead of a property of
    `ast.NodeVisitor`, so a future change to how the collector descends cannot
    quietly renumber every ordinal in the ledger (NFR-3).

    `(line, column)` and not `(line, callee)`. The first draft used the callee
    and was caught by a test written against `write(safe_path(p))`: sorting by
    name put the inner call first, which is not source order and is not what a
    reader of the record sees. Worse, it ties on `a(1); a(2)` and falls back to
    visit order — the traversal dependency this function exists to remove,
    surviving inside the fix for it.
    """
    return tuple(sorted(calls, key=lambda call: (call.line, call.column)))


def _function(node: _Definition) -> Function:
    collected = _collect(node.body)
    return Function(
        name=node.name,
        line=node.lineno,
        # `end_lineno` is optional in the ast types and always present in
        # practice on 3.11+. Falling back to `lineno` makes a one-line body,
        # which is wrong but bounded; `None` reaching the window would be a
        # crash inside a source that is supposed to record and continue.
        end_line=node.end_lineno or node.lineno,
        parameters=_parameters(node),
        calls=_sorted_calls(collected.calls),
        assignments=tuple(collected.assignments),
        membership_tests=tuple(collected.membership_tests),
        returns=tuple(collected.returns),
    )


def _definitions(tree: ast.Module) -> list[_Definition]:
    return [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def _module_function(tree: ast.Module) -> Function:
    """Top-level code as a body of its own. See the module docstring."""
    collected = _collect(tree.body)
    lines = [node.end_lineno or node.lineno for node in tree.body]
    return Function(
        name=MODULE_SCOPE,
        line=1,
        end_line=max(lines) if lines else 1,
        parameters=(),
        calls=_sorted_calls(collected.calls),
        assignments=tuple(collected.assignments),
        membership_tests=tuple(collected.membership_tests),
        returns=tuple(collected.returns),
    )


class PythonParser:
    """`ast`, the only implementation in v1 (`STACK.md` §7)."""

    language = "python"

    def applies(self, relative_path: str) -> bool:
        """Case-folded: `.PY` is a Python file wherever the filesystem says so,
        and treating it as unparsed would be a coverage gap created by a
        filename (`STACK.md` §4 makes case sensitivity a finding class here,
        not a portability note)."""
        return relative_path.lower().endswith(".py")

    def parse(self, text: str, relative_path: str) -> Unit:
        """The file's vocabulary, or `ParseFailure` — for *every* way a file can
        fail to be read here, not only a syntax error.

        **`RecursionError` and `MemoryError` are caught around parsing *and*
        extraction**, and the second half is the one that was missing. Found in
        review: a valid 3 KB file — one expression of 1,500 `p+p+…` terms,
        which CPython compiles — ended `secrev structure` with exit 3. `ast.parse`
        runs in C and survives that depth; `_BodyCollector` and `_looks_stringy`
        recurse in Python and hit the 1,000-frame limit long before. Deeper input
        fails inside `ast.parse` itself, with either error.

        That is M3.5's C1 and C2 again: hostile input classified as a bug in the
        tool, and one file ending the review of every other. A target plants it
        once and the structural review of the whole tree is gone. Caught here,
        per file, the run continues and the file lands in `unparsed`, which
        `cli.py` turns into a named gap and exit 2.

        Deliberately not answered by raising the recursion limit: that moves the
        threshold to a depth the attacker also chooses, and trades a clean
        exception for a C-stack overflow that kills the process.
        """
        try:
            tree = ast.parse(text, filename=relative_path)
            functions = [_module_function(tree)]
            functions.extend(_function(node) for node in _definitions(tree))
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            # ValueError covers a NUL byte reaching `compile`, which a decoded
            # binary can carry even after the 5% classification let the file
            # through. All four mean the same thing to the caller: not reviewed.
            raise ParseFailure(f"{relative_path}: {type(exc).__name__}: {exc}") from exc

        # `(line, name)`, so two definitions on one line — a `def` inside a
        # one-line `if`, which is legal — cannot swap between runs.
        functions.sort(key=lambda function: (function.line, function.name))
        return Unit(language=self.language, functions=tuple(functions))
