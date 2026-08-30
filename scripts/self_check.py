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
}
BANNED_ATTRS = {
    ("pickle", "load"): "STACK.md §2.1 — no pickle",
    ("pickle", "loads"): "STACK.md §2.1 — no pickle",
    ("marshal", "load"): "STACK.md §2.1 — no marshal",
    ("marshal", "loads"): "STACK.md §2.1 — no marshal",
    ("yaml", "load"): "STACK.md §2.1 — yaml.safe_load only",
    ("yaml", "unsafe_load"): "STACK.md §2.1 — yaml.safe_load only",
    ("yaml", "full_load"): "STACK.md §2.1 — yaml.safe_load only",
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
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.hits: list[tuple[int, str]] = []

    def _flag(self, node: ast.AST, why: str) -> None:
        self.hits.append((getattr(node, "lineno", 0), why))

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if why := BANNED_IMPORTS.get(alias.name):
                self._flag(node, f"import {alias.name} — {why}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if why := BANNED_IMPORTS.get(mod):
            self._flag(node, f"from {mod} import ... — {why}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and (why := BANNED_CALLS.get(func.id)):
            self._flag(node, f"{func.id}() — {why}")

        if isinstance(func, ast.Attribute):
            dotted = _dotted(func)
            head = dotted.split(".")[0]
            key = (head, func.attr)
            if why := BANNED_ATTRS.get(key):
                self._flag(node, f"{dotted}() — {why}")

            if head == "subprocess":
                for kw in node.keywords:
                    if kw.arg == "shell" and not (
                        isinstance(kw.value, ast.Constant) and kw.value.value is False
                    ):
                        self._flag(node, f"{dotted}(shell=...) — STACK.md §2.1, argument lists only")
                if node.args and isinstance(node.args[0], ast.Constant):
                    self._flag(
                        node,
                        f"{dotted}(<str>) — STACK.md §2.1, pass an argument list, not a string",
                    )
        self.generic_visit(node)


def main() -> int:
    if not SRC.is_dir():
        print("no src/secrev — nothing to check")
        return 0

    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py"), key=lambda p: p.as_posix()):
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
        except SyntaxError as exc:  # a file that will not parse is its own failure
            violations.append(f"{rel}:{exc.lineno}: does not parse — {exc.msg}")
            continue
        visitor = Visitor(rel)
        visitor.visit(tree)
        violations.extend(f"{rel}:{line}: {why}" for line, why in visitor.hits)

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
