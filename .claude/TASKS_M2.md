# M2 task ledger — the surface source

Scope: `BRIEF_M2.md`. Mechanism: `STACK.md`, especially §5 (determinism) and §9 (testing).
Receipts go in `.claude/receipts.md`. The plan this ledger follows was reviewed by `plan-reviewer`
before any code (verdict: *conflicts with spec* — one ordering defect, five unnamed conflicts, no
scope creep); its findings are folded in below.

## Owner decisions (G0), 2026-09-15

Taken before any code because each one decides bytes in the ledger or the order of the steps.

- **Q1 — one ledger, two blocks.** `sweep` replaces only the `source: pattern` records in
  `hits.jsonl`, `surfaces` only the `source: surface` records, in a fixed order (pattern block
  first). `cli._emit` overwrote the whole file, so without this `surfaces` after `sweep` erased the
  pattern records — and, found by the review, adding `surfaces` to the determinism check or the CI
  digest *before* this lands would have dropped the pattern ledger out of both NFR-3 comparisons
  while both stayed green. Hence the ordering below.
- **Q3 — no `ast` in M2.** Enumeration is line-oriented. A multi-line `__all__` and "the parser
  beneath" a CLI command are recorded in `coverage_gaps` until M4. Keeps `BRIEF_M2.md` §1 and
  `scope-guard.sh:139` as they are. `BRIEF_M2.md` §2 asks for the parser and DoD 5 names only HTTP
  and IPC as unreachable — the brief contradicts itself, and the correction goes through spec-guard.
- **C-1 — surface kinds are data, outside `patterns/`.** NFR-6: "new reachability class = new or
  edited data file". Loaded with `yaml.safe_load`, validated as strictly as the catalog, exit 2
  naming the offending kind. **Raised, not done:** the new directory is tool input exactly as
  `patterns/` is, so H-4's reasoning applies verbatim — adding it to the protected set is a
  `STACK.md` §8 amendment.
- **C-2 — a named declaration window.** Surface records carry `window_spec: "decl-20"`: the same ±20
  lines, anchored on the declaration line, under a different name so a surface window is never
  compared with a pattern window (FR-4.1: surfaces are "traced rather than windowed"; the name says
  what the span is anchored on and claims no judgment was made against it). **A `STACK.md` §5
  amendment**, which names the window specs.

Second round, taken at TASK-M2-002 because the schema is a contract:

- **Detection is data too (NFR-6).** A kind declares `files` (globs) and `declaration` (a
  line-oriented regex), not only its name and question. Metadata-only data would still need code
  for every new kind, which is the thing NFR-6 forbids.
- **Q2 — a neutral `ledger.py`.** The record (`Hit`), `to_jsonl`, the window, redaction and the
  vocabulary both sources share (`LAYERS`, `PRECISIONS`) move out of `sweep.py` and `catalog.py`,
  so neither source imports the other. `ledger.py` owns serialisation and identity-bearing bytes,
  so it joins `is_nfr3_path`; the move is proven by `tests/golden/hits.jsonl` staying byte-identical.
- **C-1 location — `surfaces/_surfaces.yaml`**, beside `patterns/`, loaded the way the catalog is.
- **Protected now, not at close.** The file is tool input exactly as `patterns/` is. The `STACK.md`
  §8 H-4 amendment, `paths.sh` and `bash_guard.py` land in the same task, with a defeat test.

TASK-M2-002 is therefore three commits: **002a** the `ledger.py` move, **002b** the protection,
**002c** the kinds file and its loader.

Still open, decided before the step that needs them: Q6 (tick TASK-M1-010), C-3 (MCP tools:
manifest-declared per `STACK.md` §7, or the Python decorator), C-4 (`BRIEF_M2.md:10` says "§1 and
§7 bind"; there is no §7), C-5 (stale "no git remote" in `BRIEF_M2.md` §4 and `TASKS_M1.md`), Q7
(escaping symlinks have no owner), Q9 (`CLAUDE.md` gives the old id derivation).

---

- [x] **TASK-M2-001 — The harness watches `surfaces.py` before it exists.**
      `is_nfr3_path` in `.claude/hooks/lib/paths.sh` += `src/secrev/surfaces.py`, with an
      `attack.py` assertion that `determinism-guard.sh` speaks on it (absolute and relative paths,
      as for `ids.py`). Until this lands the guard is silent on the one new file that derives ids.
      *Accept:* harness gate green; deleting the new line turns it red (H-8), then restored.

- [x] **TASK-M2-002a — `ledger.py`, the record every source shares (Q2).** `Hit`, `to_jsonl`,
      `window`, `redact`, `excerpt`, `WINDOW_SPEC` moved out of `sweep.py`; `LAYERS` and
      `PRECISIONS` out of `catalog.py`. A pure move, so neither source imports the other.
      `ledger.py` joins `is_nfr3_path`, with an `attack.py` assertion.
      *Accept:* `tests/golden/hits.jsonl` byte-identical (the golden test passes unchanged),
      determinism stage green, 99 guard assertions; removing the new `paths.sh` line fails
      exactly the new assertion (H-8), then restored.

- [x] **TASK-M2-002b — `surfaces/` is protected before it exists.** `STACK.md` §8 H-4 amended
      (through spec-guard); `bash_guard.py` `PROTECTED` += `surfaces`; `is_scoped_path` +=
      `surfaces/*|*/surfaces/*`; `scope-guard.sh`'s message and M2 comment; `CLAUDE.md`'s three
      restatements of the protected set. Five assertions: Bash refuses a write and permits a read;
      a file merely *named* `surfaces.txt` is not protected (the directory is, not the word — so
      `src/secrev/surfaces.py` does not read as the data directory); M0 refuses `surfaces/`, M2
      permits it.
      *Accept:* 104 guard assertions; removing both additions fails exactly the two refusal
      assertions and leaves the three permit/negative ones passing (H-8), then restored.

- [x] **TASK-M2-002c — `surfaces/_surfaces.yaml` and `kinds.py`.** Strict loader mirroring
      `catalog.py`: `safe_load`, unknown fields refused, `multiline` refused by name, one-element
      `layer`, flags subset, `files` globs and `declaration` compiled at load, sorted by id,
      duplicates refused, every message naming the kind. `SurfaceKindError` is a `ValueError`, so
      `cli.py` already reports it as exit 2. The namespace is enforced on both sides: kind ids must
      be `surface.<name>`, and the catalog now refuses a pattern id in `surface`.
      `glob_to_regex` moved from `sweep.py` to `inventory.py`, beside `language_of`, because two
      sources now need the one meaning of `**` — a second copy would let a kind and a pattern read
      one glob differently. First kind shipped: `surface.skill_activation`, not `mcp_tool`, because
      C-3 (manifest-declared vs decorator) is still open and the activation description has no open
      question. **Q4 default, not decided:** the kinds file carries its own `version`; whether that
      is what `catalog_version` means on a surface record is still the owner's call.
      *Accept:* 178 tests (was 155); `tests/golden/hits.jsonl` byte-identical after the glob move;
      mypy over 10 files.

- [ ] **TASK-M2-002 — Surface-kind data and its validator.** *(Superseded by 002a–002c above;
      kept so the numbering in the plan still resolves.)* A data file outside `patterns/` (C-1),
      strict validation, exit 2 naming the kind. Kinds carry `id` (`surface.<kind>`), `layer`,
      `precision`, `question`. The loader is in the scoped tree; the data file's protection is the
      open `STACK.md` §8 question above.
      *Accept:* a malformed kind exits 2 and names it; a kind id equal to a catalog pattern id is
      refused.

- [x] **TASK-M2-003 — `tests/test_surfaces.py`, written red, kept local.** *Done:* red on
      `ModuleNotFoundError` before the module; 14 tests green after. H-8 on the test: with the
      within-file sort removed exactly the ordering test failed — `(2, 'surface.alpha')` first — and
      the other 13, two-run identity and the golden included, stayed green, which is the reason
      the order needs its own assertion. Two runs identical; ids
      stable when an unrelated file is added; NFD and NFC spellings give one id; no surface id is a
      pattern id. Red tests stay on the machine until the module exists — pre-push runs pytest.
      The H-8 control is the **within-file ordering**, which `surfaces.py` owns; files arrive
      sorted from `walk`, and two-run comparisons do not catch a removed sort (CLAUDE.md records
      why), so the assertion must see the order itself.
      *Accept:* red before the module, green after, red again with the within-file sort removed.

- [x] **TASK-M2-004 — The fixture.** *Done:* `tests/fixtures/skills/quiet/SKILL.md`. The sweep
      golden passed unchanged against the new tree (no pattern matches it); the recon golden
      changed in exactly three lines — `files_total` 23→24, `markdown` 1→2, `loc_total` 184→202 —
      diffed in the scratchpad before being copied in. An entry point no pattern matches (AC-9a) and one example per
      kind, never under `.claude/`, `src/` or `scripts/` (`bash_guard.py:78`).
      *Accept:* `tests/golden/hits.jsonl` unchanged; `recon.json` changes only in counts,
      `by_language` and `entrypoints.declared`.

- [x] **TASK-M2-005 — `surfaces.py`, first kind.** *Done:* `surface.skill_activation`; AC-9a
      asserted both halves; `tests/golden/surfaces.jsonl` is one record; `decl-20` in `ledger.py`
      and amended into `STACK.md` §5 through spec-guard. Records in `Hit` field order, ids via
      `ids.assign`, `window_spec: "decl-20"`. The AC-9a test asserts **both halves** — `sweep`
      yields nothing for the file and `surfaces` yields a candidate — so a later pattern that
      happens to match cannot make it pass by coincidence of vocabulary.
      *Accept:* AC-9a, TASK-M2-003 green, `tests/golden/surfaces.jsonl` byte for byte.

- [ ] **TASK-M2-006 — The remaining kinds, one per commit.** Each with a negative that separates an
      entry point from a call site. A package with no `__all__` is a recorded gap.

- [ ] **TASK-M2-007 — `secrev surfaces` and the two-block ledger (Q1).** No catalog dependency;
      `run.json` names the right command (it is hard-coded `"recon"` today, `cli.py:132`).
      *Accept:* `sweep` then `surfaces` and the reverse both yield both blocks; the pattern block is
      byte-identical to today's golden.

- [ ] **TASK-M2-008 — `coverage_gaps`.** Names what is still unreachable: HTTP routes, IPC
      handlers, the CLI parser, multi-line `__all__`, non-Python surfaces.

- [ ] **TASK-M2-009 — Determinism across runs and platforms includes surfaces.** Only after
      TASK-M2-007. `scripts/determinism_check.py` and `ci.yml`'s cross-platform digest.
      *Accept:* the digest carries both blocks; Linux and macOS agree.

- [ ] **TASK-M2-010 — Self-application.** `secrev sweep src/secrev/`, `--sast`, `secrev surfaces .`
      with a small, explicable count.

- [ ] **TASK-M1-010 (carried)** — per Q6.

- [ ] **TASK-M2-011 — Close.** DoD ticked; `BRIEF_M2.md` (C-4, C-5, Q3's contradiction) and
      `STACK.md` (C-1, C-2) amendments through spec-guard; `CLAUDE.md` (Q9, and the TASK-M1-010
      condition it states wrongly — the runtime NFD test already exists, `test_sweep.py:170`).
      The marker moves only after `BRIEF_M3.md` and its scope-guard rules exist.
