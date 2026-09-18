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
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from secrev.catalog import Catalog, CatalogError, load
from secrev.inventory import MAX_FILE_BYTES
from secrev.kinds import Kinds, SurfaceKindError
from secrev.kinds import load_file as load_kinds
from secrev.ledger import BLOCK_WINDOW_SPEC, DECL_WINDOW_SPEC, WINDOW_SPEC, to_jsonl
from secrev.recon import GAP_LIST_LIMIT, Recon, recon, slug, to_json
from secrev.structure import SHAPES, structure
from secrev.structure_rules import StructureRuleError, StructureRules
from secrev.structure_rules import load_file as load_rules
from secrev.surfaces import surfaces
from secrev.sweep import sweep

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

DEFAULT_WORKSPACE = Path.home() / ".security-review"

# The blocks of `hits.jsonl`, in file order (Q1). A record whose `source` is
# not named here was not written by this tool.
SOURCES = ("pattern", "surface", "structure")

# The entries of `run.json`, in file order.
COMMANDS = ("recon", "sweep", "surfaces", "structure")

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


def resolve_rules(argument: str | None) -> StructureRules:
    """The structural rules, with the shape specifications the analyses declare.

    `SHAPES` is passed in rather than imported by the loader, so
    `structure_rules.py` holds no rule logic and no rule name — the same
    separation `catalog.py` keeps from what a pattern means.
    """
    return load_rules(
        Path(argument) if argument else _ROOT / "structure" / "_structure.yaml", SHAPES
    )


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
    # Atomic for the same reason as the ledger (M3.5 E4): this file is
    # read-modify-write too, so a truncating write loses the entries every
    # *earlier* command left — the versions behind blocks this run never
    # touched. The one artifact NFR-3 exempts is still an artifact.
    _atomic_write(path, json.dumps(ordered, indent=2, sort_keys=False) + "\n")


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


def _atomic_write(path: Path, payload: str) -> None:
    """Write `payload` to `path`, so that `path` is never partly written.

    `write_text` truncates and then writes, so a run interrupted between those
    two steps leaves the file empty or half-written. That is worst for the
    ledger: `merge_ledger` goes to deliberate lengths to keep the other
    source's block byte for byte — never parsed, never re-serialised — and a
    truncating write destroys exactly what that care protects. The surface
    block would be lost by a failure in the pattern block's write, with nothing
    saying so.

    The temporary file is created **in the destination directory**, because
    `os.replace` is atomic only within one filesystem; a temp in `/tmp` would
    silently degrade to a copy across a mount boundary. It is removed if the
    replace fails, so a failure leaves no second copy of content G-3 spent its
    effort making safe to write down.

    `NamedTemporaryFile` creates at 0o600, so artifacts inherit a private mode
    rather than the umask's. For a directory holding `match_excerpt` values
    that is the right default, and it matches the 0o700 the workspace gets.
    """
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed by the with below
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
        # `os.replace`, not `Path.replace` (PTH105). Two reasons: it is the
        # atomic-rename primitive and reads as one here, where the whole point
        # is atomicity rather than path manipulation; and it is the seam
        # `test_an_interrupted_ledger_write_leaves_the_previous_ledger` patches
        # to fail the final step. Routing through `Path.replace` would make
        # that test depend on which primitive pathlib happens to call
        # internally — a test that passes for a reason no longer stated.
        os.replace(temporary, path)  # noqa: PTH105
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _emit(directory: Path, name: str, payload: str) -> None:
    """Both destinations. §7's third checklist item requires the workspace
    file; §3 requires the redirect to produce a valid one. They are not
    alternatives."""
    _atomic_write(directory / name, payload)
    sys.stdout.write(payload)


def _write_block(directory: Path, source: str, block: str) -> None:
    """The ledger in the workspace gains this run's block. The merge runs
    before anything is written, so a ledger that is refused is left exactly as
    it was. stdout is the caller's last step, after `run.json`, so a run that
    fails to record itself has not already delivered its output.

    The write is atomic (M3.5 E4). Refusing before writing was only half the
    property: the merge protected a ledger this tool could not *read*, while a
    `write_text` truncating mid-run destroyed one it could — including the
    other source's block, which `merge_ledger` keeps byte for byte precisely so
    that it survives.
    """
    path = directory / "hits.jsonl"
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"hits.jsonl in the workspace is not UTF-8 ({exc.reason}); refusing to "
            "replace a block in a ledger it cannot read. Move the file aside or "
            "choose another --workspace"
        ) from exc
    _atomic_write(path, merge_ledger(existing, source, block))


def _positive_int(value: str) -> int:
    """`--max-file-bytes`, refusing zero and below.

    Validated here rather than in `main` so that argparse raises and exits 2
    itself. That keeps every usage error on one path — the same reasoning that
    chose `type=int` over a converter of our own — and avoids a second
    mechanism that could drift out of agreement with argparse's.

    A bound of zero or less would exclude every file, reporting an empty review
    as a complete one, which is the silent loss of scope this milestone exists
    to close.
    """
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive number of bytes")
    return number


def _parse_exclude(value: str | None) -> frozenset[str] | None:
    """`--exclude` as a set of directory names, or `None` for the default set.

    **Replacing rather than subtracting** (M3.5 A2). A subtractive flag would
    need the caller to already know the fourteen default names to predict what
    a run will do, and `recon.json` reports the applied set either way — so the
    simpler, more honest spelling is the one where what you pass is what is
    skipped.

    `--exclude ""` skips nothing, which is the case A2 exists for: reviewing a
    target's `dist/` rather than trusting it. Empty names are dropped so that a
    trailing comma is not a directory called "".
    """
    if value is None:
        return None
    return frozenset(name.strip() for name in value.split(",") if name.strip())


def _prepare(
    target: Path,
    workspace: Path,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> tuple[Path, Recon]:
    result = recon(target, excluded, max_bytes)
    directory = workspace_for(target, workspace, result.target["version"])

    # 0o700 on every level, not only the leaf (M3.5 E4). The workspace holds
    # `match_excerpt` values — the one field G-3 spends its effort making safe
    # to write down — so it is not left at whatever the umask gives. On the
    # machine this was found on that was 0o775: group-writable as well as
    # world-readable.
    #
    # Walked rather than passed as `mode=`, because both obvious spellings look
    # right and are not. `mkdir(parents=True, mode=0o700)` applies the mode to
    # the final directory only, leaving `~/.security-review/` at the default;
    # and `exist_ok=True` leaves an existing directory's mode untouched, which
    # is every run after the first.
    # Walked downward from the base rather than upward from the leaf: this
    # terminates by construction, needs no filesystem-root guard, and fails
    # loudly through `relative_to` if the base is somehow not an ancestor —
    # where walking up would quietly chmod its way toward `/`.
    # **Created at 0o700 and then confirmed, rather than created and repaired.**
    # This was `mkdir(parents=True, exist_ok=True)` followed by the chmod walk
    # below, which leaves every level world-readable between the two calls —
    # and the M4 structural source found it in this file, on the milestone that
    # shipped the rule (`structure.permission_after_creation`, F1). M3.5's E4
    # fixed the mode these directories end up with; it did not close the window
    # they pass through, and the comment above was written while looking
    # straight at it.
    #
    # `mode=` is safe here in a way it is not on `parents=True`: umask can only
    # *clear* bits, and 0o700 has no group or other bits to clear, so the
    # directory is never briefly readable. The chmod stays for levels that
    # already existed — `exist_ok=True` leaves their mode alone, and those are
    # not directories this run created, so there is no window we opened.
    base = workspace.resolve()
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    base.chmod(0o700)
    level = base
    for part in directory.relative_to(base).parts:
        level = level / part
        level.mkdir(mode=0o700, exist_ok=True)
        level.chmod(0o700)

    sys.stderr.write(f"workspace: {directory}\n")
    return directory, result


def _incomplete(result: Recon) -> int:
    """The exit code for a target this tool was not permitted to read in full.

    **Not 3.** A file the tool may not open is a fact about the target, not a
    bug in the tool, and `STACK.md` §3 reserves 3 for an internal error — so
    reporting it as 3 sends whoever reads the exit code to the wrong codebase.
    That is what happened before M3.5: `PermissionError` reached `_run`'s
    generic handler.

    **Not 0 either.** Content that should have been reviewed was not, and "I
    did not read this" must not be reported as "I read it and found nothing"
    (H-1). Exit 0 here would be a clean review of a tree the tool could not
    fully see.

    §3's parenthetical for 2 — "bad arguments, malformed catalog, missing
    target" — does not name this case. It is read as illustrative rather than
    exhaustive, on the precedent `inventory.NormalisationCollision` already
    set: it is a `ValueError` so that `cli` reports exit 2, because "the tool
    worked and the target cannot be reviewed as it stands" is a fact about the
    input. This is the same statement about a different fact.

    The artifacts are written before this is consulted, and they are complete
    for everything that could be read. The code says the review is *partial*,
    never that it is absent.
    """
    unreadable = result.inventory["unreadable"]
    # Files that nothing read, for any reason, and whose extension is not a
    # known binary asset. Added after a second review showed that `unreadable`
    # alone left two evasions at exit 0: eight NUL bytes in a comment classified
    # a runnable `install.sh` as binary, and padding it past `--max-file-bytes`
    # did the same, both with `0 candidates, exit 0` and no line in
    # `coverage_gaps` naming the file.
    #
    # The docstring above already said why that is wrong — "exit 0 here would be
    # a clean review of a tree the tool could not fully see" — and the code
    # applied the reasoning to one of the four ways a file goes unread.
    #
    # **This comment said "files with a code extension" until a fifth reading.**
    # That was true of the first version and false after the fourth review
    # inverted the test — and the phrasing survived into the message printed to
    # stderr below, which is worse: it named the mechanism that had just been
    # defeated, on a line listing `setup`, `prompt.txt` and `AGENT.md`, none of
    # which has a code extension. A correction applied to the documentation and
    # not to the string beside it is the same half-fix this milestone keeps
    # finding, one layer in.
    unread_code = result.inventory["unread_code"]
    if not unreadable and not unread_code:
        return EXIT_OK

    for count, what, paths in (
        (len(unreadable), "could not be read and were not reviewed", unreadable),
        (len(unread_code), "were never read and are not a known binary asset", unread_code),
    ):
        if not paths:
            continue
        # Named rather than repeated: the count is a display choice, and a
        # message that truncates must say how much it left out or it is a third
        # way of reporting a partial answer as a whole one.
        #
        # `recon.GAP_LIST_LIMIT`, not a local `5`. It was a local until M4,
        # when a third site would have made three definitions of one display
        # rule — and a truncation that disagrees with the artifact's own
        # truncation is a reader comparing two lists that were cut differently.
        shown = ", ".join(paths[:GAP_LIST_LIMIT])
        if count > GAP_LIST_LIMIT:
            shown += f", and {count - GAP_LIST_LIMIT} more"
        sys.stderr.write(f"{count} file(s) {what}: {shown}\n")
    return EXIT_USAGE


def run_recon(
    target: Path,
    workspace: Path,
    catalog: Catalog,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> int:
    directory, result = _prepare(target, workspace, excluded, max_bytes)
    _emit(directory, "recon.json", to_json(result))
    write_run_json(
        directory, "recon", {"catalog_version": catalog.version, "window_spec": WINDOW_SPEC}
    )
    return _incomplete(result)


def run_sweep(
    target: Path,
    workspace: Path,
    catalog: Catalog,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> int:
    directory, result = _prepare(target, workspace, excluded, max_bytes)
    hits = sweep(target, catalog, excluded, max_bytes)
    block = to_jsonl(hits)
    _write_block(directory, "pattern", block)
    write_run_json(
        directory, "sweep", {"catalog_version": catalog.version, "window_spec": WINDOW_SPEC}
    )
    sys.stdout.write(block)
    sys.stderr.write(f"{len(hits)} candidates, all unresolved\n")
    return _incomplete(result)


def run_surfaces(
    target: Path,
    workspace: Path,
    kinds: Kinds,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> int:
    directory, result = _prepare(target, workspace, excluded, max_bytes)
    hits = surfaces(target, kinds, excluded, max_bytes)
    block = to_jsonl(hits)
    _write_block(directory, "surface", block)
    write_run_json(
        directory, "surfaces", {"kinds_version": kinds.version, "window_spec": DECL_WINDOW_SPEC}
    )
    sys.stdout.write(block)
    sys.stderr.write(f"{len(hits)} surface candidates, all unresolved\n")
    return _incomplete(result)


def run_structure(
    target: Path,
    workspace: Path,
    rules: StructureRules,
    excluded: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> int:
    """The structural block, and the files this source could not read.

    **A file that would not parse makes the run exit 2**, even when the rest of
    the tree produced candidates and even when `recon` found nothing else
    wrong. It is not "no candidates here": it is a file this source never
    reviewed, and collapsing the two is H-1 — the same polarity M3.5 spent four
    review rounds arriving at for files that went unread.

    The names go to stderr and the block still goes to stdout, so
    `secrev structure target > hits.jsonl` yields a valid file whichever way the
    exit code lands (`STACK.md` §3).
    """
    directory, result = _prepare(target, workspace, excluded, max_bytes)
    produced = structure(target, rules, excluded, max_bytes)
    block = to_jsonl(produced.hits)
    _write_block(directory, "structure", block)
    write_run_json(
        directory,
        "structure",
        {"rules_version": rules.version, "window_spec": BLOCK_WINDOW_SPEC},
    )
    sys.stdout.write(block)
    sys.stderr.write(f"{len(produced.hits)} structural candidates, all unresolved\n")

    incomplete = _incomplete(result)
    if produced.unparsed:
        shown = ", ".join(produced.unparsed[:GAP_LIST_LIMIT])
        if len(produced.unparsed) > GAP_LIST_LIMIT:
            shown += f", and {len(produced.unparsed) - GAP_LIST_LIMIT} more"
        sys.stderr.write(
            f"{len(produced.unparsed)} file(s) did not parse and were not reviewed "
            f"by this source: {shown}\n"
        )
        return EXIT_USAGE
    return incomplete


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secrev", description="Security review of agentic artifacts."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    commands = (
        ("recon", "inventory a target and emit recon.json"),
        ("sweep", "run the pattern catalog and emit its block of hits.jsonl"),
        ("surfaces", "enumerate reachable entry points and emit their block of hits.jsonl"),
        ("structure", "run the structural rules and emit their block of hits.jsonl"),
    )
    for name, help_text in commands:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("target", help="path to the artifact under review")
        sub.add_argument(
            "--workspace",
            default=None,
            help=f"output root; default {DEFAULT_WORKSPACE}, never the target",
        )
        sub.add_argument(
            "--exclude",
            default=None,
            metavar="NAMES",
            help=(
                "comma-separated directory names to skip, replacing the default "
                'set; --exclude "" skips nothing'
            ),
        )
        # `type=int` rather than a converter of our own: argparse already
        # refuses a non-integer and exits 2, which is exactly `STACK.md` §3's
        # usage-error code. Writing a second converter would duplicate that and
        # risk disagreeing with it.
        sub.add_argument(
            "--max-file-bytes",
            type=_positive_int,
            default=None,
            metavar="N",
            help=f"skip files larger than N bytes; default {MAX_FILE_BYTES}",
        )
        # Neither peer source ever sees the catalog: they are peers of the
        # pattern source, not stages after it (P11, D-11, TASKS_M2.md Q2). Each
        # takes its own ruleset flag and nothing else's.
        if name == "surfaces":
            sub.add_argument(
                "--kinds",
                default=None,
                help="surface kinds file; default is the shipped surfaces/_surfaces.yaml",
            )
        elif name == "structure":
            sub.add_argument(
                "--rules",
                default=None,
                help="structural rules file; default is the shipped structure/_structure.yaml",
            )
        else:
            sub.add_argument(
                "--catalog",
                default=None,
                help="catalog file or directory of .yaml packs; default is the shipped patterns/",
            )
    return parser


@dataclass(frozen=True)
class _PeerSource:
    """A candidate source that loads its own ruleset and never sees the catalog.

    The surface and structural sources are symmetric — a flag, a loader, an
    error type, a label for the message, and a runner — so they are described
    once rather than branched on twice. The table is not only tidier: it is the
    shape D-11 asserts, and a fourth source added as another `if` in `main`
    would be the first place the peer relationship stopped being visible.

    The pattern source is deliberately absent. It is a peer too, but it is the
    one `recon` also needs a catalog for, so its resolution sits on the path
    both commands share.
    """

    flag: str
    load: Callable[[str | None], object]
    error: type[Exception]
    label: str
    run: Callable[..., int]


_PEER_SOURCES: dict[str, _PeerSource] = {
    "surfaces": _PeerSource(
        flag="kinds",
        load=resolve_kinds,
        error=SurfaceKindError,
        label="surface kinds",
        run=run_surfaces,
    ),
    "structure": _PeerSource(
        flag="rules",
        load=resolve_rules,
        error=StructureRuleError,
        label="structural rules",
        run=run_structure,
    ),
}


def _run_peer_source(
    args: argparse.Namespace,
    target: Path,
    workspace: Path,
    excluded: frozenset[str] | None,
    max_bytes: int | None,
) -> int:
    """Load a peer source's ruleset and run it.

    A schema violation is exit 2 and the message names the offending rule, for
    the same reason the catalog's does: "invalid rules" sends a reader to a file
    with no starting point (§4).
    """
    source = _PEER_SOURCES[args.subcommand]
    try:
        ruleset = source.load(getattr(args, source.flag))
    except source.error as exc:
        sys.stderr.write(f"{source.label}: {exc}\n")
        return EXIT_USAGE
    return _run(lambda: source.run(target, workspace, ruleset, excluded, max_bytes))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.is_dir():
        sys.stderr.write(f"target {target} is not a directory\n")
        return EXIT_USAGE

    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE
    # `None` when the flag is absent, which every source reads as the default
    # set. What was actually applied is reported in `recon.json`, so an
    # override is visible in the artifact rather than only in the invocation.
    excluded = _parse_exclude(args.exclude)

    max_bytes = args.max_file_bytes

    if args.subcommand in _PEER_SOURCES:
        return _run_peer_source(args, target, workspace, excluded, max_bytes)

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
        return _run(lambda: run_recon(target, workspace, catalog, excluded, max_bytes))
    return _run(lambda: run_sweep(target, workspace, catalog, excluded, max_bytes))


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
