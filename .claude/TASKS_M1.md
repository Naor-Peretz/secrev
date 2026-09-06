# M1 task ledger — the pattern sweep

Scope: `BRIEF_M1.md`. Mechanism: `STACK.md`, especially §5 (determinism) and §9 (testing).

`.claude/MILESTONE` holds `M1` and nothing else. This file is the ledger; receipts go in
`.claude/receipts.md`. **When M1 closes, move the marker** — it was wrong in both directions
during M0 and the assertion in `attack.py` only checks the M0 boxes.

## Build order, and why it is not the order in §2

`BRIEF_M1.md` §2 lists the deliverable tree alphabetically. That is not a sequence, and following
it would put `cli.py` first.

**`inventory.py` is first, and the determinism test is written before it.** It is the only file
that concentrates the decisions that cannot be changed afterwards — traversal order, NFC
normalisation, exclusions, binary detection, symlinks. `recon.py` and `sweep.py` are both consumers
of the walk: if it is right they inherit that for free, and if it is wrong both of them are
rewrites. A determinism check written after the generators exist is a retrofit onto code composed
without it, and NFR-3 is the one requirement that does not survive being retrofitted — getting it
wrong invalidates every verification recorded above it (D-4).

---

- [x] **TASK-M1-001 — The determinism gate stops being conditional on a directory.**
      `scripts/check.sh` and `scripts/determinism_check.py` keyed on `src/secrev/` existing. That
      directory appears with the *first* file, so if the first file were `cli.py` the stage would
      keep printing "nothing to compare" for exactly as long as the NFR-3 rules were being written.
      Bound to `src/secrev/inventory.py` instead — mechanical, and it cannot outlive its own truth.
      *Accept:* the message names the file; once it exists the stage runs and cannot skip.

- [x] **TASK-M1-002 — `tests/test_determinism.py`, written red.**
      Thirteen assertions, added before `inventory.py` existed and run red against a missing
      module. Three carry the weight: two walks agree byte for byte; NFD and NFC filenames produce
      one identical inventory; an unrelated file changes no existing entry.
      *Accept:* red before the module, green after, and red again when `sorted()` is removed.

- [x] **TASK-M1-003 — `inventory.py` + `tests/fixtures/`.**
      The walk, and the committed tree the check runs against — non-ASCII filename, CRLF content,
      nesting, a NUL-byte binary, and an excluded directory that is present.
      *Accept:* gate green with every stage live; removing `sorted()` turns it red.

- [x] **TASK-M1-004 — `ids.py`.** Stable candidate id from `(relative_path, rule_id,
      window_sha256, ordinal)`, the `ordinal` ranging over byte-identical windows only. Before
      `sweep.py`, for the same reason `inventory.py` came before both: an identity derived from a
      traversal counter looks correct until something is inserted ahead of it.
      *Accept:* the id of an existing candidate survives a file being added, removed and renamed
      elsewhere in the tree.
      **This line originally read `(relative_path, line, rule_id, ordinal)`** — the derivation the
      task was written against, which the task itself overturned. `line` was removed because PRD
      FR-4.5 says a verification anchored only to a line number is lost the moment the content
      moves, and an id containing `line` anchored it to exactly that; the rule-wide ordinal was
      removed because deleting one match renumbered its neighbours. `STACK.md` §5 carries both
      corrections with their reasoning. Ticking the box without correcting the text would have
      left the superseded formula in the one place a reader looks for what this task meant.

- [x] **TASK-M1-005 — `catalog.py`.** YAML load and strict validation (`BRIEF_M1.md` §4).
      `yaml.safe_load` only. A schema violation exits 2 naming the offending pattern id.
      `flags` is a fixed subset, never passthrough; no `multiline` field, now or later. Regexes
      compile at load, so a malformed one is a catalog error rather than a crash mid-sweep.
      Owner decisions, taken during planning: the field is **`default_severity_hint`** (PRD FR-3.3
      beat this brief's `severity_hint` on precedence, and the longer name reads as a default the
      severity phase may override rather than as a verdict — FR-3.2); **a `layer` list with more
      than one element exits 2** naming the id, because §5's record is a scalar and the two-layer
      representation is undecided, and accepting a catalog we cannot emit is worse than refusing.
      *Accept:* every malformed catalog in the fixtures exits 2 and names the id.

- [x] **TASK-M1-005B — `__main__.py`, and `--catalog` on `sweep`.** Not in `BRIEF_M1.md` §2's
      tree, and required anyway: `.github/workflows/ci.yml` (lines 183, 204) invokes
      `python -m secrev sweep --help`, greps for `--catalog`, and reads the offending pattern id
      from **stderr**. Absent either, the job takes its `::warning::` branch and **exits 0** having
      asserted nothing — the H-1 shape, in the job that exists to prove exit 2. The branch was
      written deliberately and says so; this is the task that retires it.
      *Accept:* the `catalog` job runs its assertion instead of warning past it.

- [x] **TASK-M1-006 — `patterns/_base.yaml` + `python.yaml`.** The seed patterns (§6) — **nine,
      not eight.** `path.traversal` was added by owner decision: §7's last DoD item requires
      flagging the region of a known path-validation issue and no original seed pattern targeted
      path handling, while PRD FR-3.4 names the class as minimum coverage with no milestone owning
      it. It asks whether a path is being built from a name rather than a literal — a token
      question. It is **not** the denylist-shape rule §1 cut to M4, which asks about control flow.
      Each ships a positive **and** a negative fixture — a pattern without a negative fixture
      drifts into over-matching and nobody notices (§9). `fs.agent_config_write` gets the most
      coverage, including `.CLAUDE` against `.claude` (`STACK.md` §4: a finding class here, not a
      portability note).
      *Accept:* both fixtures present for every pattern; `precision: low` is an expected value and
      not a defect.
      **Ordering note:** the *golden* half of these fixtures depends on TASK-M1-007's window, since
      every expected record carries an id derived from `window_sha256`. Regex-level fixtures can
      land here; expected records follow the sweep.

- [x] **TASK-M1-007 — `sweep.py` → `hits.jsonl`.** Line-oriented only. Two hits on one line stay
      two hits (D-6); no dedup by location. Patterns are questions, not verdicts — nothing here
      concludes anything (FR-3.2). Records sorted by `(file, line, rule_id, ordinal)` so the file
      is byte-stable. CRLF → LF **before hashing**, line numbers reported against the original
      (`STACK.md` §5; `tests/fixtures/crlf_module.py` exercises it). G-3 redaction applies to
      `match_excerpt` only — the window feeding `window_sha256` is hashed unredacted, or every id
      would depend on the redaction rules.
      **The window is `lines-20`** — ±20 lines, no tightening — and `window_spec` is a field on
      every record. Tightening to a block needs an AST, which §1 defers to M4; carrying the spec
      makes that transition an invalidation FR-4.6 detects rather than one someone must remember.
      **`sweep` exits 0 when it finds hits.** Exit 1 is "unresolved candidates remain"
      (`STACK.md` §3), and in M1 every candidate is unresolved by definition — exiting 1 on a
      normal run would make the code meaningless to the hook the 0/1 split exists for.
      *Accept:* golden byte-comparison against a committed expected file.

- [x] **TASK-M1-008 — `recon.py` → `recon.json`.** §3's shape. Exclusions recorded as applied,
      never silently. `entrypoints` from declared metadata only; deeper enumeration is M2.
      Three questions the documents leave open land here and want answers before the golden file
      exists, because each one is bytes in a deterministic artifact: **what `<version>` and
      `target.sha` hold for a non-git target** (§6 gives only "the resolved tag or SHA", and DoD
      item 9 sweeps `src/secrev/`, a subdirectory rather than a repo root); **the
      extension-to-language map and what `loc_total` counts** — which is not recon's alone, since
      §4's `languages: [python]` means `sweep.py` needs the identical map, so one map owned by one
      module; and **what `coverage_gaps` says in M1**, where structural analysis exists for no
      language rather than for all but two.
      *Accept:* golden byte-comparison; the determinism stage's "waiting on recon.py, sweep.py"
      disappears and the artifact checks run. §7's first item says "against a real repository" —
      the fixture golden does not discharge that half on its own.

- [x] **TASK-M1-009 — `cli.py`.** Last, not first. `recon` and `sweep` subcommands, the exit-code
      contract (0/1/2/3) and the stream contract — machine-readable to stdout, progress to stderr,
      so `secrev sweep target > hits.jsonl` yields a valid file. **The CLI is the only module that
      writes.** `sweep.py` and `recon.py` return records; this file puts them somewhere. That keeps
      G-4 containment — never write inside the reviewed target — in one checkable place instead of
      two, and it makes the golden tests byte-comparisons over returned values rather than over
      files a test had to create.
      Both destinations, not one: §7's third DoD item requires the workspace write, and
      `STACK.md` §3 requires the redirect to yield a valid file. `run.json` is written here too —
      §6 says build the layout now even though nothing reads across versions until M7, and it is
      where the timestamps and the tool version go, being the one artifact NFR-3 exempts.
      *Accept:* `secrev sweep <fixtures> > out` produces parseable JSONL with nothing else in it.

- [ ] **TASK-M1-010 — Cross-platform verification.** The NFC divergence is the one difference a
      Linux-only run cannot see, and self-application will not catch it either: it surfaces months
      later as verifications expiring for no reason.
      **Partly done.** The job existed but compared nothing: it waited for `recon.py`, so both
      runners wrote the same placeholder and `compare-platforms` printed "Linux and macOS agree"
      having diffed two identical strings. It now hashes the inventory as soon as `inventory.py`
      exists, which is where NFC and traversal order are actually decided — the artifact
      comparison still waits for `recon.py` and `sweep.py`, and that wait *is* legitimate build
      order (TASK-M1-007/008).
      **The logic half is now verified locally, and it found a real bug.**
      `tests/test_sweep.py::test_nfd_and_nfc_filenames_produce_identical_artifacts` writes one
      tree with an NFD filename and one with NFC — ext4 stores the bytes it is given, so both
      forms can exist side by side on Linux — and asserts `hits.jsonl` and the candidate ids come
      out identical. It failed on first run with `FileNotFoundError`: `inventory.walk` NFC-
      normalises `path` for the record, and `sweep`/`recon` were reopening the file through that
      normalised name, which does not exist on ext4 when the filesystem stored NFD. `FileEntry`
      now carries `os_path` (`compare=False`, so it stays out of the record and out of equality)
      and readers use it.

      That defect is worth naming precisely, because it is the shape this task exists for: on
      APFS, which matches either normalisation on lookup, the broken code works. It fails only on
      the platform *without* the forgiving filesystem — the mirror image of the divergence the
      cross-platform job was built to catch, and invisible to a macOS-only run.

      **Still needs a macOS run**, and the residue is now precise: whether APFS actually hands
      back NFD for a name written NFC. That is a claim about the filesystem, not about this code,
      and no Linux machine can settle it.
      *Accept:* the cross-platform hash-comparison job passes on a real macOS runner, having
      compared a non-empty digest.

- [x] **TASK-M1-012 — `STACK.md` §5's exclusion list was incomplete for real targets.** Found by
      the §7 requirement to run recon "against a real repository", which is exactly what that item
      exists for — the fixture tree could never have shown it.

      **Resolved rather than raised, on reflection.** The first instinct was to treat this as a
      spec question for the owner, but it is not a conflict between documents: §5 and §2.2 are
      both in `STACK.md`, and §2.2 mandates the very directory §5 forgot. A document contradicting
      itself is a defect in that document, and "raise, do not resolve" (`BRIEF_M1.md` §8) is about
      a brief disagreeing with the PRD, where resolving would destroy the signal that the PRD needs
      correcting. Nothing is lost by fixing this one.
      **Result: 1952 files → 137, 703,763 lines → 16,348, 1416 Python files → 38.**
      Exact names, not a `.venv*` / `*_cache` pattern — a pattern is a denylist over a shape (P3),
      while a named directory is auditable and reported verbatim in `recon.json`.

      Original finding, kept because the reasoning is the useful part:

      Recon of this repository reports **1952 files and 703,763 lines**, of which the overwhelming
      majority are `.venv-audit/`, `.ruff_cache/`, `.mypy_cache/` and `.pytest_cache/`. §5
      enumerates the exclusions as `.git/`, `node_modules`, `.venv`, `venv`, `__pycache__`, `dist`,
      `build` — so `.venv-audit` is *not* excluded, while `.venv` is, and §2.2 of the same document
      is what mandates `.venv-audit` existing in the first place. The two sections disagree in
      effect.

      Why it matters beyond a wrong number: `by_language` reports 1416 Python files for a project
      with about a dozen, which is a coverage claim with nothing behind it, and a sweep over that
      tree would generate thousands of candidates out of vendored third-party code. Under P4 every
      candidate must be resolved, so this does not merely add noise — it makes the ledger
      unfinishable.

      *Accept:* §5 says what is excluded and why, and recon of this repository reports a file
      count in the right order of magnitude. Both hold.

- [ ] **TASK-M1-011 — Close the milestone.** Tick `BRIEF_M1.md` §7, move `.claude/MILESTONE` to
      `M2`, and extend the DoD assertion in `attack.py` to cover `BRIEF_M1.md` as well — it
      currently guards the M0 boxes only, which would let the marker move past an unfinished M1.
      *Accept:* `session-start.sh` reports M2; no unticked box in either brief.
