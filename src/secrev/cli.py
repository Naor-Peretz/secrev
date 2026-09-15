"""The `secrev` entry point. STACK.md §3, BRIEF_M1.md §7.

One command with subcommands, not five scripts — the PRD's `scripts/` listing
names modules, not executables.

**This is the only module that writes.** `recon.py` and `sweep.py` return
records; this file decides where they land. That is what keeps G-4 — never
write inside the reviewed target — a single checkable property rather than one
that has to hold independently in every generator, and it is why the golden
tests can compare returned values instead of files a test had to create.

The contracts this file owns, both from `STACK.md` §3:

  **Exit codes.** `0` success · `1` gate failure, meaning the run worked and
  the answer is no · `2` usage or configuration error · `3` internal error. The
  0/1 split exists so a hook can tell "the tool broke" from "the tool says no".
  In M1 neither subcommand can return 1 and that is deliberate rather than
  unimplemented: `1` means unresolved candidates remain, and every M1 candidate
  is unresolved by definition (FR-3.2), so returning it on a normal sweep would
  make the code meaningless to the first hook that trusted it.

  **Streams.** Machine-readable output to stdout, progress and diagnostics to
  stderr, so `secrev sweep target > hits.jsonl` yields a valid file. Every
  progress line in this file goes to stderr for that reason, including the one
  saying where the workspace is.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from secrev.catalog import Catalog, CatalogError, load
from secrev.ledger import WINDOW_SPEC, to_jsonl
from secrev.recon import Recon, recon, slug, to_json
from secrev.sweep import sweep

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

DEFAULT_WORKSPACE = Path.home() / ".security-review"


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
    directory is simply absent. M1 is driven by hand against a checkout, so
    this is a real limit rather than a hidden one: the caller gets a message
    naming the directory and `--catalog`, not an empty result.
    """
    root = Path(__file__).resolve().parent.parent.parent
    return sorted((root / "patterns").glob("*.yaml"))


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


def write_run_json(directory: Path, catalog: Catalog, subcommand: str) -> None:
    """`run.json` — the one artifact NFR-3 exempts, and the only place a
    timestamp may appear (`STACK.md` §5). Everything time-dependent lives here
    precisely so that nothing time-dependent can leak into the artifacts that
    are compared byte for byte.
    """
    document = {
        "command": subcommand,
        "tool_version": tool_version(),
        "catalog_version": catalog.version,
        "window_spec": WINDOW_SPEC,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (directory / "run.json").write_text(
        json.dumps(document, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def _emit(directory: Path, name: str, payload: str) -> None:
    """Both destinations. §7's third checklist item requires the workspace
    file; §3 requires the redirect to produce a valid one. They are not
    alternatives."""
    (directory / name).write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)


def _prepare(target: Path, workspace: Path, catalog: Catalog) -> tuple[Path, Recon]:
    result = recon(target)
    directory = workspace_for(target, workspace, result.target["version"])
    directory.mkdir(parents=True, exist_ok=True)
    sys.stderr.write(f"workspace: {directory}\n")
    write_run_json(directory, catalog, "recon")
    return directory, result


def run_recon(target: Path, workspace: Path, catalog: Catalog) -> int:
    directory, result = _prepare(target, workspace, catalog)
    _emit(directory, "recon.json", to_json(result))
    return EXIT_OK


def run_sweep(target: Path, workspace: Path, catalog: Catalog) -> int:
    directory, _ = _prepare(target, workspace, catalog)
    hits = sweep(target, catalog)
    _emit(directory, "hits.jsonl", to_jsonl(hits))
    sys.stderr.write(f"{len(hits)} candidates, all unresolved\n")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secrev", description="Security review of agentic artifacts."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    for name, help_text in (
        ("recon", "inventory a target and emit recon.json"),
        ("sweep", "run the pattern catalog and emit hits.jsonl"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("target", help="path to the artifact under review")
        sub.add_argument(
            "--workspace",
            default=None,
            help=f"output root; default {DEFAULT_WORKSPACE}, never the target",
        )
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

    try:
        catalog = resolve_catalog(args.catalog)
    except CatalogError as exc:
        # Exit 2, and the message names the offending pattern id: a schema
        # violation is a configuration error, and §4 requires the id because
        # "invalid catalog" sends a reader to a 200-entry file with no
        # starting point.
        sys.stderr.write(f"catalog: {exc}\n")
        return EXIT_USAGE

    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE
    try:
        if args.subcommand == "recon":
            return run_recon(target, workspace, catalog)
        return run_sweep(target, workspace, catalog)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE
    except OSError as exc:
        sys.stderr.write(f"internal error: {exc}\n")
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
