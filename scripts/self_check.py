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
    ("yaml", "load"): "STACK.md §2.1 — yaml.safe_load only",
    ("yaml", "unsafe_load"): "STACK.md §2.1 — yaml.safe_load only",
    ("yaml", "full_load"): "STACK.md §2.1 — yaml.safe_load only",
    # `importlib.import_module` is `__import__` with a nicer spelling.
    ("importlib", "import_module"): "STACK.md §2.1 — no dynamic import",
}

# Process execution through `os`, which had no entry at all until M3.5 — so
# `os.system(cmd)` passed a gate whose entire subject is process execution.
#
# **This stays a denylist, and P3 makes that a standing finding rather than a
# resolution.** `os` is a large surface and its dangerous members cannot be
# enumerated with confidence; `os.exec*` and `os.spawn*` alone are a dozen
# spellings. It is matched by prefix below rather than by an exhaustive list,
# which is a shape test rather than a name list and so is narrower than it
# looks — but it is not an allowlist, and nothing here should read as though
# the question were closed. The structural fix in this file is alias
# resolution; this table is the part that remains honest guesswork.
BANNED_OS_PREFIXES = ("exec", "spawn", "posix_spawn")
BANNED_OS_NAMES = {
    "system": "STACK.md §2.1 — no shell",
    "popen": "STACK.md §2.1 — no shell",
}
BANNED_IMPORTS = {
    "requests": "NFR-4 — no network at runtime",
    "urllib.request": "NFR-4 — no network at runtime",
    "http.client": "NFR-4 — no network at runtime",
    "socket": "NFR-4 — no network at runtime",
    "pickle": "STACK.md §2.1 — no pickle",
    "marshal": "STACK.md §2.1 — no marshal",
}


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
    call resolves through it first. The map is per module and deliberately
    simple: it records imports, never assignments, so rebinding a banned member
    to a local variable and calling that is still missed. Stated rather than
    hidden — a checker claiming more reach than it has is worse than one whose
    limit is written down.
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
            if why := BANNED_IMPORTS.get(alias.name):
                self._flag(node, f"import {alias.name} — {why}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if why := BANNED_IMPORTS.get(mod):
            self._flag(node, f"from {mod} import ... — {why}")
        for alias in node.names:
            dotted = f"{mod}.{alias.name}" if mod else alias.name
            self.aliases[alias.asname or alias.name] = dotted
            # `from urllib import request` binds a banned module under a name
            # the module-key test never sees, because that key is "urllib".
            if why := BANNED_IMPORTS.get(dotted):
                self._flag(node, f"from {mod} import {alias.name} — {why}")
        self.generic_visit(node)

    def _check(self, node: ast.Call, dotted: str, shown: str) -> None:
        """`dotted` is the resolved path; `shown` is what the source wrote."""
        base, _, attr = dotted.rpartition(".")
        base = base.split(".")[0]
        if not base:
            return

        if why := BANNED_ATTRS.get((base, attr)):
            self._flag(node, f"{shown}() — {why}")

        if base == "os":
            if why := BANNED_OS_NAMES.get(attr):
                self._flag(node, f"{shown}() — {why}")
            elif attr.startswith(BANNED_OS_PREFIXES):
                self._flag(node, f"{shown}() — STACK.md §2.1 — no process execution")

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
        if isinstance(first, ast.JoinedStr) or (
            isinstance(first, ast.Constant) and isinstance(first.value, str)
        ):
            self._flag(
                node,
                f"{shown}(<str>) — STACK.md §2.1, pass an argument list, not a string",
            )

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

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
