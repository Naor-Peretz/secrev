"""The parser seam. `STACK.md` §7, `BRIEF_M4.md` §6 Q3.

Two kinds of assertion live here and they are not the same kind of claim.

The first is about the **seam**: `ast` must not be imported anywhere under
`src/secrev/` except `parser.py`. §7 asks for an interface, and an interface
that its neighbours can reach around is a comment. M4 widened
`ALLOWED_IMPORTS` in `scripts/self_check.py` to admit `ast` for the whole
package, because that list has no per-module scoping and inventing some inside a
gate script would be a new mechanism; the rule that actually matters is asserted
here instead, so the widening is paired with the narrowing that keeps it honest.

The rest are about the **vocabulary**: the shapes `structure.py` reasons over
are what this module claims they are. They are written against the described
values rather than against `ast` nodes on purpose — a test that reached for
`ast.Call` would be the same mistake the module exists to avoid, one layer up.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from secrev.parser import (
    MODULE_SCOPE,
    Function,
    ParseFailure,
    PythonParser,
    Unit,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "src" / "secrev"


@pytest.fixture(scope="module")
def parser() -> PythonParser:
    return PythonParser()


def parse(parser: PythonParser, source: str) -> Unit:
    return parser.parse(source, "sample.py")


def named(unit: Unit, name: str) -> Function:
    matches = [function for function in unit.functions if function.name == name]
    assert len(matches) == 1, f"expected exactly one {name}, found {[f.name for f in matches]}"
    return matches[0]


# --- the seam ------------------------------------------------------------


def test_only_the_parser_imports_ast() -> None:
    """`STACK.md` §7's interface, enforced rather than described.

    This is the control paired with M4's widening of `ALLOWED_IMPORTS`. That
    list admits `ast` for the whole package; if `structure.py` or `cli.py` ever
    imports it, the rules stop being written against the vocabulary and start
    being written against CPython's node types — at which point adding a second
    language means rewriting them, which is the one thing Q3's premise says must
    not happen. Nothing would be red. That is why this is a test.
    """
    offenders = []
    for path in sorted(SOURCES.glob("*.py")):
        if path.name == "parser.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "ast" or name.startswith("ast.") for name in names):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        f"only parser.py may import ast — the §7 interface is reachable around: {offenders}"
    )


def test_the_parser_exposes_no_ast_node_in_its_vocabulary(parser: PythonParser) -> None:
    """The other half of the seam, and the one a reader is likelier to break.

    Keeping `import ast` out of the neighbours means nothing if a `Unit` hands
    them a node to walk. Every value reachable from a parsed unit must be a
    built-in or one of this module's own frozen shapes.
    """
    unit = parse(parser, "import os\n\n\ndef f(p):\n    os.chmod(p, 0o600)\n    return True\n")
    for function in unit.functions:
        for call in function.calls:
            for argument in (*call.args, *(value for _, value in call.keywords)):
                assert not isinstance(argument, ast.AST)
                assert isinstance(argument.kind, str)
                assert isinstance(argument.names, tuple)


# --- what a function is --------------------------------------------------


def test_top_level_code_is_a_body_of_its_own(parser: PythonParser) -> None:
    """FR-3.7 scopes the rules to a function body. Read literally that exempts
    every top-level script, which is most of what an agentic artifact is — so
    module scope is a `Function`, named rather than hidden."""
    unit = parse(parser, "import os\n\nos.chmod('x', 0o777)\n")
    module = named(unit, MODULE_SCOPE)
    assert [call.callee for call in module.calls] == ["os.chmod"]


def test_a_nested_function_is_not_folded_into_its_parent(parser: PythonParser) -> None:
    """A record pointing at a body that does not contain the call is worse than
    no record."""
    source = "def outer():\n    def inner():\n        run(1)\n\n    other(2)\n"
    unit = parse(parser, source)
    assert [call.callee for call in named(unit, "outer").calls] == ["other"]
    assert [call.callee for call in named(unit, "inner").calls] == ["run"]


def test_a_method_belongs_to_itself_and_not_to_the_module(parser: PythonParser) -> None:
    """A class body is not a function body. Descending into one would file every
    method's calls under module scope, where nobody would look for them."""
    source = "class A:\n    def method(self):\n        run(1)\n"
    unit = parse(parser, source)
    assert named(unit, MODULE_SCOPE).calls == ()
    assert [call.callee for call in named(unit, "method").calls] == ["run"]


def test_a_lambda_body_does_not_leak_into_the_enclosing_function(parser: PythonParser) -> None:
    source = "def f():\n    g = lambda: run(1)\n    return g\n"
    unit = parse(parser, source)
    assert [call.callee for call in named(unit, "f").calls] == []


# --- determinism ---------------------------------------------------------


def test_calls_come_back_in_source_order(parser: PythonParser) -> None:
    """`ast.walk` is breadth-first, so nothing here uses it for ordering. The
    sort makes source order a property of the output rather than of
    `NodeVisitor`'s descent — an ordering inherited from a traversal is one a
    refactor can change silently, and every ordinal in the ledger hangs on it
    (NFR-3)."""
    source = "def f():\n    a()\n    b()\n    c()\n    d()\n"
    unit = parse(parser, source)
    assert [call.callee for call in named(unit, "f").calls] == ["a", "b", "c", "d"]


def test_two_calls_to_one_name_on_one_line_keep_their_order(parser: PythonParser) -> None:
    """The tie case, and the reason the sort key is `(line, column)`.

    `(line, callee)` ties here, and a stable sort then falls back to the
    collector's visit order — a traversal property, which is precisely what
    sorting was supposed to remove. It passed anyway, because visit order *is*
    source order today. A key that is only correct while an implementation
    detail holds is the shape of defect NFR-3 cannot afford.
    """
    unit = parse(parser, "def f():\n    a(1); a(2)\n")
    assert [call.args[0].name or call.column for call in named(unit, "f").calls] == [4, 10]


def test_an_outer_call_comes_before_the_call_nested_in_its_argument(
    parser: PythonParser,
) -> None:
    """Source order, which is also reading order: `write(...)` is what the line
    says it does. Sorting by name put `safe_path` first — deterministic, and
    not the order anyone reading the record would expect."""
    unit = parse(parser, "def f(p):\n    write(safe_path(p, root))\n")
    assert [call.callee for call in named(unit, "f").calls] == ["write", "safe_path"]


def test_two_parses_of_one_source_agree(parser: PythonParser) -> None:
    source = "def f(p):\n    q = build(p)\n    write(q, mode=1, flags=2)\n    return True\n"
    assert parse(parser, source) == parse(parser, source)


def test_keywords_are_sorted_so_typing_order_is_not_a_finding(parser: PythonParser) -> None:
    """`chmod(p, mode=0o600)` and `chmod(mode=0o600, path=p)` are the same call.
    A rule reading them differently would report a difference that exists only
    in how someone typed it."""
    one = parse(parser, "def f(p):\n    chmod(p, mode=1, follow=2)\n")
    two = parse(parser, "def f(p):\n    chmod(p, follow=2, mode=1)\n")
    assert [key for key, _ in named(one, "f").calls[0].keywords] == ["follow", "mode"]
    assert named(one, "f").calls[0].keywords == named(two, "f").calls[0].keywords


# --- how a value is described --------------------------------------------


def test_the_four_spellings_of_a_built_value_are_one_kind(parser: PythonParser) -> None:
    """Rule 4 asks whether a value was *built*, not how. Four kinds here would
    be four branches in the rule, and each would have to be repeated by the next
    language's parser."""
    source = (
        "def f(name):\n"
        "    run(f'x{name}')\n"
        "    run('x%s' % name)\n"
        "    run('x{}'.format(name))\n"
        "    run('x' + name)\n"
    )
    unit = parse(parser, source)
    kinds = [call.args[0].kind for call in named(unit, "f").calls if call.callee == "run"]
    assert kinds == ["interpolated"] * 4


def test_adding_two_numbers_is_not_interpolation(parser: PythonParser) -> None:
    """The negative for the rule above, and the one that keeps it from firing on
    arithmetic. Deciding whether a *variable* holds a string is dataflow, which
    FR-3.7 puts in v2 — so the test is syntactic and says so."""
    unit = parse(parser, "def f(a, b):\n    run(a + b)\n")
    assert named(unit, "f").calls[0].args[0].kind == "other"


def test_a_dotted_callee_keeps_its_namespace(parser: PythonParser) -> None:
    """`os.path.join`, never bare `join` — a rule matching the short name would
    fire on any object's method of that name."""
    unit = parse(parser, "def f(p):\n    os.path.join(p)\n")
    assert named(unit, "f").calls[0].callee == "os.path.join"


def test_an_unnameable_callee_is_empty_rather_than_a_placeholder(parser: PythonParser) -> None:
    """`""`, not `<expr>`. A placeholder is a string a rule can match by
    accident; the empty name matches nothing, which is the safe direction."""
    unit = parse(parser, "def f(handlers):\n    handlers[0]()\n")
    assert named(unit, "f").calls == ()


def test_a_value_carries_the_names_and_calls_inside_it(parser: PythonParser) -> None:
    """Rule 3 asks "did this reach a validator", which is a question about what
    is inside a value rather than about its shape."""
    unit = parse(parser, "def f(p):\n    write(safe_path(p, root))\n")
    argument = named(unit, "f").calls[0].args[0]
    assert argument.kind == "call"
    assert argument.name == "safe_path"
    # The callee is an identifier inside the value, so it is in `names` too —
    # `names` is every identifier, not every *operand*. A rule asking "is a
    # parameter among these" is unaffected; a rule asking "was a validator
    # called" should read `calls`, which is why both fields exist.
    assert argument.names == ("safe_path", "p", "root")
    assert argument.calls == ("safe_path",)


# --- the shapes rules 1 and 2 ask about ----------------------------------


def test_a_membership_test_over_a_literal_collection_is_recorded(parser: PythonParser) -> None:
    unit = parse(parser, "def f(x):\n    return x in ('a', 'b', 'c')\n")
    tests = named(unit, "f").membership_tests
    assert len(tests) == 1
    assert tests[0].size == 3 and not tests[0].negated


def test_a_membership_test_against_a_variable_is_not_recorded(parser: PythonParser) -> None:
    """The negative. Rule 2's signature is a literal collection written into the
    source — a check against a value loaded from somewhere is a different
    question and answering it here would be a guess."""
    unit = parse(parser, "def f(x, deny):\n    return x in deny\n")
    assert named(unit, "f").membership_tests == ()


def test_an_empty_literal_collection_is_a_size_and_not_an_absence(parser: PythonParser) -> None:
    """`None` and `0` had to stay apart: an empty denylist is a real thing to
    write and the one case that is obviously a bug. Collapsing it into "not a
    collection" would make it the only one nothing can see."""
    unit = parse(parser, "def f(x):\n    return x in ()\n")
    assert [test.size for test in named(unit, "f").membership_tests] == [0]


def test_assignments_carry_their_target_and_value(parser: PythonParser) -> None:
    """Rule 1 needs these to tell whether two calls name the same resource
    through an intermediate variable."""
    unit = parse(parser, "def f(p):\n    handle = open(p)\n")
    assignment = named(unit, "f").assignments[0]
    assert assignment.targets == ("handle",)
    assert assignment.value.kind == "call" and assignment.value.name == "open"


def test_returns_are_described_including_the_bare_one(parser: PythonParser) -> None:
    unit = parse(parser, "def f(x):\n    if x:\n        return True\n    return\n")
    returns = named(unit, "f").returns
    assert [r.value.kind if r.value else None for r in returns] == ["literal", None]


def test_a_function_carries_its_parameters(parser: PythonParser) -> None:
    unit = parse(parser, "def f(a, /, b, *args, c=1, **kw):\n    pass\n")
    assert named(unit, "f").parameters == ("a", "b", "c", "args", "kw")


def test_a_function_carries_the_span_its_window_will_use(parser: PythonParser) -> None:
    """`block-20` is anchored on these two numbers (BRIEF_M4.md §6 Q2)."""
    unit = parse(parser, "def f():\n    a()\n    b()\n")
    function = named(unit, "f")
    assert (function.line, function.end_line) == (1, 3)


# --- failure -------------------------------------------------------------


def test_a_file_that_does_not_parse_raises_rather_than_returning_nothing(
    parser: PythonParser,
) -> None:
    """H-1, at the level of one file. Returning an empty `Unit` would make "this
    file has no candidates" and "this file was never reviewed" the same value,
    and the caller could not tell them apart afterwards."""
    with pytest.raises(ParseFailure) as failure:
        parser.parse("def f(\n", "broken.py")
    assert "broken.py" in str(failure.value)


def test_a_nul_byte_raises_the_same_failure(parser: PythonParser) -> None:
    """A decoded binary can carry a NUL even after the 5% rule lets the file
    through, and `ast.parse` raises `ValueError` rather than `SyntaxError` for
    it. Two exception types, one meaning to the caller: not reviewed."""
    with pytest.raises(ParseFailure):
        parser.parse("x = 1\0\n", "nul.py")


def test_depth_that_python_compiles_is_a_parse_failure_not_a_crash(
    parser: PythonParser,
) -> None:
    """The half the first version missed. `ast.parse` survives 1,500 terms; the
    collector's own recursion does not, so the error came from *extraction*,
    outside the `try` that only wrapped parsing."""
    deep = "def f(p):\n    x = " + "+".join(["p"] * 1500) + "\n    open(x)\n"
    with pytest.raises(ParseFailure) as failure:
        parser.parse(deep, "deep.py")
    assert "RecursionError" in str(failure.value)


def test_depth_that_defeats_ast_parse_itself_is_a_parse_failure(parser: PythonParser) -> None:
    """The other half: deep enough that `ast.parse` raises before any
    extraction runs. Either error type, same meaning to the caller."""
    with pytest.raises(ParseFailure):
        parser.parse("x = " + "(" * 200_000 + "1" + ")" * 200_000 + "\n", "deeper.py")


def test_the_parser_claims_python_whatever_the_case_of_the_extension(
    parser: PythonParser,
) -> None:
    """`STACK.md` §4 makes case sensitivity a finding class here rather than a
    portability note. A `.PY` file treated as unparseable would be a coverage
    gap manufactured by a filename."""
    assert parser.applies("a/b.py")
    assert parser.applies("a/B.PY")
    assert not parser.applies("a/b.pyi.txt")
