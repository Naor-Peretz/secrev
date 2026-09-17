# Brief — M3.5: The Reviewer Against a Hostile Target

**Milestone:** M3.5 — inserted between M3 and M4, not a renumbering
**Prerequisites:** M1 (`inventory`, `ids`, `catalog`, `sweep`, `recon`), M2 (the surface source and the
two-block ledger), `STACK.md` (§2.1 self-application, §3 exit codes, §5 traversal, §8 the harness),
PRD (G-3 redaction, P3 denylists, P11 detection-does-not-decide-scope, NFR-3, NFR-4, AC-10)
**Goal:** a target cannot hide code from the tool, stop the tool, or make the tool leak.

**Provenance, and why it is unusual.** This brief is not derived from the PRD. It exists because an
external review read the source rather than the README and ran the tool against purpose-built target
trees. Every finding below was reproduced against the code before it was written down here.

That provenance changes what binds. M1–M3 were written *from* the documents; this one is written
*against* them, and where a finding contradicts binding text the text is wrong and is corrected
through spec-guard rather than worked around. Three such contradictions are already known and are
named in §4.

**Why a milestone rather than a correction pass.** Strictly, each finding belongs to the milestone
that introduced it — M1 for the walk, the catalog and recon; M2 for the ledger merge. But they are
cross-cutting, several contradict binding documents, and `.claude/MILESTONE` holds one token. A
milestone is the honest container for work that spans four modules and two binding documents.

**The number.** Inserting `M3.5` rather than renumbering M4–M12 keeps every existing reference in
the PRD, the briefs and the receipts true. PRD §13's build order has no row for it, and adding one
is a **PRD correction raised for the owner** (§6), not something this brief decides.

---

## 1. Scope

**Build:** fixes, each with a test that fails first; and corrections to the documents that currently
describe behaviour the code does not have.

Six groups. A–E are defects; **F is the most urgent and is not a defect at all** — it is text that
claims coverage the code does not provide, which this project holds to be worse than an absent
check, because the green is taken as evidence.

- **A — Scope evasion.** A target must not be able to hide code from the sweep.
- **B — Secrets.** G-3 must actually redact before anything reaches the ledger.
- **C — Liveness.** A target must not be able to hang the run or crash it, and one bad file must not
  end the review of every other file.
- **D — Containment.** The tool must not read outside the target it was pointed at.
- **E — Self-application and the harness.** `self_check.py` is a denylist, which P3 makes a finding;
  the settings allowlist has no assertion at all, which is how two holes got in.
- **F — Documents that describe behaviour the code does not have.**

**Do not build.** Each is a later milestone, or a fix shaped wrongly:

| Not now | Why | When |
|---|---|---|
| `structure.py`, `_structure.yaml` | Several findings would be *easier* with an AST, which is exactly the pressure that gets M4 designed around what M3.5 happened to need | M4 |
| `closure.py`, `_instruction.yaml`, `_manifest.yaml` | Q7's escaping symlink and the instruction layer both live here and are already scoped there | M5 |
| Triage, severity, the ledger gate | Nothing here decides whether a candidate is real | M7 |
| New surface kinds, new archetypes | M3.5 fixes the machinery; it adds no questions | M8 |
| **Removing the exclusions entirely** | Walking `node_modules/` makes the tool unusable on any real target and trades a silent gap for a slow one. The answer is exclusions that are *visible and overridable*, not absent | — |
| **A different regex engine** | `STACK.md` §2 considered and rejected `regex` with a reason. The answer to a quadratic pattern is bounded input and a fixed pattern, not a new dependency on the critical path | — |
| **Sandboxing the target** | Real, and far larger than this. The findings here are reachable without executing anything the target ships | — |

---

## 2. Deliverables

```
src/secrev/ledger.py      # B: redact before truncate; boundaries that hold inside a name
src/secrev/inventory.py   # A: exclusions recorded as applied, not as a constant
                          # A: a NUL byte stops meaning "do not review"
                          # C: regular files only; no read of a FIFO or a device
                          # C: a symlink loop is an input fact, not a RuntimeError
                          # D: one read per file, carried forward
src/secrev/recon.py       # A: report exclusions that were applied
                          # D: no is_file()/is_dir() through a symlink; validate the ref path
src/secrev/cli.py         # C: an unreadable file is exit 2, never exit 3
                          # E: atomic ledger write; workspace mode 0o700
src/secrev/catalog.py     # C: input bounds, and a docstring that scopes the risk correctly
patterns/_base.yaml       # C: log.sensitive stops being quadratic
scripts/self_check.py     # E: allowlist shape, and the workspace-write check README claims
.claude/settings.json     # E: no auto-approved arbitrary execution
tests/harness/attack.py   # E: the allowlist is asserted, so a third hole cannot arrive silently
README.md                 # F: the status block, and the AST claim
```

`patterns/` is in the tree, which M2's brief forbade and this one permits for one reason only: a
shipped pattern that takes an hour on a crafted line is a defect in that pattern, not a new rule.
**No pattern is added and no question changes.**

---

## 3. The shape of the work

**Every fix gets a target tree that reproduces it, and the test is written first.** This is the
milestone where that discipline matters most, because each finding was found by construction rather
than by reading — a fix with no reproducing fixture is a guess that the fix addressed the finding.

**Fixtures here are hostile by design**, which is new. `tests/fixtures/` has so far held examples;
this milestone adds a tree whose purpose is to defeat the tool. Two constraints follow: a FIFO and a
symlink loop cannot be committed to git, so they are built at runtime and skipped where the
filesystem refuses them (the `test_determinism.py` precedent); and a fixture carrying a NUL byte
must not be linted, formatted or swept as ordinary source.

**Exclusions become data with an escape hatch, not a constant.** The failure is not that `dist/` is
skipped — it is that `recon.json` reports the static list, so a reader cannot tell a skipped
`dist/` from an absent one. Report what was applied; make the set overridable; keep the default.

**`--max-file-bytes` and a line-length bound are mechanism, so they are `STACK.md` §5 amendments**,
raised before they are implemented. A bound that appears only in code is a limit nobody agreed to.

---

## 4. Definition of done

Each box names the evidence, because "fixed" is not observable and this milestone's whole subject is
checks that looked like they were working.

- [x] **A1 — Exclusions are reported as applied.** `recon.json`'s `excluded` lists the directories
      actually present and skipped, not `EXCLUDED_DIRS`. `inventory.exclusions_applied()` is called
      by the code rather than only by a test. Evidence: a fixture with `dist/` and without it produce
      different `recon.json` — `test_a_tree_with_dist_and_one_without_report_differently`, red
      first. The fixture golden's `excluded` falls from all fourteen constant names to the one
      directory the tree actually contains.
      **The verification that carries the weight is what did *not* change:** `files_total` stays 30
      and `loc_total` stays 291. Exclusions were always *applied* correctly; only the *report* was
      wrong. Had either number moved, the fix would have altered what gets walked rather than what
      gets said about it, which is a different and much larger change.
- [x] **A2 — A target cannot hide code in an excluded directory without that being visible**, and
      the exclusion set is overridable from the command line. Evidence: the golden shows the applied
      list; an override sweeps `dist/` and says so.
      **`coverage_gaps` now states the skipped directory**, which is what makes the headline true:
      it was previously visible only in `inventory.excluded`, to a reader who thought to compare
      that list against a constant they would have had to go and find. The line *disappears* under
      an override, so the override is visible in the artifact rather than only in the invocation
      that produced it.
      **`--exclude` replaces rather than subtracts.** A subtractive flag would require the caller to
      know all fourteen default names to predict what a run will do, and the applied set is reported
      either way — so what you pass is what is skipped. `--exclude ""` skips nothing, which is the
      case A2 exists for: reviewing a target's `dist/` rather than trusting it.
      **The coupling comment asserted an invariant that was already false.** It asked that ruff's
      `extend-exclude` and `EXCLUDED_DIRS` be kept "identical so the linter and the scanner never
      disagree about scope". One held six names and the other fourteen — missing `.git`,
      `.venv-audit` and all five tool caches. Broken deliberately rather than repaired: what we skip
      linting *our* code and what we skip reviewing *someone else's target* are different questions.
- [x] **A3 — Nothing about a file's name or size removes it from review.** *(Reopened three times,
      and each reopening moved the evasion further from the thing the box originally named.
      First: one NUL stopped working in M3.5 and eight did not, because the target picks the ratio,
      so the answer is the exit code and a `coverage_gaps` line rather than a different threshold.
      Then a third review moved it off the byte count entirely — `install` with a shebang and no
      extension, and a `SKILL.md` with a NUL in an HTML comment, were both still exit 0, because
      the test for "is this code" was the extension. That fix added a shebang check and a set of
      artifact names, **which was itself a denylist**, and a fourth review walked past it with
      `AGENT.md`, `prompt.txt` and a 5 MB `setup`. `_is_code` now asks one inverted question: an
      unread file counts unless its extension is a known binary asset, so the burden of
      enumeration is ours. See `.claude/TASKS_M3.5.md`.)* A runnable `install.sh` carrying a
      NUL in a comment produces the same candidate as one without it. Evidence: a fixture pair, and
      the sweep finding the same rule in both —
      `test_a_nul_in_a_comment_does_not_hide_a_script_from_the_sweep`, which failed first as
      `assert ['net.fetch_exec'] == []`: the clean script yields a candidate and its twin, differing
      by one byte inside a comment, yields nothing at all.
      **The `STACK.md` §5 amendment went first**, through spec-guard, because §5 bound "detected by
      NUL byte in the first 8 KiB" and a brief loses to `STACK.md` on mechanism. Binary is now
      "non-text bytes exceed 5% of the first 8 KiB", and the 5% was **measured, not chosen**: text
      tops out at 0.00% across the whole fixture tree, the evasion sits at 1.75–3.33%, and the
      lowest real binary at 8.51%. The threshold is placed in the empty band between them, which is
      why **no golden changed and no fixture was reclassified**.
- [x] **B1 — `redact()` catches what it claims.** `DB_PASSWORD=…`, `{"password": "…"}`,
      `OPENAI_API_KEY="…"` are all redacted. Evidence: a table test over the forms the review used,
      each failing before the fix. `test_the_review_forms_are_redacted` — seven forms, all seven red
      first. A third cause turned up beside the two the review named: `Authorization: Bearer <token>`
      redacted the word `Bearer` and left the token, so the scheme moved into the separator.
- [x] **B2 — Redaction happens before truncation.** A 40-character credential cut to 20 is still
      redacted. Evidence: the test that fails against today's `excerpt()`, and the docstring's
      ordering argument corrected to match what the code does.
      **Two edges cut, not one.** The 200-character cap is the one the review named; the ±24
      margin does the same thing sooner, clipping a credential that sits just past it to a handful
      of characters before the redactor ever sees it. Both are the same finding — something
      shortens a secret below the length `_LONG_OPAQUE` measures — so both are fixed, and there is
      a red-first test for each.
- [x] **C1 — A FIFO, a device or a socket in the target does not block the walk.** Evidence: a
      runtime-built FIFO; the run completes and records the path as not-a-regular-file.
      **This is the one finding that could not be reproduced inside the suite.** Opening a FIFO
      with no writer blocks forever — nothing raised, nothing timed out — so a test written red
      would have hung pytest itself with no timeout to rescue it. The reproduction ran in a bounded
      scratchpad probe instead, `inventory.walk` on a daemon thread with a deadline, and the suite
      received its three assertions only once completion was guaranteed.
      **The check had to go before the read, not around it**, which is exactly why `-002`'s
      `except OSError` never reached this: a blocking open raises nothing for any `except` clause
      to catch. And the same defect sat in all three readers — `inventory`, `sweep` and `recon` —
      so fixing one would have left a review that still never finishes.
- [x] **C2 — A symlink loop and an unreadable file are exit 2, not exit 3, and the rest of the tree
      is still reviewed.** Evidence: both cases run to completion; `STACK.md` §3's contract is
      quoted in the test.
      **Ticked with one deliberate divergence from the wording, for the owner to confirm or
      reverse.** The two cases got *different* codes:
      - **Unreadable file → exit 2**, as written. Content that should have been reviewed was not,
        and exit 0 would report a clean review of a tree the tool could not fully see (H-1).
      - **Symlink loop → exit 0**, not 2. The loop is fully resolvable *as a fact*: it is recorded
        as a symlink that does not stay inside the tree, nothing went unreviewed, and a loop has no
        content to review. Exit 3 was the defect; exit 2 here would be the overcorrection, making
        every target that happens to contain a self-referential symlink report a usage error.
      The defect the box names — a target fact reported as an internal error — is gone in both
      cases, and both run to completion. What changed is that "not exit 3" and "therefore exit 2"
      turned out to be two different claims once the cases were separated.
- [x] **C3 — A crafted line cannot make a full sweep take superlinear time.** *(Reopened twice, and
      the wording above is widened because "the shipped catalog" was the wrong subject. First: four
      patterns were quadratic, not one, and the check measured a single pattern with `re.search`
      where `sweep.py` uses `finditer`. Then a third review found the sweep still quadratic with
      every pattern linear — the cost had moved into identity, where each candidate's window was
      rebuilt per match and hashed twice. A regex timing test cannot see that, so a second test
      times `sweep()` itself and asserts the ratio rather than a ceiling. No id moved. See
      `.claude/TASKS_M3.5.md`.)* A 1 MB
      minified line completes within a stated bound. Evidence: a timing assertion with a generous
      margin, plus the rewritten `log.sensitive` with its fixture pair intact.
      Measured: 185.72 ms at 9,600 bytes and 11.4 s at 76,800 before the fix, extrapolating to
      roughly **48 minutes on a 1 MB line**; after it, a 1.2 MB line measures ~1.9 s against a 10 s
      assertion. All seven fixture lines keep their verdicts, 35 golden records change in
      `catalog_version` alone, and **no candidate id moved**.
      **The mechanism was not what the code claimed.** `log.sensitive` had no nested quantifier —
      the blowup is the *outer* scan retrying from thousands of matching start positions. Two
      candidate repairs were measured and rejected for losing findings rather than time:
      `[^()\n]*` is linear but silently drops every nested call such as
      `print(sanitize(password))` — and agreed with all seven fixtures, so the fixtures were not
      the control; `[^)\n]*+` is worse, breaking two shipped positives because a possessive
      quantifier swallows the keyword it exists to find.
      **The adopted fix bounds the rule, not the scan**, which departs from §5's wording above. It
      is taken deliberately — the alternative is a live 48-minute hang in a shipped pattern — and
      the residue is stated: a keyword more than 400 characters into one call is no longer seen.
      **The bounds half of this work is not done**: `--max-file-bytes` and a line-length bound are
      mechanism and remain raised in §6 for the owner.
- [x] **D1 — recon reads nothing outside the target.** *(Reopened and re-closed 2026-09-17: five
      more reach-by-name sites, patched per site the first time. They now derive from `_found_paths`,
      what the walk found, so containment is inherited rather than remembered.)* `pyproject.toml`,
      `package.json`, `.git` and
      `.git/HEAD` as symlinks pointing outside are not followed, and a `ref:` value containing `..`
      is refused. Evidence: a fixture tree with all four — five tests, all red first.
      **The breach published what it read, rather than merely touching it.** The manifests put a
      foreign file's entry points into `recon.json` as `['leaked = private.cli:main']`, and the
      three git cases reported another repository's SHA as this target's version — which, since
      `STACK.md` §6 makes the version a directory in the workspace, would file one tree's review
      under another tree's history.
      **The shape is worth carrying:** `inventory.walk` has never followed a symlink, so
      containment held for every file the tool *discovered* and failed for every file it went
      *looking for* by name. All four breaches are reach-by-name sites. The exception to a rule
      sits wherever the rule is not the thing doing the work.
      The `ref:` case needed no symlink at all — the target supplies the path directly, and
      `path.traversal` is a rule this tool ships, so being subject to it is the self-application
      failure AC-10 exists to prevent.
- [x] **E1 — `self_check.py` does not pass the twenty-four bypasses.** *(Reopened twice, and the
      count in this line is part of the contract rather than decoration. First: eleven more walked
      past the M3.5 denylists, including two `yaml` loaders that contradict "safe_load only", so
      imports and `yaml` members became allowlists. Then four more — a wildcard import, two
      subscripted callees, and an argv whose first element is a shell — and the `os` table became
      an allowlist of the two members this package calls, which its own comment had been asking
      for since M3.5. See `.claude/TASKS_M3.5.md`.)* Aliased imports,
      `from x import y`
      call forms, `os.system`, `__import__`, f-string arguments. Evidence: a fixture file containing
      all nine, asserted to exit 1 — and asserted to *have* exited 0 before the fix.
      **All nine exited 0 with empty stdout and stderr.** The gate did not struggle and report
      something ambiguous; it reported clean on a file containing `os.system`, `__import__` and an
      aliased banned call. Silent success is the worst shape a gate can fail in, and this one had
      been doing it since M0 — because **`self_check.py` had no tests at all**, which is H-8
      exactly: a guard nobody has tried to defeat is an assumption rather than a control.
      **Five of the nine were one defect.** The checker tested the *spelling* at the call site
      instead of resolving what a name refers to, so both aliased heads and all three
      `from x import y` forms fell to one cause and are closed by one mechanism — an import alias
      map — rather than by five more table rows. That is the difference between answering P3 and
      postponing it. Three were genuinely absent entries; one was an `ast.JoinedStr` the
      `ast.Constant` test could not see.
- [x] **E2 — The workspace-write check the README claims actually exists**, or the README stops
      claiming it. Either is acceptable; the two disagreeing is not.
      **The claim is dropped, deliberately rather than for cheapness.** `cli.py` writes by design —
      it is the only module that does — so a name-based AST test would flag it, and deciding
      whether a write lands *inside* the workspace is a dataflow question a name test cannot
      answer. Claiming an AST walk enforces it was the expensive kind of wrong: a check nobody
      looked for because the documentation said it was already there. The README now states the
      limit and names the structural property that actually holds the rule. The narrowed version
      that would be true — flag write calls in any module except `cli.py` — is real work and is
      recorded as a candidate task rather than folded in here.
- [x] **E3 — The settings allowlist is asserted.** *(Reopened twice, on one class named correctly
      the first time. M3.5 removed `head`, `wc`, `ls` and `diff` because each prints a file the
      `.env` deny refuses. A second review found `git diff --no-index` doing the same, plus
      `pytest:*` running anything in an unprotected `tests/`. A third found `git show :.env` and
      `git blame --contents`. Each round removed the commands that had been *demonstrated*; what
      remains is inspection that reports about history rather than anything that can be pointed at
      a working-tree path. See `.claude/TASKS_M3.5.md`.)* No auto-approved rule grants arbitrary command
      execution, and `attack.py` fails if one is added. Evidence: H-8 — add one back, watch it fail.
      Both clauses now hold. The allowlist and the deny list are pinned in `attack.py`, and H-8 was
      performed rather than asserted — with a probe rule added, exactly 1 of 120 assertions failed
      and **named the arriving entry**, while the deny pin stayed green; the probe was then removed
      and `git diff` confirmed `settings.json` differed from HEAD by one line only.
      **`Bash(sh .claude/hooks/*)` is gone.** Permission matchers are prefix-based, so it
      auto-approved any command beginning with that prefix — arbitrary execution, and what made the
      first clause false. Removed on the precedent of `Bash(uv run:*)` in `-000`: the cost is a
      narrow convenience, and neither `sh .claude/check.sh` nor `sh scripts/check.sh` matches it.
      **The residual, stated rather than hidden:** `Bash(uv sync:*)` runs third-party build hooks,
      which is code execution, though not arbitrary *command* execution in the sense this box means
      — it is raised below rather than removed. Two further contradictions sit beside it:
      `Bash(head:*)`, `diff:*`, `wc:*` and `ls:*` each read what `deny Read(**/.env)` refuses, so
      that deny rule is defeated by four allow rules; and `Bash(uv sync:*)` runs third-party build
      hooks, which is code execution, against a `STACK.md` §3 that says nothing may depend on `uv`.
      All three are **raised rather than fixed**: this is the owner's permission set, the reads are
      daily conveniences, and a gate reddened by my unilateral choice is a gate someone edits back.
      `Bash(uv run:*)` was different — removing it cost nothing.
- [x] **E4 — The ledger write is atomic**, and the workspace is created `0o700`. Evidence: an
      interrupted write leaves the previous ledger intact — the final `os.replace` is failed and
      the ledger compares byte-identical to what it was.
      **Three non-atomic writes, not one.** `_write_block`, `write_run_json` and `_emit` were all
      `path.write_text`, which truncates before writing. The box names the ledger; fixing only it
      would have left two identical defects in the same file, and `run.json` is read-modify-write
      too, so a truncating write there loses the entries *earlier* commands left.
      **Refusing before writing was only half the property.** `merge_ledger` already declined to
      touch a ledger it could not read — but nothing protected one it could, and that file is where
      the other source's block is kept byte for byte. A failure in the pattern block's write
      destroyed the surface block, with nothing saying so.
      **The mode was worse than the finding said, and both obvious fixes look right and are not.**
      Measured 0o775, not 0o755: this machine's umask is 002, so the workspace was group-writable
      as well as world-readable. `mkdir(parents=True, mode=0o700)` applies the mode to the final
      directory only, and `exist_ok=True` leaves an existing directory's mode untouched — which is
      every run after the first. Every level is set explicitly, walking down from the base.
- [x] **F1 — Every document claim in §1F is true or gone**, including the README status block, the
      README AST claim, `inventory.py`'s "recorded as applied", `excerpt()`'s ordering argument, and
      `catalog.py`'s ReDoS scoping.
      All five done — four landed with their own tasks (`excerpt()` in -001, `catalog.py` in -007,
      the README AST claim in -009, and `inventory.py`'s claim became true when -003 wired
      `exclusions_applied` in), and the README status block here.
      **The sweep found three the brief did not name, which is why it is a sweep and not a
      checklist.** `ledger.py` attributed the excerpt shape to `STACK.md` §5, which says nothing
      about excerpts — the wording is `BRIEF_M1.md` §5. `CLAUDE.md` still said M3 was "complete in
      work on `m3/overlays`, unpushed" after PR #14 had merged it, which is the worst placement a
      false claim can have: that file loads into every session, so it misdirects from the first
      token. And `CLAUDE.md` presented `self_check.py` as "AST-based on purpose" — true, and the
      very property that made it look sound while it missed nine spellings.
      **One of those is not a false claim but an incomplete one that functions as reassurance.**
      F1 is written about text claiming coverage the code lacks; this was text claiming a technique
      the code genuinely used, phrased so that a reader would stop asking. Corrected on the same
      grounds, because the effect on a reader is identical.
      **Negative results recorded as coverage (P6):** `STACK.md` carries no enforcement claims of
      that shape, and `CONTRIBUTING.md`'s one assertion claim is true — backed by
      `test_the_product_gate_does_not_reach_into_the_harness`.
- [x] Both gates green; self-application clean; every golden regenerated deliberately and every
      changed line explained.
      439 tests (from 372 at M3's close), 120 guard assertions (from 118), mypy across 16 source
      files (from 11), determinism byte-identical with ids stable, self-application clean,
      gitleaks clean.
      **Every golden change was generated into the scratchpad, diffed, explained, then copied** —
      never edited in place. `hits.jsonl` moved twice: eight `match_excerpt` values under -001, with
      **no candidate id moved**, and all 35 `catalog_version` strings under -007. `recon.json`
      gained four fields across -002, -006 and -007 and one `coverage_gaps` line under -005.
      `surfaces.jsonl` never changed at all, which is itself the check working: surface records
      carry the *kinds* file's version, so nothing in the catalog or the ledger should have touched
      them, and nothing did.

---

## 5. Notes for the implementer

- **Order: B, C2, A1, then the rest.** B is a live secret leak into a file that gets committed. C2
  is small and stops one bad file ending a review. A1 is the one where the fix already exists in the
  codebase and is simply not called, which makes it the cheapest honest win.
- **The `ruff` coupling is the root cause of A2 and should be broken deliberately.**
  `pyproject.toml` keeps `extend-exclude` identical to `EXCLUDED_DIRS`, commented "so the linter and
  the scanner never disagree about scope". They are different questions: one is what we skip when
  linting *our* code, the other is what we skip when reviewing *someone else's target*. `dist/` is
  our build output and their shipped artifact.
- **Do not fix C3 by loosening the pattern until it stops matching things.** `log.sensitive` is
  `precision: low` by design and its recall matters; the fix is to bound the scan, not the rule.
- **A fixture that defeats the tool is the deliverable**, not a nuisance. If a fix cannot be
  demonstrated failing first, it has not been shown to address the finding.

---

## 6. Raised before implementation, for the owner

- **PRD §13's build order has no row for M3.5.** Inserting one is a PRD correction. The alternative
  — renumbering M4–M12 — would falsify every existing reference in the briefs and receipts, so the
  recommendation is a row, but the edit is the owner's.
- **Is a NUL byte still the binary test?** `STACK.md` §5 fixes it, and A3 makes it no longer decide
  reviewability on its own. Whether the rule changes, or only its consequence, is a §5 amendment
  either way.
- **`--max-file-bytes` and a line-length bound are new mechanism** and belong in `STACK.md` §5
  before they exist in code.
- **Does the exclusion override belong in M3.5 at all?** A2 adds a command-line flag, which is
  interface. It could be argued into M7's contract freeze instead; the counter-argument is that
  without it A1 reports a gap nobody can close.
