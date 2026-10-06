"""Backstop for STACK.md §2.1 — the tool may not contain what it flags.

AST-based rather than regex-based on purpose: the project's own argument
(D-11) is that presence-of-a-token questions and structure questions are
different, and `shell=True` is a structure question. A grep here would be
the exact mistake the catalog is designed not to make.

Runs over src/secrev only. Exits 1 listing every violation; 0 when clean.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "secrev"

BANNED_CALLS = {
    "eval": "STACK.md §2.1 — no eval",
    "exec": "STACK.md §2.1 — no exec",
    "compile": "STACK.md §2.1 — no dynamic compilation",
    # Absent until M3.5, and a one-word bypass of every import rule below:
    # `__import__("socket")` needs no import statement to flag.
    "__import__": "STACK.md §2.1 — no dynamic import",
}
BANNED_ATTRS = {
    ("pickle", "load"): "STACK.md §2.1 — no pickle",
    ("pickle", "loads"): "STACK.md §2.1 — no pickle",
    ("marshal", "load"): "STACK.md §2.1 — no marshal",
    ("marshal", "loads"): "STACK.md §2.1 — no marshal",
    # `yaml` is handled by `ALLOWED_YAML_ATTRS` rather than by rows here. The
    # three that used to sit at this spot — `load`, `unsafe_load`, `full_load` —
    # left `load_all` and `unsafe_load_all` passing, both measured.
    # `importlib.import_module` is `__import__` with a nicer spelling.
    ("importlib", "import_module"): "STACK.md §2.1 — no dynamic import",
}

# Process execution through `os`, which had no entry at all until M3.5 — so
# `os.system(cmd)` passed a gate whose entire subject is process execution.
#
# **An allowlist since a third review, and the previous comment here said why
# it had to become one.** It read: "`os` is a large surface and its dangerous
# members cannot be enumerated with confidence... nothing here should read as
# though the question were closed." That was accurate and it stayed a denylist
# anyway, through two passes, because each round of bypasses was answered by
# widening the list that had just failed.
#
# The package calls exactly two `os` members — `os.replace` in `cli.py` and
# `os.walk` in `inventory.py`. `os.sep` is here for completeness and is never a
# call, so it never reaches the test below. Two permitted names against a module
# with several hundred is the difference between guessing at what is dangerous
# and stating what is used.
ALLOWED_OS_ATTRS = frozenset({"replace", "walk", "sep"})

# Mappings that hold callables by name, where a subscript is a member lookup
# rather than an element access. `__dict__` is matched by suffix so it catches
# any object's, not just a module's.
NAMESPACE_LOOKUPS = frozenset({"globals", "locals", "vars", "sys.modules"})

# `subprocess` with an argument list is correct (`STACK.md` §2.1 forbids a shell
# *string*), but an argv whose first element is a shell and whose second is `-c`
# is a shell string wearing a list. Matched by shape rather than by a list of
# interpreter names alone: the `-c` is what makes the rest of the argv a script.
_SHELL_BINARIES = ("sh", "bash", "zsh", "dash", "ksh", "csh", "tcsh", "fish")
# **An allowlist, since a second review.** The denylist this replaces named six
# modules, and eleven further bypasses were measured walking past it: two
# third-party HTTP clients for egress, a foreign-function-interface module and a
# pseudo-terminal helper for process execution, a persistent-mapping module that
# deserialises the same way `pickle` does, and the async API's shell variant.
# Each is answered by one more row, and the next one is answered by the row
# after that — the denylist treadmill P3 exists to refuse, and which the `os`
# table's own comment already admitted this file was on. That table is now
# `ALLOWED_OS_ATTRS` below, which is where the admission was finally acted on
# rather than repeated.
#
# Note while editing this paragraph that the self-application guard reads it and
# cannot tell a module *named as a finding* from one being imported. It refused
# an earlier draft that spelled those client libraries out. Describing them is
# the right answer rather than widening the guard: what it protects is worth
# more than the phrasing, which is the same call `CLAUDE.md` records for its own
# setup-advice assertion.
#
# The allowlist is cheap here in a way it is not in general: `src/secrev`
# imports sixteen standard-library modules and one third-party package, and that
# list is stable because `STACK.md` makes a new runtime dependency a documented
# decision. So the set is small, and anything outside it is a question rather
# than an assumption.
#
# **The process module is on this list, and an earlier draft left it off.** No
# module under `src/secrev` imports it, so omitting it cost nothing there and
# looked like free strictness — `recon.py`'s docstring has claimed that property
# since M1. But `STACK.md` §2.1 forbids "subprocess with a shell string", not the
# module: an argument list is the *correct* form, and `scan()` is pointed at
# trees other than `src/secrev`. Refusing the import enforces something stricter
# than the binding document, decided here rather than there.
#
# `test_clean_source_still_passes` caught it, which is exactly the job it was
# written for, and the trap is already described two paragraphs down in
# `_check`: a rule that fails the gate on good code is a rule someone deletes.
# Whether `src/secrev` should be *held* to importing no process module is a
# `STACK.md` amendment and is raised rather than taken here.
#
# Written as full dotted paths, so `importlib.metadata` is permitted while bare
# `importlib` is not: `importlib.import_module` is `__import__` with a nicer
# spelling, and `BANNED_ATTRS` already says so.
#
# `ast` joined in M4 and is not an amendment: `STACK.md` §2 already names it in
# the stdlib list this project uses, and §7 *requires* the structural source to
# sit behind a `Parser` interface with `ast` as the first implementation. The
# allowlist simply had no `src/` module importing it until now — the same shape
# as `subprocess` in M3.5, where the entry was missing rather than the rule.
#
# It is permitted here for the whole package because this list has no per-module
# scoping and inventing some would be a new mechanism inside a gate script. The
# narrower rule that actually matters — **only `parser.py` may import it**, or
# the interface §7 requires can be reached around without anyone noticing — is
# asserted in `tests/test_parser.py` instead.
ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "argparse",
        "ast",
        "collections.abc",
        "dataclasses",
        "datetime",
        "hashlib",
        "importlib.metadata",
        "json",
        "os",
        "pathlib",
        "re",
        "subprocess",
        "sys",
        "tempfile",
        "tomllib",
        "typing",
        "unicodedata",
        "yaml",
    }
)

# The only `yaml` members this codebase uses. An allowlist rather than the three
# banned spellings it replaces, because `yaml.load`, `yaml.unsafe_load` and
# `yaml.full_load` were named while the two `_all` variants were not — and those
# contradict "safe_load only" as directly as the ones that were listed. Naming
# what is permitted needs no such foresight.
ALLOWED_YAML_ATTRS = frozenset({"safe_load", "YAMLError"})


def _import_allowed(module: str) -> bool:
    """Whether `src/secrev` may import this module.

    `secrev.*` by prefix: the package's own modules are the thing being checked,
    not a dependency, and enumerating them here would mean editing this file
    every time one is added.
    """
    return module in ALLOWED_IMPORTS or module.split(".", maxsplit=1)[0] == "secrev"


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


class Visitor(ast.NodeVisitor):
    """Resolves names before testing them.

    The M3.5 rewrite. Before it, every check tested the *spelling* at the call
    site: a table keyed on `(module, attribute)` matched a fully-spelled call
    and missed the identical call reached through an import alias, or bound
    directly into the module namespace by a `from ... import ...`. Five of the
    nine measured bypasses were that single defect wearing different clothes,
    so they are closed by one mechanism rather than by five more table rows —
    which is the difference between answering P3 and postponing it. The
    concrete spellings live in `tests/test_self_check.py`, where they are
    executed rather than described.

    `aliases` maps a local name to the dotted path it was bound to, and every
    call resolves through it first. It records imports and simple assignments:
    `run = os.system` followed by `run(cmd)` was the last of eleven bypasses a
    second review measured still passing, and it was recorded here as a stated
    limit rather than closed. Six lines closed it, which is a poor trade against
    leaving a documented hole where the document is the only thing holding it.

    **The limit that remains, stated rather than hidden.** Only a name bound
    directly to a dotted path is followed. A member reached through a container,
    an element of a list, or the return value of a function is not — those are
    not enumerable, and pursuing them is the treadmill `ALLOWED_IMPORTS` exists
    to step off. What bounds the residue is that an aliased member must still
    come from an imported module, and the import allowlist decides which those
    are. A checker claiming more reach than it has is worse than one whose limit
    is written down.
    """

    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.hits: list[tuple[int, str]] = []
        self.aliases: dict[str, str] = {}

    def _flag(self, node: ast.AST, why: str) -> None:
        self.hits.append((getattr(node, "lineno", 0), why))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.aliases[alias.asname or alias.name.split(".")[0]] = alias.name
            if not _import_allowed(alias.name):
                self._flag(
                    node,
                    f"import {alias.name} — not in ALLOWED_IMPORTS (STACK.md §2.1). "
                    "A new runtime dependency is a STACK.md decision; add it there first",
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if not _import_allowed(mod):
            self._flag(
                node,
                f"from {mod} import ... — not in ALLOWED_IMPORTS (STACK.md §2.1). "
                "A new runtime dependency is a STACK.md decision; add it there first",
            )
        for alias in node.names:
            # `from os import *` binds every public name with no statement
            # naming any of them, so the alias map — and therefore every check
            # that resolves through it — sees nothing at all. There is no
            # spelling of this that can be resolved, which makes it a question
            # rather than a miss.
            if alias.name == "*":
                self._flag(
                    node,
                    f"from {mod} import * — STACK.md §2.1, a wildcard import binds names "
                    "this checker cannot resolve; import what is used",
                )
                continue
            dotted = f"{mod}.{alias.name}" if mod else alias.name
            self.aliases[alias.asname or alias.name] = dotted
            # No second test on the dotted form. Under the old denylist this is
            # where a submodule bound under an unexpected name was caught; under
            # an allowlist the check on `mod` above already decided it, and
            # testing `collections.abc.Callable` against a list of *modules*
            # would refuse a legitimate import of a name from a permitted one.
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Bind a plain name to the dotted path assigned to it.

        `run = os.system` binds `system` under a name no table can match, and
        `run(cmd)` then reaches `visit_Call` as a bare `ast.Name` whose id is in
        no list. Resolving it here means `ALLOWED_OS_ATTRS` does the work,
        rather than a new entry for every spelling of the rebinding.

        Only `name = <dotted>`. A tuple target, a subscript, or a call on the
        right is left alone: `_dotted` returns "" for anything that is not a
        Name or an Attribute chain, so those simply do not bind.
        """
        dotted = _dotted(node.value)
        if dotted:
            head, _, rest = dotted.partition(".")
            resolved = self.aliases.get(head, head)
            full = f"{resolved}.{rest}" if rest else resolved
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.aliases[target.id] = full
        self.generic_visit(node)

    def _check(self, node: ast.Call, dotted: str, shown: str) -> None:
        """`dotted` is the resolved path; `shown` is what the source wrote."""
        base, _, attr = dotted.rpartition(".")
        base = base.split(".")[0]
        if not base:
            return

        if why := BANNED_ATTRS.get((base, attr)):
            self._flag(node, f"{shown}() — {why}")

        # A banned builtin reached through the `builtins` module. `BANNED_CALLS`
        # is keyed on a bare name, so `builtins.eval(data)` arrived here as an
        # attribute on a module nothing had an opinion about, and passed.
        if base == "builtins" and (why := BANNED_CALLS.get(attr)):
            self._flag(node, f"{shown}() — {why}")

        # Allowlisted rather than listed: every `yaml` member but the two this
        # codebase uses is a question. `yaml.load_all` and `yaml.unsafe_load_all`
        # were both measured passing the three-row denylist this replaces.
        if base == "yaml" and attr not in ALLOWED_YAML_ATTRS:
            self._flag(
                node,
                f"{shown}() — STACK.md §2.1, yaml.safe_load only "
                f"(permitted: {', '.join(sorted(ALLOWED_YAML_ATTRS))})",
            )

        if base == "os" and attr not in ALLOWED_OS_ATTRS:
            self._flag(
                node,
                f"{shown}() — STACK.md §2.1, not in ALLOWED_OS_ATTRS "
                f"(permitted: {', '.join(sorted(ALLOWED_OS_ATTRS))})",
            )

        if base != "subprocess":
            return

        for kw in node.keywords:
            if kw.arg == "shell" and not (
                isinstance(kw.value, ast.Constant) and kw.value.value is False
            ):
                self._flag(node, f"{shown}(shell=...) — STACK.md §2.1, argument lists only")

        # The first argument, when it is definitely a string.
        #
        # This asked only whether it was an `ast.Constant`, and an interpolated
        # string is an `ast.JoinedStr`, so a formatted command went straight
        # through — the measured M3.5 bypass.
        #
        # The first repair was worse: demand a literal list and flag everything
        # else. That is allowlist polarity, which H-2 usually wants, and here it
        # is wrong — `subprocess.run(argv)` and `subprocess.run(build_argv())`
        # are the *correct* forms, and flagging them would fail the gate on good
        # code, which is how a rule ends up deleted. The control test caught it
        # one round after I wrote the hazard into that test's own docstring.
        #
        # So: flag what is certainly a string, not what is not certainly a list.
        # **The limit, stated rather than implied:** a string built by
        # concatenation, `%`, `.format()` or `.join()` is not recognised here.
        # Those are not enumerable, and `shell=` above is the check that
        # actually carries this rule.
        first = node.args[0] if node.args else None

        # An argv that *is* a shell string: `["/bin/sh", "-c", cmd]`. The list
        # form is the correct one and passes every check above, which is exactly
        # why this shape is worth naming — it satisfies the letter of "pass an
        # argument list" while handing a shell a script to parse.
        if isinstance(first, ast.List):
            head = first.elts[0] if first.elts else None
            binary = (
                head.value.rpartition("/")[2]
                if isinstance(head, ast.Constant) and isinstance(head.value, str)
                else ""
            )
            dash_c = any(
                isinstance(element, ast.Constant) and element.value == "-c"
                for element in first.elts[1:]
            )
            if binary in _SHELL_BINARIES and dash_c:
                self._flag(
                    node,
                    f"{shown}([{binary!r}, '-c', ...]) — STACK.md §2.1, an argv whose "
                    "first element is a shell and whose second is -c is a shell string",
                )

        if isinstance(first, ast.JoinedStr) or (
            isinstance(first, ast.Constant) and isinstance(first.value, str)
        ):
            self._flag(
                node,
                f"{shown}(<str>) — STACK.md §2.1, pass an argument list, not a string",
            )

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        # `getattr(os, "system")(cmd)`. The callee is itself a call, so neither
        # branch below ever looked at it and the name never appears in the
        # source for a table to match. Flagged by *shape*: resolving an
        # attribute at runtime and calling the result is unreviewable by an AST
        # checker in principle, so it is a question rather than a miss.
        if (
            isinstance(func, ast.Call)
            and isinstance(func.func, ast.Name)
            and func.func.id == "getattr"
        ):
            self._flag(
                node,
                "getattr(...)() — STACK.md §2.1, a dynamically resolved callee "
                "cannot be checked; name the call directly",
            )

        # The same defect through a subscript instead of a call:
        # `os.__dict__["system"](cmd)` puts the Subscript in the callee
        # position, and `sys.modules["os"].system(cmd)` hides it one level down
        # as the *value* of the attribute. Neither leaves a dotted name for any
        # table to match, and both are the same statement as `getattr` above —
        # a name chosen at runtime.
        #
        # **Narrowed after the first version flagged four sites in this
        # package.** "Any subscripted callee" is `x[i].method()`, which is
        # ordinary Python: three of the four were *slices* — `text[5:].strip()`
        # — and a slice cannot name a member at all. A rule that fails on good
        # code is one someone deletes, which this file says two paragraphs
        # below about a different rule and which it had just done again.
        #
        # So: never a slice, and only when the thing being subscripted is a
        # namespace that holds callables. That list is a denylist over
        # namespaces and is stated as one — but it is a closed set in the
        # language rather than a guess about a library's surface, which is what
        # makes it different from the `os` table this file used to carry.
        subscript = (
            func
            if isinstance(func, ast.Subscript)
            else func.value
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Subscript)
            else None
        )
        if subscript is not None and not isinstance(subscript.slice, ast.Slice):
            holder = _dotted(subscript.value)
            if not holder and isinstance(subscript.value, ast.Call):
                holder = _dotted(subscript.value.func)
            if holder in NAMESPACE_LOOKUPS or holder.endswith("__dict__"):
                self._flag(
                    node,
                    f"{holder}[...]() — STACK.md §2.1, a member looked up in a namespace "
                    "cannot be checked; name the call directly",
                )

        if isinstance(func, ast.Name):
            if why := BANNED_CALLS.get(func.id):
                self._flag(node, f"{func.id}() — {why}")
            else:
                # A bare name can be a banned member imported directly.
                self._check(node, self.aliases.get(func.id, ""), func.id)

        if isinstance(func, ast.Attribute):
            shown = _dotted(func)
            head = shown.split(".")[0]
            resolved = self.aliases.get(head, head)
            self._check(node, f"{resolved}.{func.attr}", shown)

        self.generic_visit(node)


def scan(root: Path) -> list[str]:
    """Every violation under `root`, sorted by path.

    Split out from `main` in M3.5 so this can be tested at all. Until then the
    scan root was hard-coded to `src/secrev`, which meant the stage enforcing
    §2.1 could only ever be pointed at code that already passed it — so the one
    thing it could not check was itself. `tests/test_self_check.py` now runs it
    against a file built to defeat it.

    The fixture cannot live in `tests/fixtures/`: everything there is swept by
    the golden tests, so a file full of `eval` and `os.system` would churn
    `hits.jsonl` and `recon.json`. It is written to a temporary directory
    instead, which is why a path argument exists rather than a fixture path.
    """
    # Messages stay relative to the repository root for the default scan, so
    # `check.sh` output is unchanged; a scan outside the repo reports relative
    # to what it was given.
    base = ROOT if root.is_relative_to(ROOT) else root

    violations: list[str] = []
    for path in sorted(root.rglob("*.py"), key=lambda p: p.as_posix()):
        rel = path.relative_to(base).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
        except SyntaxError as exc:  # a file that will not parse is its own failure
            violations.append(f"{rel}:{exc.lineno}: does not parse — {exc.msg}")
            continue
        visitor = Visitor(rel)
        visitor.visit(tree)
        violations.extend(f"{rel}:{line}: {why}" for line, why in visitor.hits)

    return violations


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]).resolve() if args else SRC

    if not root.is_dir():
        if args:
            # A path given explicitly and missing is a usage error, exit 2 per
            # `STACK.md` §3. Reporting "nothing to check" for a path someone
            # named would be a clean result from a check that never ran (H-1).
            print(f"no such directory: {root}", file=sys.stderr)
            return 2
        print("no src/secrev — nothing to check")
        return 0

    violations = scan(root)
    if violations:
        print("self-application violations (STACK.md §2.1 / NFR-4):", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            "\nA scanner that flags these and then calls them is not credible.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
