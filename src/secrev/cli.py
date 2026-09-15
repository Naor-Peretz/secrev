"""The `secrev` entry point. STACK.md §3, BRIEF_M1.md §7, BRIEF_M2.md §1.

One command with subcommands, not five scripts — the PRD's `scripts/` listing
names modules, not executables.

**This is the only module that writes.** `recon.py`, `sweep.py` and
`surfaces.py` return records; this file decides where they land. That is what
keeps G-4 — never write inside the reviewed target — a single checkable
property rather than one that has to hold independently in every generator,
and it is why the golden tests can compare returned values instead of files a
test had to create.

The contracts this file owns, from `STACK.md` §3 and TASKS_M2.md:

  **Exit codes.** `0` success · `1` gate failure, meaning the run worked and
  the answer is no · `2` usage or configuration error · `3` internal error. The
  0/1 split exists so a hook can tell "the tool broke" from "the tool says no".
  No subcommand can return 1 yet and that is deliberate rather than
  unimplemented: `1` means unresolved candidates remain, and every candidate is
  unresolved by definition until triage exists (FR-3.2), so returning it on a
  normal run would make the code meaningless to the first hook that trusted it.

  **Streams.** Machine-readable output to stdout, progress and diagnostics to
  stderr, so `secrev sweep target > hits.jsonl` yields a valid file. Every
  progress line in this file goes to stderr for that reason, including the one
  saying where the workspace is.

  **One ledger, one block per source** (Q1). The pattern and surface sources
  write into the same workspace `hits.jsonl`, each replacing only its own
  block, pattern block first — so the file is the same whichever order the
  commands ran in. stdout carries only the run's own block (owner decision):
  a pipe's output depends on its inputs, never on what ran earlier in the
  workspace.

  **`run.json` keeps one entry per command** (owner decision), each replaced
  only by its own command, so the versions behind each block stay recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from secrev.catalog import Catalog, CatalogError, load
from secrev.kinds import Kinds, SurfaceKindError
from secrev.kinds import load_file as load_kinds
from secrev.ledger import DECL_WINDOW_SPEC, WINDOW_SPEC, to_jsonl
from secrev.recon import Recon, recon, slug, to_json
from secrev.surfaces import surfaces
from secrev.sweep import sweep

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

DEFAULT_WORKSPACE = Path.home() / ".security-review"

# The blocks of `hits.jsonl`, in file order (Q1). A record whose `source` is
# not named here was not written by this tool.
SOURCES = ("pattern", "surface")

# The entries of `run.json`, in file order.
COMMANDS = ("recon", "sweep", "surfaces")

_ROOT = Path(__file__).resolve().parent.parent.parent


def tool_version() -> str:
    try:
        return version("secrev")
    except PackageNotFoundError:  # pragma: no cover - only when not installed
        return "0.0.0+unknown"


def default_catalog_paths() -> list[Path]:
    """The shipped catalog, found relative to this file.

    `patterns/` sits beside `src/` rather than inside the package, which is
    `BRIEF_M1.md` §2's tree. That works for the editable install `STACK.md` §3
    documents and would not survive being packaged into a wheel, where the
    directory is simply absent. The tool is driven by hand against a checkout,
    so this is a real limit rather than a hidden one: the caller gets a message
    naming the directory and `--catalog`, not an empty result. The surface
    kinds in `surfaces/` share the limit, for the same reason.
    """
    return sorted((_ROOT / "patterns").glob("*.yaml"))


def resolve_catalog(argument: str | None) -> Catalog:
    if argument:
        given = Path(argument)
        paths = sorted(given.glob("*.yaml")) if given.is_dir() else [given]
    else:
        paths = default_catalog_paths()
    if not paths:
        raise CatalogError(
            "no catalog files found. The shipped catalog lives in `patterns/` "
            "beside `src/`; point at another with --catalog"
        )
    return load(paths)


def resolve_kinds(argument: str | None) -> Kinds:
    return load_kinds(Path(argument) if argument else _ROOT / "surfaces" / "_surfaces.yaml")


def workspace_for(root: Path, base: Path, target_version: str) -> Path:
    """`<base>/<slug>/<version>/`, having refused to write inside the target.

    G-4 is checked here rather than trusted. `--workspace .` inside the
    reviewed repository is an easy thing to type and a review that modifies its
    target is not a review — so the containment is an assertion, not a
    convention, and it is the one place that has to hold.
    """
    resolved = base.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError(
            f"workspace {resolved} is inside the target {root}. G-4: a review never "
            "writes into the artifact it is reviewing"
        )
    return resolved / slug(root.name) / target_version


def _read_run_json(path: Path) -> dict[str, object]:
    """The entries earlier commands left. Anything else — the flat shape M1
    wrote, a damaged file — starts afresh, and says so on stderr: `run.json`
    records runs, not results, and is the one artifact NFR-3 exempts, so
    nothing is lost that rerunning the command does not restore, but a silent
    discard would read as though nothing had been there."""
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        document = None
    kept: dict[str, object] = {}
    if isinstance(document, dict):
        kept = {
            name: entry
            for name, entry in document.items()
            if name in COMMANDS and isinstance(entry, dict)
        }
    if not isinstance(document, dict) or len(kept) != len(document):
        sys.stderr.write(
            "run.json: earlier content was not one entry per command and was not kept\n"
        )
    return kept


def write_run_json(directory: Path, command: str, entry: dict[str, str]) -> None:
    """`run.json` — the one artifact NFR-3 exempts, and the only place a
    timestamp may appear (`STACK.md` §5). Everything time-dependent lives here
    precisely so that nothing time-dependent can leak into the artifacts that
    are compared byte for byte.

    One entry per command, replaced only by that command (owner decision): a
    later `surfaces` run must not erase the catalog version behind the pattern
    block, and no command has to load another's input to write it.
    """
    path = directory / "run.json"
    document = _read_run_json(path)
    document[command] = {
        "tool_version": tool_version(),
        **entry,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    ordered = {name: document[name] for name in COMMANDS if name in document}
    path.write_text(json.dumps(ordered, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def merge_ledger(existing: str, source: str, block: str) -> str:
    """The workspace ledger with `source`'s block replaced by `block` (Q1).

    Other blocks are kept line for line, byte for byte — never parsed and
    re-serialised — so a block written by one command is exactly the bytes
    that command produced. Blocks are written in `SOURCES` order, which is
    what makes the file independent of the order the commands ran in.

    Refused rather than overwritten when a line is not a record this tool
    wrote: a file it cannot read as its own ledger is damaged or someone
    else's, and replacing one block in it would silently discard the rest. A
    last line with no newline is refused too, since the next block would be
    joined onto it.

    Split on `\\n` alone, never `str.splitlines`, which also splits on U+0085,
    U+2028 and U+2029. `to_jsonl` writes those unescaped inside a record, so a
    filename carrying one would cut its own record in two and every later run
    would be refused — a target choosing its own filenames could lock the
    surface source out of its workspace (P11). Found in review. The run's own
    block is never split at all.
    """
    if existing and not existing.endswith("\n"):
        raise ValueError(
            "hits.jsonl in the workspace does not end in a newline, so a block cannot "
            "be joined to it safely. Move the file aside or choose another --workspace"
        )
    blocks: dict[str, list[str]] = {name: [] for name in SOURCES}
    for number, line in enumerate(existing.split("\n")[:-1], start=1):
        try:
            record = json.loads(line)
        except ValueError:
            record = None
        found = record.get("source") if isinstance(record, dict) else None
        if not isinstance(found, str) or found not in blocks:
            raise ValueError(
                f"hits.jsonl line {number} in the workspace is not a record this tool "
                "wrote; refusing to replace a block in a ledger it cannot read. Move "
                "the file aside or choose another --workspace"
            )
        blocks[found].append(line + "\n")
    blocks[source] = [block]
    return "".join(chunk for name in SOURCES for chunk in blocks[name])


def _emit(directory: Path, name: str, payload: str) -> None:
    """Both destinations. §7's third checklist item requires the workspace
    file; §3 requires the redirect to produce a valid one. They are not
    alternatives."""
    (directory / name).write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)


def _write_block(directory: Path, source: str, block: str) -> None:
    """The ledger in the workspace gains this run's block. The merge runs
    before anything is written, so a ledger that is refused is left exactly as
    it was. stdout is the caller's last step, after `run.json`, so a run that
    fails to record itself has not already delivered its output."""
    path = directory / "hits.jsonl"
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"hits.jsonl in the workspace is not UTF-8 ({exc.reason}); refusing to "
            "replace a block in a ledger it cannot read. Move the file aside or "
            "choose another --workspace"
        ) from exc
    path.write_text(merge_ledger(existing, source, block), encoding="utf-8")


def _prepare(target: Path, workspace: Path) -> tuple[Path, Recon]:
    result = recon(target)
    directory = workspace_for(target, workspace, result.target["version"])
    directory.mkdir(parents=True, exist_ok=True)
    sys.stderr.write(f"workspace: {directory}\n")
    return directory, result


def run_recon(target: Path, workspace: Path, catalog: Catalog) -> int:
    directory, result = _prepare(target, workspace)
    _emit(directory, "recon.json", to_json(result))
    write_run_json(
        directory, "recon", {"catalog_version": catalog.version, "window_spec": WINDOW_SPEC}
    )
    return EXIT_OK


def run_sweep(target: Path, workspace: Path, catalog: Catalog) -> int:
    directory, _ = _prepare(target, workspace)
    hits = sweep(target, catalog)
    block = to_jsonl(hits)
    _write_block(directory, "pattern", block)
    write_run_json(
        directory, "sweep", {"catalog_version": catalog.version, "window_spec": WINDOW_SPEC}
    )
    sys.stdout.write(block)
    sys.stderr.write(f"{len(hits)} candidates, all unresolved\n")
    return EXIT_OK


def run_surfaces(target: Path, workspace: Path, kinds: Kinds) -> int:
    directory, _ = _prepare(target, workspace)
    hits = surfaces(target, kinds)
    block = to_jsonl(hits)
    _write_block(directory, "surface", block)
    write_run_json(
        directory, "surfaces", {"kinds_version": kinds.version, "window_spec": DECL_WINDOW_SPEC}
    )
    sys.stdout.write(block)
    sys.stderr.write(f"{len(hits)} surface candidates, all unresolved\n")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secrev", description="Security review of agentic artifacts."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    commands = (
        ("recon", "inventory a target and emit recon.json"),
        ("sweep", "run the pattern catalog and emit its block of hits.jsonl"),
        ("surfaces", "enumerate reachable entry points and emit their block of hits.jsonl"),
    )
    for name, help_text in commands:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("target", help="path to the artifact under review")
        sub.add_argument(
            "--workspace",
            default=None,
            help=f"output root; default {DEFAULT_WORKSPACE}, never the target",
        )
        # The surface source never sees the catalog: it is a peer of the
        # pattern source, not a stage after it (P11, TASKS_M2.md Q2).
        if name == "surfaces":
            sub.add_argument(
                "--kinds",
                default=None,
                help="surface kinds file; default is the shipped surfaces/_surfaces.yaml",
            )
        else:
            sub.add_argument(
                "--catalog",
                default=None,
                help="catalog file or directory of .yaml packs; default is the shipped patterns/",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.is_dir():
        sys.stderr.write(f"target {target} is not a directory\n")
        return EXIT_USAGE

    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE

    if args.subcommand == "surfaces":
        try:
            kinds = resolve_kinds(args.kinds)
        except SurfaceKindError as exc:
            # Exit 2, naming the kind, for the catalog's reason below.
            sys.stderr.write(f"surface kinds: {exc}\n")
            return EXIT_USAGE
        return _run(lambda: run_surfaces(target, workspace, kinds))

    try:
        catalog = resolve_catalog(args.catalog)
    except CatalogError as exc:
        # Exit 2, and the message names the offending pattern id: a schema
        # violation is a configuration error, and §4 requires the id because
        # "invalid catalog" sends a reader to a 200-entry file with no
        # starting point.
        sys.stderr.write(f"catalog: {exc}\n")
        return EXIT_USAGE

    if args.subcommand == "recon":
        return _run(lambda: run_recon(target, workspace, catalog))
    return _run(lambda: run_sweep(target, workspace, catalog))


def _run(command: Callable[[], int]) -> int:
    """The exit-code contract, in one place for every subcommand.

    Anything unexpected is `3`, never the interpreter's default `1`: `1` means
    "the tool worked and the answer is no" (`STACK.md` §3), and a hook reading
    a bug's traceback exit as a gate verdict is the confusion the split exists
    to prevent. Found in review.
    """
    try:
        return command()
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE
    except Exception as exc:
        sys.stderr.write(f"internal error: {type(exc).__name__}: {exc}\n")
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
