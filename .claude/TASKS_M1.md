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

- [ ] **TASK-M1-004 — `ids.py`.** Stable candidate id from `(relative_path, line, rule_id,
      ordinal)`. Before `sweep.py`, for the same reason `inventory.py` came before both: an
      identity derived from a traversal counter looks correct until something is inserted ahead
      of it.
      *Accept:* the id of an existing candidate survives a file being added, removed and renamed
      elsewhere in the tree.

- [ ] **TASK-M1-005 — `catalog.py`.** YAML load and strict validation (`BRIEF_M1.md` §4).
      `yaml.safe_load` only. A schema violation exits 2 naming the offending pattern id.
      `flags` is a fixed subset, never passthrough; no `multiline` field, now or later.
      *Accept:* every malformed catalog in the fixtures exits 2 and names the id.

- [ ] **TASK-M1-006 — `patterns/_base.yaml` + `python.yaml`.** The seed patterns (§6). Each ships
      a positive **and** a negative fixture — a pattern without a negative fixture drifts into
      over-matching and nobody notices (§9).
      *Accept:* both fixtures present for every pattern; `precision: low` is an expected value and
      not a defect.

- [ ] **TASK-M1-007 — `sweep.py` → `hits.jsonl`.** Line-oriented only. Two hits on one line stay
      two hits (D-6); no dedup by location. Patterns are questions, not verdicts — nothing here
      concludes anything (FR-3.2).
      *Accept:* golden byte-comparison against a committed expected file.

- [ ] **TASK-M1-008 — `recon.py` → `recon.json`.** §3's shape. Exclusions recorded as applied,
      never silently. `entrypoints` from declared metadata only; deeper enumeration is M2.
      *Accept:* golden byte-comparison; the determinism stage's "waiting on recon.py, sweep.py"
      disappears and the artifact checks run.

- [ ] **TASK-M1-009 — `cli.py`.** Last, not first. `recon` and `sweep` subcommands, the exit-code
      contract (0/1/2/3) and the stream contract — machine-readable to stdout, progress to stderr,
      so `secrev sweep target > hits.jsonl` yields a valid file.
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
      **Still needs a macOS run**, and nothing local can substitute: the digest has only ever been
      produced on ext4. Whether APFS yields the same bytes is precisely the untested claim.
      *Accept:* the cross-platform hash-comparison job passes on a real macOS runner, having
      compared a non-empty digest.

- [ ] **TASK-M1-011 — Close the milestone.** Tick `BRIEF_M1.md` §7, move `.claude/MILESTONE` to
      `M2`, and extend the DoD assertion in `attack.py` to cover `BRIEF_M1.md` as well — it
      currently guards the M0 boxes only, which would let the marker move past an unfinished M1.
      *Accept:* `session-start.sh` reports M2; no unticked box in either brief.
