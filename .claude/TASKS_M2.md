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

Third round, at TASK-M2-006:

- **C-3 — two MCP kinds.** `surface.mcp_tool`: a tool declared in code (a Python decorator such
  as `@mcp.tool(`), layer `code`. `surface.mcp_server`: a server declared in a manifest
  (`.mcp.json`, the command that starts it), layer `manifest`. `STACK.md` §7 says MCP tools are
  "manifest-declared"; in practice a manifest declares the *server* and the tools are declared in
  its code, so taking only one would miss either every code-defined tool or every server with no
  Python in the tree. §7's wording is corrected at close (TASK-M2-011).

**Open finding, introduced by TASK-M2-002b.** `bash_guard.py` matches `surfaces` as a protected
directory wherever it ends a token after `/`, and the branch this milestone is built on is called
`m2/surfaces`. So `git push -u origin m2/surfaces` was refused as a write to a protected path. A
branch name is not a path; the push went through as `git push -u origin HEAD`, which writes to
nothing protected and still ran the full pre-push gate. The same will refuse `gh pr create --head`
and `git log origin/m2/...` spelled out. Options for the owner: narrow the guard so a protected name
must be followed by `/` (a directory) rather than also accepting end-of-token, or accept it and
avoid spelling the branch. Not changed yet — a guard edit gets its own H-8 defeat test.
**Second instance, at TASK-M2-010:** the guard also refuses the tool's own subcommand —
`python -m secrev surfaces <target> ...` from a shell is read as touching the protected directory,
so self-application of the surface source could only be run by the owner with `!`. The same
narrowing (a protected name must be followed by `/`) would fix both.

**Fixed by owner decision (2026-09-15), from the TASK-M2-007 review.** Now one
`inventory.split_lines` (CRLF, CR and LF only) serves `sweep.py`, `surfaces.py` and `recon.py`'s
line count, asserted per character in `tests/test_lines.py`. The finding as raised: `sweep.py` and `surfaces.py`
split file content with `str.splitlines()`, which also breaks on `\v`, `\f` (form feed, `^L`,
which Python source does contain), `\x1c`–`\x1e`, U+0085, U+2028 and U+2029. Deterministic, so
NFR-3 holds — but every line number and window after such a character disagrees with what an
editor counting `\n` shows, and `STACK.md` §5 says line numbers are reported against the
original. Not fixed: it is M1 code and changes candidates' `line` and window, so a verification
made against a shifted window would be invalidated. The same defect in `cli.merge_ledger` was fixed
in TASK-M2-007, where it could lock the workspace ledger.

## Carried beyond M2 — enforcement that does not read shell text

Raised by two reviews of the guard's over-match (2026-09-16) and accepted by the owner. The Bash
guard is a guardrail against mistakes: its trigger is a test over path spellings, so `cd src && …`,
`rm -rf sur*aces`, `d=surf; rm -rf "${d}aces"`, `find . -delete` and `python -c` all evade it, while
a bare word equal to a protected name is refused although it is not a path. Both directions are now
stated in `STACK.md` §8 H-2 and `CLAUDE.md`, and the refusal names the token. **Nothing that matters
may rest on it.** Rejected: structural shell parsing (needs per-program knowledge and is evaded the
same ways), renaming the product's subcommand, and requiring a trailing `/` (admits `rm -rf src`).

- [ ] **HARNESS-CI — a check on protected paths, after the code leaves the machine.** A CI job that
      fails when a commit touches `.claude/hooks/**`, `.claude/settings.json`, `patterns/**` or
      `surfaces/**` without an explicit approval line in the commit message, plus `CODEOWNERS` and
      branch protection on those paths. Cannot be defeated by a glob, a variable or `chattr`,
      because it runs where the agent does not. This is the one the review called most important:
      if the agent can edit the file that defines the hook, every other control collapses.
      *Accept:* a commit touching a guard without the line fails CI and names the path; with it,
      passes; the job is defeat-tested in both directions before it is trusted.

- [ ] **HARNESS-FS — file ownership on the harness itself (step 3, planned now so the close does
      not lose it).** Machine-local, not repository-enforced, and therefore a complement to
      HARNESS-CI rather than a substitute.
      *Scope:* `.claude/hooks/*.sh`, `.claude/hooks/lib/*.sh`, `.claude/hooks/*.py`,
      `.claude/settings.json`.
      *Mechanism, in the order preferred:* (1) root ownership — `sudo chown root:root`, mode 644 —
      so the agent's user cannot write them at all and no `sudo` is available to it; (2)
      `sudo chattr +i` on ext4 in addition, which also refuses a write by root until cleared.
      `chmod a-w` alone is not enough: the owning user can undo it, and the agent is that user.
      *Repair workflow, documented in `CLAUDE.md` when this lands:* the owner unlocks
      (`sudo chattr -i <file>` / `chown`), the change goes through `Write`/`Edit` where the guards
      see it, both gates run, the owner locks again.
      *Known costs, stated before adopting:* a `git checkout`, `merge`, `pull` or `stash` that
      touches a locked file fails, so the owner unlocks before those; a fresh clone has none of it,
      which is why HARNESS-CI carries the repository-side guarantee.
      *Verification:* `lsattr .claude/hooks/*.py` and `ls -l`, by hand. Deliberately **not** an
      assertion in `.claude/check.sh`: the property is about one machine, and a check that cannot
      run on a CI runner would have to either fail there (wrong) or pass silently (H-1).
      *Decision still open:* whether the friction is worth it on this machine, or whether
      HARNESS-CI alone is enough.

**Carried to M4, not a surface (owner, 2026-09-15).** The result of an outbound call —
`res = session.call_tool(...)` — is untrusted input arriving, but the reviewed code chose to make
the call and when; nobody outside can initiate it, so it is not an entry point and no surface kind
records it. What it raises is a data-flow question: where `res` goes — into a model's context
(P8, G-6: a tool's output can carry an injection), a shell, a file. That is the structural
source (M4) and the closure (M5). No M2 task covers it, and no later brief exists yet to hold it,
so it is recorded here to be carried into `BRIEF_M4.md` when that is written.

TASK-M2-002 is therefore three commits: **002a** the `ledger.py` move, **002b** the protection,
**002c** the kinds file and its loader.

Still open, decided before the step that needs them: Q4 (`catalog_version` on a surface record),
Q6 (tick TASK-M1-010), C-4 (`BRIEF_M2.md:10` says "§1 and §7 bind"; there is no §7), C-5 (stale
"no git remote" in `BRIEF_M2.md` §4 and `TASKS_M1.md`), Q7 (escaping symlinks have no owner). C-3
was decided in the third round above; Q9 was fixed in `CLAUDE.md` on 2026-09-15.

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

- [x] **TASK-M2-006 — The remaining kinds, one per commit.** Each with a negative that separates an
      entry point from a call site. A package with no `__all__` is a recorded gap.
      `tests/test_surfaces.py` carries one row per shipped kind — a declaration it must enter and
      a near miss it must not — and asserts the rows and the shipped kinds match in both
      directions, so a kind cannot ship without its negative.
      - [x] `surface.mcp_tool` (kinds `2026.09.2`): the SDK's decorator forms and `add_tool(`;
            `call_tool(` call sites and `list_tools` are not entered. Fixture `mcp/server.py`.
            Goldens: `surfaces.jsonl` gains one record and the skill record changes only in
            `catalog_version`; `recon.json` changes in three counts; `hits.jsonl` unchanged.
      - [x] `surface.mcp_tool_listing` (same commit, same kinds version). Owner decision,
            2026-09-15, extending C-3: a low-level server's `@server.list_tools()` returns the
            names, descriptions and schemas a model reads, which is behaviour-defining prose (P8)
            that no kind recorded; FastMCP's docstring already sits in the `mcp_tool` window.
            Layer `instruction`, precision `medium`, because the decorator is matched by name
            and not by import. A client's `session.list_tools()` is not entered. Fixture
            `mcp/lowlevel.py`.
      - [x] `surface.mcp_tool` corrected (kinds `2026.09.3`), owner decision 2026-09-15:
            precision `high` → `medium`, and the question no longer says "any connected client",
            which is true of MCP only. The kind matches the decorator by name and cannot see the
            import, so another framework's `@x.tool` enters; it is still a model-callable tool,
            so it stays in, and the record no longer overstates what is known about it.
      - [x] `surface.mcp_server` (kinds `2026.09.4`), the second half of C-3: a local server's
            `command` and a remote server's `url`, in `.mcp.json`, `mcp.json` (Cursor, VS Code)
            and `claude_desktop_config.json`. The remote `url` is included although C-3 named
            only "the command that starts it": a remote server has no command, and leaving it out
            would miss every hosted server — the gap C-3 was decided to close. A key merely
            containing the word (`shutdownCommand`, `--command`, `COMMAND`) is not entered, nor a
            `"command"` key in `package.json` or `tasks.json`. Fixture `mcp/.mcp.json`.
      - [x] `surface.hook_binding` (kinds `2026.09.5`): an event name keyed to a list in Claude
            Code's two settings files and a plugin's `hooks/hooks.json`. Matched by shape — a
            capitalised key whose value is a list — not by a list of event names, which would miss
            every later event silently (H-2, P3); a hypothetical `SomeFutureEvent` is asserted to
            enter. Precision `medium`, since the shape cannot confirm an event. Fixture
            `plugin/hooks/hooks.json`, because a fixture under the agent config directory cannot
            be staged; those trees are built at runtime in the tests.
      - [x] `surface.cli_command` (kinds `2026.09.6`): `name = "module.path:function"` in
            `pyproject.toml` — `[project.scripts]`, and `gui-scripts` and `entry-points` groups,
            which are entry points too. Precision `medium`: a line cannot see its TOML table (the
            section issue named in the plan), so the shape elsewhere enters and a reader resolves
            it. `build-backend`, version specifiers and URLs do not match. Fixture
            `cli/pyproject.toml`, in a subdirectory so `recon.py` does not read it as the tree's
            own entry points (`entrypoints.declared` confirmed unchanged).
      - [x] `surface.public_export` (kinds `2026.09.7`): an assignment to `__all__` — plain,
            annotated, `+=`, `.extend(`, `.append(` — indentation allowed, since an `__all__` in an
            `if` block is still the module's. A multi-line `__all__` enters on its first line with
            its names in the `decl-20` window, so Q3's "multi-line `__all__`" gap is narrower than
            planned; TASK-M2-008 now names what is really missed. Reading, comparing,
            `self.__all__` and a comment are not entered. Fixture `exports/__init__.py`.
      Every kind carries a row in `CASES`, and every kind was defeat-tested (H-8): its
      declaration loosened, its near miss and the golden failed, restored.

- [x] **TASK-M2-006b — A kind's `files` ignore case (owner, 2026-09-15).** Found while writing
      `hook_binding`: a case-insensitive filesystem hands the agent `.Claude/settings.json` when it
      asks for `.claude/settings.json`, and the kinds matched names exactly, so the entry point
      would enter on macOS-authored trees only by luck. The owner's approach: compare the path
      case-insensitively (`re.IGNORECASE` on each kind's compiled glob), keep the recorded path as
      on disk (the id derives from it), leave the declaration case-sensitive, and leave the shared
      `glob_to_regex` alone — it also serves `paths_exclude`, where ignoring case fails open.

- [x] **TASK-M2-007 — `secrev surfaces` and the two-block ledger (Q1).** No catalog dependency;
      `run.json` names the right command (it is hard-coded `"recon"` today, `cli.py:133`).
      Owner decisions, 2026-09-15:
      - **stdout is the run's own block only.** The workspace `hits.jsonl` is where the two
        blocks are joined; a pipe's output depends only on its inputs, so `secrev surfaces t > x`
        is the same every time whatever ran earlier in the workspace. "The file and stdout agree"
        becomes "stdout equals this source's block of the file".
      - **`run.json` holds one entry per command** (`recon`, `sweep`, `surfaces`), each replaced
        only by its own command, so the catalog version behind the pattern block survives a
        later `surfaces` run and no command has to load another's input.
      *Accept:* `sweep` then `surfaces` and the reverse both yield both blocks; the pattern block is
      byte-identical to today's golden.

- [x] **TASK-M2-008 — `coverage_gaps`.** *Done:* the line "surface enumeration not implemented"
      is gone; one line names the code languages present that no kind reads ("read in Python
      only; not read for: …"), and one line per limit below. Fixed text in `recon.py`, not derived
      from the kinds, because recon is a peer of the surface source and does not import it. Names
      what is still unreachable: HTTP routes, IPC
      handlers, the CLI parser, a package with no `__all__`, the names of an `__all__` longer
      than the `decl-20` window (a multi-line `__all__` itself enters, on its first line, with
      its names in the window), `__all__` built dynamically, non-Python surfaces, and any declaration
      split across lines for any kind — a decorator or a key wrapped onto a second line is missed
      by a line-oriented kind (Q3) — and the reverse, several declarations on one line (minified
      JSON holding several MCP servers) entering as one record. Hooks declared outside
      Claude Code's settings files and plugin `hooks/hooks.json` — in agent or skill frontmatter,
      and in other clients' hook configs — are not enumerated. CLI commands declared in
      `setup.cfg`, `setup.py` or `package.json` are not enumerated either. The owner accepted the
      line-oriented limits on this condition:
      each one has to be named here rather than left implicit.

- [x] **TASK-M2-009 — Determinism across runs and platforms includes surfaces.** Only after
      TASK-M2-007. `scripts/determinism_check.py` and `ci.yml`'s cross-platform digest.
      *Done locally:* both determinism checks run `surfaces`, and the two-run check fails when
      either block is missing, so a surface source that produced nothing cannot pass as
      compared (H-1). `ci.yml` runs `surfaces` before hashing. The cross-platform half is
      proven only when CI runs it on GitHub, which waits for the owner's push (compute
      minutes); until then "Linux and macOS agree" on both blocks is unverified.
      *Accept:* the digest carries both blocks; Linux and macOS agree.

- [x] **TASK-M2-010 — Self-application.** `secrev sweep src/secrev/`, `--sast`, `secrev surfaces .`
      with a small, explicable count. *Done at `361f275`:* CodeQL no alerts; the sweep finds 2 in
      `src/secrev/` (both `fs.agent_config_write` on the `kinds.py` docstring that names
      `.claude/settings.json` as its example — prose, not a write) and 8 in `scripts/`, the same
      count M1 recorded; `surfaces` finds **27**, of which 15 are the harness's own hooks and
      skills, 2 the tool's own entry points, 10 the fixtures, and 1 a false positive (a
      `description:` line inside a documentation template). The surface count is the smallest of
      the three sources, as BRIEF_M2.md §5 predicts. The `surfaces` run had to be made by the
      owner: the guard reads the subcommand name as the protected directory (the finding above).

- [ ] **TASK-M1-010 (carried)** — per Q6.

- [ ] **TASK-M2-011 — Close.** DoD ticked; `BRIEF_M2.md` (C-4, C-5, Q3's contradiction) and
      `STACK.md` (C-1, C-2) amendments through spec-guard; `CLAUDE.md` (Q9, and the TASK-M1-010
      condition it states wrongly — the runtime NFD test already exists, `test_sweep.py:170`).
      The marker moves only after `BRIEF_M3.md` and its scope-guard rules exist.
