# M3.5 task ledger — the reviewer against a hostile target

Scope: `BRIEF_M3.5.md`. Mechanism: `STACK.md`. Receipts in `.claude/receipts.md`.

Unlike M1–M3 this milestone is not derived from the PRD. It comes from an external review that read
the source and ran the tool against purpose-built target trees on 2026-09-16. Every finding was
reproduced against the code before it was written down, and the reproduction is what each task owes
before its fix.

**The discipline that matters most here.** Every one of these is a check that looked like it was
working. So a fix is not accepted because it looks right — it is accepted because the fixture that
defeated the tool now fails first and passes after. A fix with no reproducing fixture is a guess.

## Decided by the owner, 2026-09-16

**M3.5 exists, inserted between M3 and M4.** Not a renumbering: every reference to M4–M12 in the
PRD, the briefs and the receipts stays true. PRD §13 has no row for it — **raised in `BRIEF_M3.5.md`
§6, not resolved here.**

**M3 releases on its own.** None of these findings are M3's code; M3 is four prose files plus test
and guard infrastructure. Folding hardening into that PR would make it unreviewable and would delay
work already verified.

## The findings, as verified against the source

Each was confirmed by reading the code, not by accepting the report.

| # | Finding | Confirmed at |
|---|---|---|
| A1 | `exclusions_applied()` exists, is documented, and is never called | `inventory.py:298`, `recon.py:272` |
| A2 | `dist/`, `build/`, `node_modules/` skipped at any depth | `inventory.py:355` |
| A3 | One NUL byte in the first 8 KiB removes a file from review | `inventory.py:238`, `sweep.py:131` |
| B1 | `\b` cannot match inside `DB_PASSWORD`; JSON's quote breaks the separator | `ledger.py:59` |
| B2 | `excerpt()` truncates, then redacts — a cut token escapes `{32,}` | `ledger.py:117` |
| C1 | `read_bytes()` on a FIFO blocks forever | `inventory.py:284` |
| C2 | `Path.resolve()` raises `RuntimeError` on a loop; `except OSError` misses it | `inventory.py:263` |
| C3 | An unreadable file reaches `_run`'s generic handler as exit 3 | `cli.py:373` |
| C4 | The shipped `log.sensitive` is quadratic; no size or line bound anywhere | `_base.yaml:58` |
| D1 | `is_file()`/`is_dir()` follow symlinks; `ref:` is joined unvalidated | `recon.py:143`, `recon.py:92` |
| E1 | `self_check.py` misses aliased imports, `ast.Name` call forms, `os.system`, `__import__`, f-strings | `self_check.py:62` |
| E2 | No workspace-write check exists, though `README.md:67` says the AST walk enforces one | `self_check.py` |
| E3 | `Bash(uv run:*)` was auto-approved arbitrary execution | `settings.json` |
| E4 | `_write_block` is read-merge-write: not atomic, no lock | `cli.py:229` |
| F1 | `README.md:7` says the catalog, the sweep and `secrev` do not exist | `README.md` |

**A root cause the review did not name.** `pyproject.toml:64-66` keeps ruff's `extend-exclude`
identical to `EXCLUDED_DIRS`, commented "keep the two lists identical so the linter and the scanner
never disagree about scope". They are different questions — what we skip linting *our* code, and
what we skip reviewing *someone else's target*. `dist/` is our build output and their shipped
artifact. A2 breaks the coupling deliberately rather than by accident.

---

- [x] **TASK-M3.5-000 — The brief, the rules, then the marker.** `BRIEF_M3.5.md`; this ledger; an
      M3.5 branch in `scope-guard.sh` permitting `src/`, `patterns/` and `scripts/` and refusing
      `surfaces/` and `threat-models/` **by name**, per the D-1 lesson that a branch answers
      "permit" by silence for any directory it does not mention; assertions in `attack.py`; the
      marker last (H-6).
      *Accept:* M3.5 permits `src/secrev/ledger.py` and refuses `threat-models/`; the AST heuristic
      does not fire on `scripts/self_check.py`, which is M3.5's own subject.

- [x] **TASK-M3.5-001 — B: G-3 actually redacts.** The live secret leak, and therefore first.
      Word boundaries that hold inside `DB_PASSWORD` and `OPENAI_API_KEY`; the JSON form; and
      redaction **before** truncation, with `excerpt()`'s docstring corrected to describe what the
      code does rather than the opposite.
      *Accept:* a table test over every form the review used, each failing before the fix; a
      40-character credential truncated to 20 is still redacted.

      *Done.* Nine tests red first, then green; 381 pass, both gates green. Three things beyond
      what the review named:

      1. **The margin cuts as surely as the cap.** B2 was written against `EXCERPT_LIMIT`, but the
         ±24 margin clips a credential sitting just past it to a handful of characters *before*
         `redact` ever runs — the same defect, reached sooner. Fixed with the cap, red-first test
         each. Both edges are now widened to whole runs before redaction, because a run cut at the
         boundary is one `_LONG_OPAQUE` cannot measure: half a token is not a shorter finding, it
         is no finding.
      2. **`Authorization: Bearer <token>` redacted the word `Bearer` and kept the token.** A third
         cause in the same regex; the scheme is now part of the separator.
      3. **`ledger.py` cited the wrong document.** The excerpt shape was attributed to `STACK.md`
         §5, which says nothing about excerpts — the wording is `BRIEF_M1.md` §5. Corrected here
         rather than deferred to -012, since it sits in the comment block B2 sends you to. This is
         F1's quieter half: a citation nobody can follow is one nobody checks.

      **No amendment was needed and no conflict raised**, which is worth recording because the
      opposite was expected. PRD G-3 says a credential is "redacted in the ledger and report, never
      reproduced" — absolute, and it settles the ordering as compliance rather than preference.
      `BRIEF_M1.md` §5 independently says "redact … before writing it", and the margin and the
      200-char cap both survive unchanged. The documents agreed; only the code disagreed with them.

      **Golden:** `tests/golden/hits.jsonl`, 8 of 35 records, `match_excerpt` the only field
      touched and **no candidate id moved** — asserted mechanically, not by eye. That is the
      property that had to hold: `window_sha256` is hashed unredacted precisely so that tuning
      redaction cannot re-identify candidates and invalidate verifications recorded against them
      (FR-4.6). Every changed line is one boundary that had been sitting inside an identifier —
      `<suppli`→`<supplied`, `ntext`→`context`, `.copy`→`shutil.copy`, `as ha`→`as handle`,
      `user_sup`→`user_supplied_name`, `case`→`case-sensitivity` — and each is strictly more
      readable, which is a side effect rather than the reason.

- [x] **TASK-M3.5-002 — C2, C3: one bad file does not end the review.** A symlink loop and an
      unreadable file are input facts — exit 2 per `STACK.md` §3 — and the rest of the tree is
      still walked.
      *Accept:* both cases complete; the test quotes the exit-code contract; `RuntimeError` is
      caught where `OSError` is.

      *Done.* Six tests red first, then green; 388 pass (was 381), both gates green.

      1. **The review's claim was right and the reason was sharper than reported.** Asked of the
         interpreter rather than taken on trust: a loop raises `RuntimeError("Symlink loop from
         ...")` and `isinstance(that, OSError)` is **False** — the two are unrelated branches of
         the hierarchy, so no widening of `OSError` would ever have caught it.
      2. **The unreadable case was worse than one file.** All three consumers re-read every file
         independently — `sweep.py:134`, `surfaces.py:116`, `recon.py:241` — on top of
         `inventory`'s own read for hashing. So a single `chmod 000` did not cost one file, it
         **ended the sweep of the entire tree**: the reproducing test asserted `[] == ['readable.py']`
         before the fix.
      3. **The flag is carried, not the content.** `BRIEF_M3.5.md` §2 scopes "one read per file,
         carried forward" on `inventory.py`, but that is group D (-008), and holding decoded
         content on every `FileEntry` has a memory cost that wants `--max-file-bytes` (-007)
         decided first. So M3.5-002 adds `FileEntry.is_readable` and one condition at each of the
         three skip sites — no new `try/except` in the consumers, and nothing for -008 to undo.
      4. **`recon.json` gains `unreadable`.** FR-3.8: a file absent from every list in that
         artifact reads as reviewed and clean. The golden gains exactly one line, `"unreadable":
         []` — which asserts nothing on its own, so `test_an_unreadable_file_is_listed_rather_than_omitted`
         is what makes the key real. An empty list is what you get whether the code populates it or
         not, and a golden alone would stay green if the key were deleted and the golden
         regenerated.

      **Diverged from the DoD wording, raised rather than resolved.** Box C2 says a loop *and* an
      unreadable file are exit 2. They got different codes: unreadable → 2 (content that should
      have been reviewed was not, H-1), loop → 0 (recorded as a fact, nothing hidden, and exit 2
      would make any target containing a self-referential symlink report a usage error). "Not exit
      3" and "therefore exit 2" are two claims, and separating the cases showed only the first is
      true of both. **Owner to confirm or reverse.**

      **§3's exit-2 row does not name this case**, listing only "bad arguments, malformed catalog,
      missing target". Read as illustrative rather than exhaustive, on the precedent
      `NormalisationCollision` already set — a `ValueError` so `cli` reports 2, because "the tool
      worked and the target cannot be reviewed as it stands" is a fact about the input. No
      amendment raised; if the owner reads that list as exhaustive instead, this becomes a
      `STACK.md` §3 amendment rather than a code change.

      **Two process faults of mine, both worth the record.** Restructuring a batch to avoid two
      parallel edits in one file, I **dropped the `_file_entry` edit entirely** — `FileEntry` grew
      the field and `_escapes` was fixed while the read stayed unwrapped. The tests caught it
      immediately and named it precisely, which is the whole return on writing them first; without
      them it would have shipped looking complete. Separately, the determinism guard failed
      mid-batch because I ran parallel edits across files that depend on each other and the hook
      fired on a half-changed tree. It passed standalone straight after. Edits that must land
      together should not be parallelised with anything that executes them.

- [x] **TASK-M3.5-003 — A1: exclusions are reported as applied.** The cheapest honest win, because
      the function already exists and is simply not called. `recon.json` reports what was skipped,
      not what could be.
      *Accept:* a tree with `dist/` and one without produce different `recon.json`; the
      `inventory.py` docstring's claim becomes true.

      *Done.* Two tests red first, then green; 390 pass (was 388), both gates green. The cheapest
      task by far — the fix is one call — and the interesting parts are all in the checking.

      1. **A third check found green for the wrong reason.** `test_exclusions_are_recorded_as_applied_not_silently`
         has passed since M1 asserting `"node_modules/" in excluded`. That was true whether or not
         the directory existed, because all fourteen names were listed unconditionally — so it
         asserted the *constant*, not the behaviour, and would have kept passing if the walk had
         stopped excluding anything at all. It is left in place and the new test sits beside it
         naming what it cannot see. That makes three this milestone, after `excerpt()`'s ordering
         argument and `recon.json`'s `unreadable` key.
      2. **What did not change is the verification.** `files_total` stays 30, `loc_total` stays 291.
         Exclusions were always applied; only the report was wrong. A change in either number would
         have meant the fix altered the walk rather than the reporting — a different and far larger
         change wearing this one's clothes.
      3. **A false comment died with it.** `recon.py` carried "Recorded as applied, never silently
         (STACK.md §5)" directly above the line emitting the constant. The comment described §5
         correctly and the code beneath it did the opposite, which is F1's shape exactly: the
         sentence was true of the requirement and false of the ten characters under it.

      **Three things raised rather than folded in** — see the open list below: `exclusions_applied`
      calls `os.walk` with no `onerror`, so an unreadable directory silently under-reports its own
      exclusions (same family as C2); `recon()` now walks the tree twice and the two walks could in
      principle disagree; and the -002 exit-code divergence. Widening a task mid-fix is how a fix
      stops being traceable to the finding it was written for.

- [x] **TASK-M3.5-004 — A3: a NUL byte stops deciding reviewability.** A runnable `install.sh`
      carrying a NUL in a comment yields the same candidate as one without.
      *Accept:* the fixture pair; and the `STACK.md` §5 amendment, if the rule rather than its
      consequence changes.

      *Done.* Three tests red first and two guards green throughout; 395 pass (was 390), both gates
      green, **no golden changed and no fixture reclassified** — which was the design target rather
      than luck, since 5% was placed in the empty band precisely so nothing would move.

      *Measured before anything was proposed*, because the change is a threshold and a threshold
      invented in code is one nobody agreed to (`BRIEF_M3.5.md` §3). Non-text = a C0 control other
      than `\t \n \v \f \r \x1b`, over the first 8 KiB:

      | Input | Non-text | Under the old rule |
      |---|---|---|
      | every text file in `tests/fixtures/` (30 files) | **0.00%** | text |
      | `install.sh` with one NUL hidden in a comment | **3.33%** | **BINARY — the evasion** |
      | `assets/blob.bin`, the committed binary fixture | **8.51%** | binary |
      | `test_surfaces.py:125` blob | 11.76% | binary |
      | `test_sweep.py:261` blob | 15.00% | binary |
      | `test_determinism.py:55` `logo.png` | 27.78% | binary |
      | a real PNG header run | **90.28%** | binary |

      **The threshold is pinned, not free.** `blob.bin` at 8.51% sits above the evasion at 3.33%,
      so the line must fall between them; 10% would reclassify the committed binary fixture and
      churn the recon golden. 5% lands in the gap where nothing lives — no fixture changes, no
      golden churn, and every real text file is four full percentage points clear of it.

      **A prediction of mine that the measurements falsified.** Before measuring I recorded that
      `test_sweep.py:260` and `test_surfaces.py:124` "must flip, and their flipping is the fix" —
      both assert that a mostly-source blob with a few control bytes is correctly dropped from
      review, which looked like the evasion written down as intended behaviour. At 15% and 11.76%
      they sit well above 5% and stay binary, so both pass unchanged and neither was ever the bug.
      Recorded because the claim was already in this ledger before the numbers existed, and a
      prediction quietly dropped once it turns out wrong is the habit this milestone is about.

      **The `STACK.md` §5 amendment went first**, through spec-guard. §5 bound "detected by NUL
      byte in the first 8 KiB" and a brief loses to `STACK.md` on mechanism, so no code could go in
      ahead of it. The PRD was checked and says nothing about binary detection, so §5 is the sole
      binding text and there was no conflict to raise — only an amendment.

      **The suite rejected my first text-control set, which is the second prediction of mine this
      task falsified.** I counted every C0 control below 0x20 as non-text, and
      `tests/test_lines.py` went red on U+001C, U+001D and U+001E — the file, group and record
      separators. `inventory.split_lines` deliberately does *not* break on those, which is already
      a statement that they occur inside real text; had the two disagreed, the line splitter and
      the binary detector would have held different definitions of "text", exactly the drift
      `glob_to_regex` and `language_of` are centralised to prevent.

      **Only the smallest fixture caught it.** `test_the_line_count_is_the_editors` writes six
      bytes, `a<SEP>b\nc\n`, so one separator is 16.7% non-text and the file was called binary,
      returning `loc_total` 0. Its two sibling tests use the same characters in ~33-byte files —
      3%, under the threshold — and passed throughout. The same defect sat in all three and was
      visible in one. **A proportion rule is size-sensitive**, and that is now written into §5 as a
      known edge rather than left to be rediscovered.

      **Re-measured before choosing, again.** The worry was `assets/blob.bin`: 4 non-text bytes in
      47, only 2 of them NULs, so if the other two were separators it would drop to 4.26% and
      reclassify, churning the recon golden. It is
      `b'BLOB\x00\x01\x02binary by content, never by extension\x00\xff\xfe'` — 0x00, 0x01, 0x02 and
      no separators at all — so it holds at 8.51% under both sets. Nothing reclassifies.

      **One correction owed to §5.** The amendment first quoted the evasion as a flat 3.33%; a
      longer script measures 1.75%. Same single NUL, different denominator — the ratio is
      length-dependent. §5 now carries the range, because a binding document quoting one figure no
      reader can reproduce is the same "citation nobody can follow" defect fixed in `ledger.py`
      under -001.

- [x] **TASK-M3.5-005 — A2: the exclusion set is overridable and the coupling is broken.**
      `pyproject.toml`'s comment is corrected: the linter's scope and the scanner's are different
      questions.
      *Accept:* an override sweeps `dist/` and says so in `coverage_gaps`.

      *Done.* 424 pass (was 420), both gates green.

      **I had wrongly called this blocked, and that is the first thing to record.** §5 *directs*
      the coupling fix — "should be broken deliberately" — and §6's open question is only about the
      override *flag*. Where a DoD box and a §6 question disagree, the box is the contract and the
      question is a request to reverse it; that is exactly how C2's exit codes were handled in -002.
      Declaring all three remaining tasks blocked was inconsistent with my own precedent.

      1. **The coupling comment demanded an invariant that was already false.** It asked that the
         two lists be kept "identical so the linter and the scanner never disagree about scope".
         `extend-exclude` held six names; `EXCLUDED_DIRS` holds fourteen. Broken rather than
         repaired, because they answer different questions.
      2. **`coverage_gaps` states the skipped directory**, which is what makes A2's headline true.
         It was previously visible only in `inventory.excluded`, to a reader who thought to compare
         that against a constant elsewhere. The line vanishes under an override.
      3. **Replace, not subtract.** A subtractive flag needs the caller to know all fourteen
         defaults to predict a run; the applied set is reported either way.
      4. **`None`-defaulted, not `EXCLUDED_DIRS`-defaulted.** `sweep`, `surfaces` and `recon` no
         longer import that constant — -003 removed the last import — and a default naming an
         unimported name is a `NameError` at definition time. `inventory` resolves `None`.
      5. **Computed once.** `exclusions_applied` is bound once in `recon()` and used twice, rather
         than adding a third full tree-walk to a function that already walks twice.

      **Five half-landed changes in this task alone, and the pattern is now named:** it happens when
      I split one change across two edits to manage a hazard, then treat the first edit as the whole
      job. The determinism guard caught one directly — `exclusions_applied` given a `None` default
      while its body still read `excluded`, so `name in None` raised. The worst was a docstring
      asserting that a gap line "appears" and "disappears" above a body that returned the same three
      entries as before: a false claim about itself, in the file where -012 had just finished
      removing false claims. What fixed it was not batching less but writing down precisely what
      remained before landing the first half.

      **On discipline, plainly:** A2's first half was red first in -003, where both exclusion tests
      failed against the constant. The override half is new interface, and its four tests passed on
      their first run — the only red available before a flag exists is "unrecognized arguments",
      which proves nothing about behaviour.

- [x] **TASK-M3.5-006 — C1: regular files only.** A FIFO, device or socket is recorded as
      not-a-regular-file rather than read.
      *Accept:* a runtime-built FIFO (committed fixtures cannot carry one); skipped where the
      filesystem refuses it, the `test_determinism.py` precedent.

      *Done.* 398 pass (was 395), both gates green.

      1. **The only finding here that fails silently.** Every other one raises, or returns the
         wrong answer. This one returns nothing at all: no exception, no timeout, just a review
         that never finishes. A target needs one named pipe.
      2. **So it could not be reproduced in the suite.** A red test would have hung pytest with
         nothing to stop it. Reproduced in a bounded scratchpad probe — `walk` on a daemon thread
         with a 5s deadline, abandoned if it never returned — which printed REPRODUCED before the
         fix and the full entry list after. The suite got its assertions only once completion was
         guaranteed, which inverts this milestone's usual order for good reason.
      3. **Before the read, not around it.** `-002` wrapped `read_bytes()` in `except OSError`;
         a blocking open raises nothing, so no `except` clause could ever have reached this. The
         regular-file test has to happen first.
      4. **Three readers, three hangs.** `inventory`, `sweep` and `recon` each read every file
         independently, so each would block on its own and fixing one would leave a review that
         still never finishes — the same structure found in -002, and the reason `-008`'s "one read
         per file" is worth doing.
      5. **A design reversal, stated rather than quietly made.** -002's receipt said this case
         would reuse `is_readable`. That was wrong: "permission denied" and "not a regular file"
         are different facts, and a FIFO reported as unreadable sends a reviewer to check file
         modes that were never the problem. It gets `is_regular`, and the probe output shows the
         distinction holding — the pipe returns `is_readable=True, is_regular=False`.
      6. **`is_file()` rather than `import stat`.** On a path that reaches `_file_entry` symlinks
         are already routed away, so it is exactly `S_ISREG` and it never opens the file. It does
         fold "cannot stat" into "not a regular file"; that conflation is written into the comment
         rather than left for someone to discover.
      7. **`recon.json` gains `not_regular`**, and a behavioural test with it, because the golden's
         `[]` asserts nothing — the fifth time this milestone that a check would have passed for a
         reason unrelated to its claim.

- [x] **TASK-M3.5-007 — C4: input bounds, not a new engine.** `log.sensitive` rewritten to be
      linear with its fixture pair intact; a file-size and line-length bound. Both bounds are
      **mechanism and therefore `STACK.md` §5 amendments raised first** — a limit that exists only
      in code is one nobody agreed to. `catalog.py`'s docstring stops scoping the risk to
      `--catalog`, which the measurements disprove.
      *Accept:* a 1 MB crafted line completes within a stated bound, with a generous margin.

      **Both halves are now done.** DoD box C3 was ticked on the regex work; the bounds followed,
      and the task closes with them. I had called this blocked, wrongly and for the same reason as
      A2: "raised before implementation" *is* the spec-guard amendment, which is exactly how the §5
      binary rule landed in -004. I stopped one step short of a path I had already walked.

      **The measurements changed what the amendment says, and dropped a bound I had myself raised.**
      The earlier cap numbers measured the *quadratic* rule, where a line cap was the only lever.
      With `{0,400}` the catalog is linear in every shape tried — crafted many-line input at
      ~1.7 ms/KiB, a single 4 MB line at the same per-byte cost, ordinary minified source ~25×
      cheaper — so a line-length bound buys nothing a file bound does not, while adding a second
      limit to reason about and a second way to truncate a file silently. §5 now carries the file
      bound and explicitly declines the line bound.

      **5 MiB because the bound's own cost is a coverage gap.** Real source is rarely that large;
      minified bundles can be. A cap tight enough to exclude a genuine bundle would hide exactly the
      shipped artifact `dist/` already tempts a reviewer to skip.

      **Checked before the read**, like the FIFO test above it: `lstat` gives the size without
      opening anything, so an oversized file costs a stat rather than however long reading it would
      have taken — which is the whole point. `size` is real on such an entry and `sha256` is None,
      and the test asserts that pairing, because it is the evidence the order was right.

      **`is_within_size_bound` is a third field**, not a variant of `is_readable` or `is_regular`,
      on the argument -006 made when those two were split: a permission, a kind of file, and a
      threshold are different problems with different remedies. Recorded in `recon.json`'s
      `too_large`, never silent — a size cap that quietly dropped a file would recreate precisely
      the evasion A3 and C1 closed.

      **Validation lives in argparse's `type=` callable**, so argparse raises and exits 2 itself.
      One exit-2 mechanism rather than two that could drift apart — and it removed the seventh
      `return` that ruff flagged in `main`, which a `noqa` would have buried.

      *Done:* 400 pass (was 398), both gates green. Suite runtime 1.29s → 3.09s, which is the
      1.2 MB timing assertion and is a real cost paid deliberately.

      1. **My first measurement was a false negative, and it nearly closed the finding.** probe_c4
         reported clean linear growth — 10x input for 10x time — and on that evidence I would have
         recorded the review's "quadratic" claim as unreproduced. The reasoning that saved it:
         `[^)\n]*` has no nested quantifier, so the *inner* scan really is linear; the blowup is
         the **outer** scan, since `re.search` retries the whole pattern from every position and my
         line contained `print` exactly once. The adversary is `"print(" * K` — many matching
         starts, no `)` to stop consumption, and `(` is not excluded.
      2. **Corrected, it reproduces decisively.** Doubling ratios converge on 4.0; 185.72 ms at
         9,600 bytes, 11.4 s at 76,800, ~48 minutes extrapolated to 1 MB.
      3. **Two repairs measured and rejected, both for recall.** `[^()\n]*` is linear and agrees
         with all seven shipped fixtures and loses *every* nested call — `print(sanitize(password))`
         is probably the commonest real spelling, since a credential reaching a log call has
         usually been passed through something. The fixtures were not the control here, which is
         why `test_log_sensitive_still_sees_a_credential_inside_a_nested_call` now exists.
         `[^)\n]*+` is worse: a possessive quantifier never gives back, so it swallows the keyword
         and breaks two shipped positives, while staying O(N^2) anyway.
      4. **`{0,400}` adopted.** Linear, keeps every fixture and both nested-call cases. 400 rather
         than 120 or 200 because those were measured losing a keyword 150 and 300 characters into a
         call. Residue stated: beyond 400 characters in one call, unseen.
      5. **`catalog_version` bumped**, and the loader refused the half-change — "one run has one
         catalog_version" — so the version belongs to the catalog rather than a pack. A check doing
         its job, and independent confirmation that FR-4.6 semantics are structural here. Golden:
         35 records, `catalog_version` the only field touched, **zero ids moved**.
      6. **`catalog.py` was wrong in both directions.** It named nested quantifiers as the
         precondition (wrong mechanism — which is why reading the shipped pack never caught this)
         and scoped the exposure to `--catalog` users (wrong scope — the quadratic pattern was the
         one we ship).

      **Three probe-engineering errors of mine**, all in one afternoon and all worth the record:
      abandoned CPU-bound threads that compounded and contaminated later trials, where the FIFO
      probe had got away with it only because its stranded thread blocked on I/O; no `flush`, so a
      killed run lost results it had already computed; and re-measuring the known-quadratic variant
      at a *larger* size, which is what consumed the budget. The runaway task was stopped rather
      than left burning the machine.

- [x] **TASK-M3.5-008 — D1: the tool reads nothing outside the target.** No `is_file()`/`is_dir()`
      through a symlink; a `ref:` containing `..` refused.
      *Accept:* a fixture with `pyproject.toml`, `package.json`, `.git` and `.git/HEAD` all
      symlinked outside.

      *Done.* Five tests red first, then green; 405 pass (was 400), both gates green, **no golden
      churn** — the fixture tree has no root manifests and no `.git`, so tightening these four
      sites changes nothing the tool produces.

      1. **The breach published what it read.** Not "could touch a foreign file": the manifests
         copied another file's entry points into `recon.json` (`['leaked = private.cli:main']`,
         `['leaked = ./private.js']`), and the three git cases reported another repository's SHA as
         this target's version. `STACK.md` §6 makes that version a workspace directory, so one
         tree's review would be filed under another's history, and nothing in the artifact would
         say so.
      2. **Containment failed exactly where the walk was not doing the work.** `inventory.walk`
         has never followed a symlink. All four breaches are files `recon.py` reaches for *by
         name* — `pyproject.toml`, `package.json`, `.git`, `.git/HEAD` — and `is_file()`/`is_dir()`
         both follow. The rule held for every file the tool discovered and failed for every file it
         went looking for.
      3. **The `ref:` case needs no symlink.** The target writes `ref: ../../escape` in its own
         HEAD and the path was joined verbatim. `path.traversal` is one of the nine rules this tool
         ships, so being subject to it is the AC-10 self-application failure, not merely a bug.
      4. **Checked as a string, deliberately not with `resolve()`.** `resolve()` follows symlinks,
         which is the thing being defended against, and -002 established it raises `RuntimeError`
         on a loop. A containment check that can be hung by the tree it is containing is not a
         check.

      **A test-design trap caught at authoring time rather than after.** The three git tests use
      40 characters of `a`, `b` and `c` as fake SHAs — all hex digits, so
      `re.fullmatch(r"[0-9a-f]{40}")` accepts them. With a non-hex filler `git_identity` would have
      returned `("directory", None)` for the wrong reason and all three would have passed against
      the unfixed code. That is the sixth instance this milestone of a check that would have been
      green without testing its claim; the first one noticed before it was written rather than
      after.

      **My own slip, the second of this kind.** I fixed `pyproject.toml` and left `package.json`
      untouched in the same batch — the same omission as dropping `_file_entry` in -002 when
      restructuring to avoid parallel same-file edits. The red test named it immediately, which is
      what red-first is for; without it the task would have looked finished with half the manifest
      surface still open.

- [x] **TASK-M3.5-009 — E1, E2: `self_check.py` stops being a denylist.** This is P3 turned on the
      project's own gate, and the founding finding was a denylist bypass. Either the workspace-write
      check exists or the README stops claiming it — the two disagreeing is what is not allowed.
      *Accept:* a fixture carrying all nine bypasses exits 1, and is asserted to have exited 0
      before the fix.

      *Done.* Twelve tests, ten red first; 417 pass (was 405), both gates green.

      1. **The gate enforcing §2.1 had never been tested.** `tests/test_self_check.py` did not
         exist. The script has been in `check.sh` since M0, and nothing had ever tried to defeat
         it — H-8 says that makes it an assumption, not a control.
      2. **It could not test itself even in principle.** The scan root was hard-coded to
         `src/secrev`, so the only thing it could ever be pointed at was code that already passed
         it. A `scan(root)` seam was split out of `main` before any fix, purely to make the red
         observable. The fixture cannot live in `tests/fixtures/` — everything there is swept by
         the golden tests — so it is built in a temporary directory, which is why a path argument
         exists at all.
      3. **All nine exited 0 with empty output.** Not a wrong answer: no answer, on a file
         containing `os.system` and `__import__`.
      4. **Five of nine shared one cause** — testing the spelling rather than resolving the name —
         and are closed by one alias map. Three were absent entries; one was an `ast.JoinedStr`.
      5. **The control caught my over-correction, one round after I wrote the hazard into its own
         docstring.** My first repair demanded a literal list as `subprocess`'s first argument and
         flagged `subprocess.run(argv)` — the correct form. Had it shipped, the gate would fail on
         good code, and the usual response to that is deleting the rule. The check now flags what
         is *certainly* a string, and the residue is written down: a string built by concatenation,
         `%`, `.format()` or `.join()` is not recognised.
      6. **E2: the claim is dropped, not the check built.** `cli.py` writes by design, and
         inside-versus-outside the workspace is dataflow rather than a name test. The README now
         says so and names the structural property instead.

      **The self-application guard blocked one of my own edits**, refusing a docstring that named a
      banned construct while explaining the checker that forbids it. A true positive for the guard's
      design and a false positive for the change — the prose-versus-code discrimination `skill.md`
      records from the M2 case, now landing on our own harness. Rewording was the right response
      rather than weakening the guard, and it produced a better comment. Recorded as an observation,
      not a defect.

      **Raised here, and closed in -013.** `mypy`'s `files` was `["src/secrev"]`, so `scripts/`
      was type-checked by nothing at all — not by the product gate, and not by the harness gate,
      whose `mypy --strict` covers `.claude/` and `tests/harness/`. A gate script carrying an alias
      map, a resolver and real branching with no type checking is the same gap as one with no
      tests, one layer along.

      **Closing it required no code changes.** Adding `scripts` to `files` gave "no issues found in
      16 source files" on the first run: all five scripts were already fully annotated, and only
      the enforcement was missing. That inverts this milestone's recurring finding — eight times
      the claim outran the code, and here the code outran the claim, which is exactly why nobody
      noticed the check was absent. `scripts/` is now type-checked on every push.

      **Still candidate later work:** the narrowed workspace-write check (writes confined to
      `cli.py`), which `-009` chose not to build because deciding whether a write lands inside the
      workspace is a dataflow question rather than a name test.

- [x] **TASK-M3.5-010 — E3: the allowlist is asserted.** `attack.py` already parses
      `settings.json` for the hook check and never looks at what is auto-approved — which is how
      `Bash(find:*)` and `Bash(uv run:*)` both arrived. No auto-approved rule may grant arbitrary
      execution.
      *Accept:* H-8 — add one back, watch it fail. Also settle `Bash(head:*)` against
      `deny Read(**/.env)`.

      **Now ticked.** `Bash(sh .claude/hooks/*)` was removed, which was the one rule making DoD box
      E3's first clause false — prefix matching meant anything after it ran unattended. Removed on
      the `-000` precedent for `Bash(uv run:*)`: the cost is a narrow convenience, and neither
      `sh .claude/check.sh` nor `sh scripts/check.sh` matches that prefix. The pin in `attack.py`
      was updated in the same breath, and the harness gate confirms the two agree.

      **I had called this blocked, wrongly, for the same reason as A2.** The box requires that no
      auto-approved rule grant arbitrary execution; one did; removing it is within the DoD, not a
      change to the owner's posture that needed asking. What genuinely remains yours is the pair
      below, and neither blocks the box because neither grants *command* execution.

      *Done.* 120 guard assertions (was 118), harness gate green.

      1. **The gap was not a missing parser but one aimed at the wrong half of the file.**
         `test_bash_guard_is_wired` has opened `settings.json` since M0 and reads only
         `hooks.PreToolUse`. `permissions.allow` — the array that decides what runs unattended —
         was never read by anything. That is how two execution grants arrived in silence.
      2. **Pinned, not pattern-matched**, following the C-1 ruling for question ids: discovery in
         code, the pin in data. A rule that tried to *recognise* arbitrary execution would be a
         denylist over command shapes (P3) and would have to be right about every shell in advance.
         A pin only has to be noticed, and every addition now costs a deliberate edit.
      3. **The deny list is pinned too.** A deny rule removed is quieter than an allow rule added:
         nothing fails, a refusal simply stops happening.
      4. **H-8 performed, not asserted.** With a probe rule added, exactly 1 of 120 failed and the
         message named `['Bash(secrev-h8-probe:*)']` — not merely "the set changed", which would be
         half a control. The deny pin stayed green, so the failure was scoped to what changed. The
         probe was inert by construction (a command that does not exist) so that a failure to
         restore could grant nothing; it was removed, and `git diff` confirms `settings.json` now
         differs from HEAD by one line only.

      **Three contradictions found, none fixed unilaterally — owner to settle:**

      - **`Bash(sh .claude/hooks/*)` is arbitrary execution.** Matchers are prefix-based, so
        anything after that prefix rides along. This alone makes DoD E3's first clause false.
      - **`deny Read(**/.env)` is defeated by four allow rules** — `head:*`, `diff:*`, `wc:*`,
        `ls:*` all read it through Bash. A deny that four allows walk around is the same "two
        disagreeing" state E2 refused, in the permission set instead of the README. Either the
        readers go or the deny should stop claiming to protect anything.
      - **`Bash(uv sync:*)` executes third-party build hooks**, which is code execution, and
        `STACK.md` §3 says nothing may depend on `uv`.

      Not decided here because it is your permission set and the readers are daily conveniences; a
      gate reddened by my choice is a gate someone edits back. `Bash(uv run:*)` was different —
      removing it in -000 cost nothing.

- [x] **TASK-M3.5-011 — E4: the ledger write is atomic, and the workspace is `0o700`.** Temp file
      plus `os.replace`. The workspace holds excerpts that may carry secrets.
      *Accept:* an interrupted write leaves the previous ledger intact and readable.

      *Done.* Three tests, two red first; 420 pass (was 417), both gates green.

      1. **Three non-atomic writes, not one** — `_write_block`, `write_run_json`, `_emit`. The
         third time this milestone that one defect lived in every place doing the same thing, after
         -002's three readers and -008's four reach-by-name sites. Fixing only the site the DoD
         named would have left two of them.
      2. **Refusing before writing was only half the property.** `merge_ledger` declines to touch a
         ledger it cannot *read*; nothing protected one it could. And that is the file where the
         other source's block is preserved byte for byte — so a failure writing the pattern block
         destroyed the surface block, silently.
      3. **The temp file goes in the destination directory**, because `os.replace` is atomic only
         within one filesystem; a temp under `/tmp` degrades to a copy across a mount boundary and
         nothing announces it. `NamedTemporaryFile` creates at 0o600, so artifacts inherit a
         private mode rather than the umask's, which matches the workspace's 0o700.
      4. **The mode was worse than reported: 0o775, not 0o755.** Umask 002 here, so the workspace
         was group-writable too.
      5. **Both obvious spellings of the mode fix look right and are not.**
         `mkdir(parents=True, mode=0o700)` applies the mode to the final directory only, leaving
         `~/.security-review/` at the default; `exist_ok=True` leaves an existing directory's mode
         untouched, which is every run after the first. Every level is set explicitly.
      6. **The walk goes down from the base, not up from the leaf** (after ruff flagged the
         upward form). It terminates by construction, needs no filesystem-root guard, and fails
         loudly through `relative_to` if the base is not an ancestor — where the upward walk would
         quietly chmod its way toward `/`.
      7. **`os.replace` kept over `Path.replace`** with a justified suppression: it is the atomic
         primitive and reads as one where atomicity is the whole point, and it is the seam the
         interruption test patches. Routing through `Path.replace` would make that test depend on
         which primitive pathlib happens to call internally — a test passing for a reason no longer
         stated, which is this milestone's recurring failure mode.

      **`test_a_failed_write_leaves_no_temporary_file` was green before and after**, as intended: a
      guard for the new mechanism rather than a reproduction. And the determinism stage is what
      confirms the rest — every artifact now reaches disk through a temp file and a rename, and not
      one byte that lands there changed.

- [x] **TASK-M3.5-012 — F1: the documents stop claiming what the code does not do.** The README
      status block and its AST claim; `inventory.py`'s "recorded as applied"; `excerpt()`'s ordering
      argument; `catalog.py`'s ReDoS scoping. Several land earlier as part of their own task; this
      is the sweep that checks none was missed.
      *Accept:* each claim quoted and shown true, or gone.

      *Done.* 420 tests, 120 guard assertions, both gates green.

      **The five named items.** `excerpt()`'s ordering argument (-001), `catalog.py`'s ReDoS
      scoping (-007), the README AST claim (-009), and `inventory.py`'s "recorded as applied" —
      which needed no edit, because -003 wiring `exclusions_applied` into `recon.py` made the
      existing sentence true. The README status block was corrected here.

      **Three the brief did not name.** Working only from its list would have defeated the point of
      having a sweep at all:

      1. **`ledger.py` cited the wrong document** — the excerpt shape attributed to `STACK.md` §5,
         which says nothing whatever about excerpts; the wording is `BRIEF_M1.md` §5. Found in
         -001. A wrong number gets caught by the next person who checks; a wrong *attribution* gets
         caught by nobody, because following it costs more than trusting it.
      2. **`CLAUDE.md:14` said M3 was "complete in work on `m3/overlays`, unpushed"** after PR #14
         had merged it. The worst placement a false claim can have — that file loads into every
         session, so it misdirects every future decision from the first token.
      3. **`CLAUDE.md:285` presented `self_check.py` as "AST-based on purpose"**, contrasting it
         with grep. Literally true, and exactly the property that made the checker look sound while
         it passed nine bypasses.

      **The third is worth separating out.** F1 is written about text claiming coverage the code
      does not provide. That sentence claimed a technique the code really did use — it was
      *incomplete*, not false, and phrased so a reader would stop asking. Corrected on the same
      grounds, because the effect is identical and only the mechanism differs.

      **Clean sweeps are results too (P6).** `STACK.md` carries no enforcement claims of that
      shape. `CONTRIBUTING.md`'s single assertion claim — "writing across it is not, and an
      assertion enforces it" — is true, backed by
      `test_the_product_gate_does_not_reach_into_the_harness` in the guard listing. Recorded
      because "I looked and found nothing" and "I did not look" are the two states this whole
      milestone exists to keep apart.

- [x] **TASK-M3.5-013 — Close.** DoD ticked; amendments through spec-guard; receipts. The marker
      moves only after `BRIEF_M4.md` and its scope-guard rules exist.

      *Done.* All fifteen Definition-of-done boxes ticked. 439 tests (from 372 at M3's close), 120
      guard assertions (from 118), mypy across 16 source files (from 11), determinism
      byte-identical with ids stable, self-application clean, gitleaks clean, both gates green.

      **Closing requires grepping this file and the brief for `- [ ]`, and that is a step rather
      than a courtesy.** `test_the_marker_may_not_pass_a_brief_with_open_boxes` inspects only
      briefs *below* the marker — and it must, because a milestone in progress legitimately has
      open boxes. So the current milestone's own completeness is the one thing no assertion can
      check, and it falls entirely to this procedure.

      It caught a real miss on the first run: `TASK-M3.5-010` was still `- [ ]` while its body read
      "**Now ticked.**" — the file contradicting itself, and "13/13 tasks" claimed several times on
      the strength of it. The cause is the pattern recorded six times already in this ledger: I
      edited the substance and left the marker. Ninth instance, and the first found by a check
      written for exactly that purpose rather than by a test going red.

      **Counting the boxes then falsified the claim a second way: there are fourteen tasks, not
      thirteen.** `-000` through `-013` inclusive, and the grep returns fourteen `- [x]`. So every
      "13/13" in this session was wrong twice — about the denominator as well as the tick. A number
      repeated confidently and never counted is the same failure as a comment describing code it
      sits above, and it survived precisely because repeating it felt like verifying it.

      **Two `STACK.md` §5 amendments, both through spec-guard, both measured before proposed.**
      Binary became a proportion rather than a single NUL; and a file-size bound was added while
      the line-length bound — which I had raised myself — was **withdrawn on the evidence**, since
      one enormous line costs no more per byte than many small ones once `log.sensitive` is linear.

      **The marker stays at `M3.5`.** Moving it before `BRIEF_M4.md` and its scope-guard rules
      exist write-locks the scoped tree with no rules to permit anything (H-6) — the failure this
      file records from M1's close.

      **What the milestone actually produced, beyond the fixes.** Eight checks were found green for
      a reason unrelated to their claim: `excerpt()`'s truncation test passing on a 400-character
      run; two `[]` golden fields asserting nothing; the exclusions test asserting a constant;
      `test_sweep.py`'s "binary" blob; the three D1 git tests, which needed hex filler to fail at
      all; `self_check.py` having no tests since M0; and the `os.replace` seam. The thesis of this
      milestone applied to our own suite more than to the tool.

      **Three things remain open, all owner decisions:** `deny Read(**/.env)` defeated by four
      allowlisted readers, one auto-approved `uv` subcommand running third-party build hooks, and
      PRD §13 still without a row for M3.5.

## Open, for the owner — raised in `BRIEF_M3.5.md` §6

- **PRD §13 needs an M3.5 row — added in -013**, between M3 and M4, through spec-guard. Inserting
  a row rather than renumbering M4–M12 keeps every existing reference in the PRD, the briefs and
  the receipts true. The omission was never a decision: the owner created M3.5, and §13 simply had
  not caught up.
- **Is a NUL byte still the binary test**, or only no longer decisive? Either way a §5 amendment.
- **`--max-file-bytes` and a line-length bound** are new mechanism, for §5 before code.
- **Does the exclusion override belong here at all?** It adds interface, which could be argued into
  M7's contract freeze — against which A1 would report a gap nobody can close.

Raised during the work, not from the review:

- **Do a symlink loop and an unreadable file deserve the same exit code?** DoD box C2 says both are
  exit 2. Implemented as unreadable → 2 and loop → 0, because separating the cases showed "not exit
  3" and "therefore exit 2" are two different claims: content that should have been reviewed was
  not, versus a fact fully recorded with nothing hidden. Exit 2 for a loop would make any target
  containing a self-referential symlink report a usage error. **Owner to confirm or reverse**, and
  if §3's exit-2 list is meant as exhaustive rather than illustrative this becomes a `STACK.md` §3
  amendment instead of a code change (TASK-M3.5-002).
- **`exclusions_applied` cannot see what it cannot read.** It calls `os.walk(root)` with no
  `onerror`, and `os.walk` swallows errors silently by default — so an unreadable directory
  under-reports its own exclusions, and the field M3.5-003 just made honest goes quiet again in
  exactly the case C2 is about. Same family as C2, found while fixing A1 and deliberately **not**
  folded into it, since widening a task mid-fix is how a fix stops being traceable to its finding.
  Candidate work for -006, which is already in the walk.
- **`recon()` now walks the tree twice** — once in `walk()` and once in `exclusions_applied()` — and
  the two could in principle disagree, since only the first refuses to follow symlinked directories.
  The single-walk version wants `walk()` to return what it pruned, which changes its signature and
  every caller. Left alone because -003 is scoped as "the function exists and is not called", and
  because -008's "one read per file, carried forward" is the change that would naturally absorb it.
- **Three auto-approved rules — all now settled (TASK-M3.5-010), none of them by leaving them.**
  Each was raised here first and then removed, on the precedent `Bash(uv run:*)` set in -000.
  Reversing any of them is one line, and `test_the_auto_approved_allowlist_is_pinned` makes the
  reversal visible rather than silent.
  - `Bash(sh .claude/hooks/*)` — **removed.** Matchers are prefix-based, so anything after that
    prefix ran unattended. It was what made DoD box E3's first clause false.
  - `Bash(head:*)`, `diff:*`, `wc:*`, `ls:*` — **removed**, settling the question -010's accept
    line names. Each reads a file's contents to stdout, so each defeated `deny Read(**/.env)`
    through Bash while it refused the `Read` tool. A deny that four allow rules walk around is
    worse than no deny, because it reads as protection — the state E2 refused in the README,
    reproduced in the permission set. They still run; they ask first. `sha256sum` and `shasum` stay
    (a digest is not the file), and `git diff` is allowlisted separately.
  - `Bash(uv sync:*)` — **removed.** It resolves and installs dependencies, and build hooks are
    third-party code execution, against a `STACK.md` §3 that permits `uv` but says nothing may
    depend on it. `uv python` stays: installing an interpreter is a different act.
- **The licence allowlist read `;` and `,` as disjunctions — fixed in -013.** Found while writing
  the first tests `scripts/license_check.py` had ever had. `_normalise` split `" OR "`, `";"` and
  `","` identically into one flat list, and the caller accepted when **any** candidate was in
  `ALLOWED` — so `"MIT, GPL-3.0"` passed on the strength of MIT alone. Right for a genuine SPDX
  `OR`, where the licensee chooses; wrong for the multiple trove classifiers `pip-licenses` joins
  with `;`, which all apply. A check admitting exactly what it exists to refuse, with every gate
  run green.
  `_normalise` now returns groups of alternatives — each group must be satisfied, one alternative
  within a group suffices — and the decision moved into `is_allowed`, which nothing could reach
  while it was inline in a function that shells out to `pip-licenses`.
  **The trap in the change, guarded explicitly:** `any([])` is `False` but `all([])` is `True`, so
  flipping the operator would have turned "no licence declared" into "acceptable" inside a change
  that reads as tightening. Pinned by
  `test_an_empty_licence_field_yields_no_candidates_and_is_refused`, which was green before *and*
  after — the only shape of test that can catch a regression introduced by a stricter rule.
  **Measured before it shipped:** the real dependency set still reports "13 dependencies, every
  licence allowed", so nothing was passing on a permissive branch. Had one failed, that would have
  been a finding about our dependencies rather than a reason to revert.

## The second review, 2026-09-17 — five boxes were closed on the demonstrated case

A second external review ran the tool from `pr15`, replayed the original attack trees (all now
refused), then varied them. Seven findings, and **one shape underneath five of them**: M3.5 fixed
the site that had been demonstrated rather than the class that produced it. One pattern of four,
four reach-by-name sites of nine, four permission rules of six, nine bypass spellings of twenty,
one of four ways a file goes unread. Each box then recorded the demonstrated case as evidence, so
each read as closed.

DoD boxes **A3, C3, D1, E1 and E3 were unticked** and re-closed against the class. The owner asked
for two (C3, D1); the other three are the same state and are raised here rather than left ticked.

- **C3 — four patterns were quadratic, not one.** `net.fetch_exec`, `deser.unsafe`,
  `exec.shell_true` and `path.traversal` all carry an unbounded `[^x]*` reachable from a repeatable
  start. Under `finditer`, which is what `sweep.py:78` uses: 0.164 s at 20 KB and 0.618 s at 40 KB
  for `net.fetch_exec`. All four now carry `{0,400}`; re-measured at 1.9–2.1x for 2x input, and
  `net.fetch_exec` fell from 0.618 s to 0.014 s.
  **The C3 check measured with `re.search`, which returns at the first match.** `deser.unsafe`
  measured 0.000 s under it and 0.692 s under `finditer` — the check modelled the cheap call.
  Replaced by `tests/test_catalog_timing.py`, over every pattern *and* every surface kind, with a
  seed-coverage assertion so a rule added without a timing seed turns it red.
  **Two of the four were not in the review either**, and were found by measuring the whole catalog
  rather than the two reported.
- **D1 — five more reach-by-name sites**, one of them (`dependabot`) not in the review and one
  (`_SAST_CONFIG`) found while fixing the others. `SECURITY.md`, `dependabot.yml`/`.yaml` and the
  SAST configs used a bare `is_file()`, which follows a link; `.github/workflows` used `glob`,
  which follows a linked directory; `_resolve_ref` tested `is_symlink()` on the finished path,
  which lstats the last component only, so `.git/refs -> ../../outside` reported a foreign SHA.
  **Fixed structurally, not per site.** Those fields now come from `_found_paths`, the set the walk
  actually found, so containment is inherited rather than remembered. `.git` is excluded from the
  walk, so it gets `_within_real_path`, which checks every component.
- **A3 — one NUL byte no longer hides a file; eight still did.** The threshold was measured against
  the fixtures, but the attacker picks the ratio: 8 NULs in a 59-byte script is 12%. Padding past
  `--max-file-bytes` does the same. Both returned `0 candidates, exit 0`, and `coverage_gaps` read
  `no coverage for: markdown` — naming the one harmless file and omitting the script carrying
  `curl | sh`.
  **Refined from the review's literal proposal, deliberately.** It asked for exit 2 on `binary` and
  `too_large` alike; every ordinary target holds binary assets, so that lights the signal on nearly
  every run, and an exit code that is always on is H-1's habit in a new place. The exit now keys on
  `unread_code` — unread files whose *extension* says code — and every unread bucket gets a
  `coverage_gaps` line regardless, capped at five with a pointer to the inventory field.
- **E1 — eleven more bypasses**, including `yaml.load_all` and `yaml.unsafe_load_all`, which
  contradict "safe_load only" as directly as the three that were listed. Imports and `yaml` members
  are now **allowlists**; the `os` table stays a denylist and says so where it is defined.
  **An over-reach was caught by the suite's own control.** The first allowlist omitted the process
  module, which reads as free strictness since `src/secrev` imports none — but `STACK.md` §2.1
  forbids a shell *string*, not the module, and `test_clean_source_still_passes` went red. Holding
  the package to importing none is a `STACK.md` amendment and is raised, not taken here.
- **E3 — `git diff --no-index /dev/null .env` prints the file**, so the rule survived the removal of
  the four that did the same. Demonstrated, not argued. Removed rather than narrowed: matchers are
  prefix-based, and enumerating the flags that turn a diff into a read is a denylist over flags.
  `Bash(pytest:*)` and `Bash(python3 -m pytest:*)` went with it — pytest runs whatever is in
  `tests/`, `conftest.py` included, and `tests/` is not protected, so between them they were
  arbitrary execution approved unattended.
- **G-3 leaked four more shapes.** URL userinfo (`scheme://user:pass@host`) matches neither rule —
  no credential word, and a password is rarely 32 characters. `PGPASS` and `private_key` named a
  credential and were not on the word list. A quoted value was cut at the first space.
  **One of them only appeared to pass**: `passphrase=correct-horse-battery` was redacted by the
  long-opaque rule because `=` is inside its alphabet and the string reached exactly 32 characters.
  One character shorter and it leaked. `tests/test_ledger.py`, which did not exist, now pins the
  short case.
- **"One read per file, carried forward" overstates, and the review's wording overstates back.**
  Both consumers *do* honour every flag the walk set before reading — the protections are there.
  What is not carried forward is the read: there are two, so a file replaced between them is a real
  TOCTOU window. Recorded at all three sites. **Not fixed**: a single read means the bytes travel on
  the entry, which holds a tree in memory, and wrapping the second read in a silent skip would
  create an unreported gap — P4's "silence is not an outcome" inside a change that reads as
  hardening. Raised as an architecture question.

**Three errors of mine during this pass, recorded because the pattern matters.** The first ReDoS
probe used `re.search` and reported `deser.unsafe` as unreproduced — the same false negative the C4
probe made in M3.5, repeated after the file documenting it had been read. Two changes half-landed:
`_entrypoints` gained a `found` parameter in its body but not its signature, and the call site was
updated before the variable existed. Writing the parts down first is not enough; they have to be
checked against what actually landed.

## The third review, 2026-09-17 — the cost moved, it did not leave

A third external review ran the tool from `3906c51`, replayed every attack tree
from both previous rounds — all refused — and then varied them again. Five
findings. The headline one is that **C3's guarantee was false for a third time,
by a route neither previous fix could have covered**.

- **ReDoS, through identity rather than through regex.** Every pattern is linear
  and `secrev sweep` was still quadratic: 0.37 s, 1.17 s, 4.06 s at 40/80/160 KB,
  about 3.5x per doubling. The cost had moved out of `patterns/` entirely.
  Each candidate's window is ±20 lines, which on a file that is one enormous
  line is approximately the whole line, and that window was **rebuilt once per
  match and then hashed twice** — `window()` in the source, `window_sha256` for
  the ordinal's group key, and `window_sha256` again inside `derive`. Three
  passes over ~N characters, K times.
  Fixed by sharing one window object per line across the matches on it and
  hashing it once. Measured after: 0.13 s, 0.25 s, 0.50 s — a flat 2.0x, and
  160 KB fell from 4.06 s to 0.50 s. **No id moved**, because the bytes fed to
  SHA-256 are the same four components in the same order; only the number of
  times they are computed changed. `derive()` keeps its signature — it is the
  `STACK.md` §5 identity contract — and delegates to `_id_from_digest`.
  **`test_catalog_timing.py` could not have caught this and still cannot**: it
  times regexes. A second test now times `sweep()` itself and asserts the
  *ratio*, because a ceiling in seconds passes on a fast runner while the curve
  is still quadratic — which is how the previous check stayed green through
  exactly this defect.
  The reviewer named two of the three passes; the `window()` rebuild was found
  by reading the call site rather than from the report.
- **A file with no code extension still hid at exit 0.** `unread_code` keyed on
  the extension, so `install` with a shebang and eight NULs, and a `SKILL.md`
  with a NUL inside an HTML comment, were both classified binary and reported
  clean. The second is the sharper case: the instruction layer is this tool's
  own subject (P8), and `markdown` sits in `_NOT_CODE`.
  `_is_code` now asks three questions — extension, shebang, artifact name.
  `has_shebang` is set from bytes `_file_entry` had already read to answer
  `is_binary`, so it costs a slice rather than an open. **An oversized file is
  still judged by its name alone**, because reading two bytes there means
  opening a file the size bound exists to leave shut, and that is the TOCTOU
  window this milestone spent its effort documenting.
- **The `.env` deny was walked around by two more git subcommands.**
  `git add -f .env && git show :.env` reads the blob back out of the index;
  `git blame --contents .env README.md` reads the named file for its content.
  Both reproduced, both exit 0 with the value on stdout, both auto-approved.
  Removed. What stays is inspection that reports *about* history — `log`,
  `shortlog`, `rev-parse`, `rev-list`, `remote`, `status`, `branch` — rather
  than anything that can be pointed at a working-tree path and made to emit it.
  **Three rounds, three removals, one class.** It was named correctly the first
  time ("a command that can print a file's contents defeats a Read deny") and
  answered each time by removing the commands that had been *demonstrated*.
- **`self_check.py`: four more, and the `os` table finally inverted.** A
  wildcard import binds every name while naming none; a subscripted callee
  (`sys.modules["os"].system`, `os.__dict__["system"]`) leaves no dotted name to
  match; and `subprocess.Popen(["/bin/sh", "-c", cmd])` is a shell string
  wearing the argument list that every other check asks for.
  The `os` denylist became `ALLOWED_OS_ATTRS` — the package calls exactly
  `os.replace` and `os.walk`. The comment that table carried had said, for two
  milestones, that it could not be enumerated with confidence and should not
  read as closed. It was right both times and stayed a denylist anyway.
- **G-3 leaked four more shapes**: URL userinfo with no username, `--password X`
  and `-p X` (a space-separated CLI flag, which has no separator character for
  the key rule to anchor on), `pwd=` and `MYSQL_ROOT_PW=`. All redacted, with
  three over-redaction controls — `--port 8080`, a plain URL, and prose — held
  green on both sides of the change.

**Two rules of mine failed on good code during this pass, and both were caught
by controls rather than by review.** The import allowlist omitted `subprocess`,
which reads as free strictness since `src/secrev` imports none — but §2.1
forbids a shell *string*, not the module, and `test_clean_source_still_passes`
went red. Then "any subscripted callee" flagged four sites in this package,
three of them *slices* (`text[5:].strip()`), where no member is named at all;
the rule is now limited to namespaces that hold callables, and
`test_ordinary_subscripting_is_not_a_namespace_lookup` is written from the four
real lines rather than from invented ones.

**Raised, not closed:**

- **Ledger flooding is M7's.** A 5 MB crafted file produces roughly 500,000
  records, every one of which P4 requires be resolved. Linear time does not make
  that reviewable, and triage is where it belongs.
- **Whether `src/secrev` should be *held* to importing no process module** is a
  `STACK.md` §2.1 amendment, not a script edit. Removing `subprocess` from
  `ALLOWED_IMPORTS` would enforce something stricter than the binding document
  and would fail the control test above on correct code.
- **Redaction's remaining tail** — `Cookie: session=`, and any key naming a
  credential in a vocabulary the list does not carry — is the structural limit
  of redacting by key name, stated rather than chased.

## The fourth review, 2026-09-18 — a commit message claimed a fix that did not exist

Two findings. The first is the worst shape available to this project, because the false statement
was in the previous commit's own message.

- **`pwd=` and `MYSQL_ROOT_PW=` leaked, and the commit message said they were fixed.** `pwd` had
  been added only to `_CLI_CREDENTIAL`, the space-separated flag form (`--pwd X`); `pw` was never
  added at all. Neither reached `_SECRET_ASSIGNMENT`'s key list, so `pwd="…"` and `MYSQL_ROOT_PW=…`
  went through untouched.
  **The probe that cleared them failed by the coincidence this repository had already documented and
  named.** It used a 28-character value, and `=` is inside `_LONG_OPAQUE`'s alphabet, so
  `pwd=<28 chars>` reached exactly 32 characters and the *generic* rule caught it. That is the same
  accident as `passphrase=correct-horse-battery` two reviews earlier — the one
  `test_a_short_passphrase_is_redacted_by_the_key_rule_not_by_luck` exists to pin, in the very
  module the probe was exercising. A green check whose greenness comes from somewhere other than its
  subject is the F-class, and this time it produced a false claim in permanent history.
  Fixed by adding `pwd` and `pw` to the key alternation, with tests naming the two strings that
  commit message cited, a value short enough that the generic rule cannot reach them, and an
  assertion that `len(...) < 32` so the coincidence cannot return unnoticed. A polarity control
  holds `the pwd command prints a directory` unchanged, since `pwd` is also an ordinary command and
  the separator is what distinguishes a key from a word.
  **The history cannot be corrected.** `3906c51` and `f5dc0eb` are pushed; the claim is corrected
  here, in the following commit message, and in the PR description, rather than by a force-push.
- **`_AGENT_ARTIFACTS` was a denylist, written in the pass that inverted two others.** The third
  review closed a NUL-in-`SKILL.md` evasion by adding names to a set — the polarity P3 refuses, and
  the same pass had just inverted the `os` and `yaml` tables for that reason. A fourth review walked
  past it three ways in one attempt: `AGENT.md` (singular, a real convention for several tools),
  `prompt.txt`, and `setup` with no extension at all. Each cost a rename.
  **Inverted.** An unread file counts as `unread_code` *unless* its extension is in
  `_BINARY_ASSETS`, so the burden of enumeration moved from the target to us. It stays a pure
  function of the path, which is what lets it cover the oversized case the third pass wrote down as
  an accepted residue — a residue that was only ever a statement that padding is free, since
  `setup` at 5 MB never opens and no test needing its bytes could reach it.
  `has_shebang` is **removed** from `FileEntry`, and `_AGENT_ARTIFACTS` with it. Both are subsumed:
  a file with a shebang either has no extension (not exempt) or a code extension (not exempt). A
  field added one day earlier, carrying a comment claiming it closes an evasion that a different
  mechanism now closes, is a debt rather than an asset.
  The test is parametrised over `SKILL.md`, `AGENT.md`, `prompt.txt` and `notes.mdc`, and **none of
  those names appears anywhere in the source** — they pass because their extensions are not
  exempted, so a fifth spelling needs no code change. That is what the inversion buys, and it is
  the difference between this fix and the one it replaces.

**Accepted as structural, the reviewer agreeing:** `Cookie: session=`, a credential in a tuple
position (`auth = ("admin", "x")`), and triple-quoted values. All three are the limit of redacting
by key name rather than by shape.

**Still open and correctly placed:** ledger flooding is M7's; whether `src/secrev` should be *held*
to importing no process module is a `STACK.md` §2.1 amendment.

## The fifth review, 2026-09-18 — F1 was closed on its sites, like the rest

A fifth review found that the fix for the fourth had itself been applied to the occurrences that
were demonstrated. `952fd8e` corrected two sentences in `CLAUDE.md` and left the same wording in
the code — including in the line printed to `stderr`, which is the only one a user sees, and which
was printed beside `setup`, `prompt.txt` and `AGENT.md`, none of which has a code extension.

**Three mechanisms, not one phrase.** Searching the whole tree rather than the named sites found
that `inventory.py`'s module docstring still stated "Binary — a NUL byte in the first 8 KiB", the
rule a `STACK.md` §5 amendment replaced in this milestone; and that two comments in
`self_check.py` referred to `BANNED_OS_PREFIXES` and `BANNED_OS_NAMES`, constants deleted when that
table became an allowlist. A docstring is the worst placement of the three after a printed string:
it is read first, and by someone who has come to change the thing it describes.

**F1 was reopened and re-closed against the class**, on the precedent of A3, C3, D1, E1 and E3.

**The method, now in `CLAUDE.md`.** The reviewer proposed searching the old mechanism name after any
replacement. The refinement worth recording is that the *list of names must be derived, not
remembered* — a remembered list is a denylist, and this milestone's own history is four rounds of
those failing. `git log -p <base>..HEAD` over the branch's commits yields it; `git diff <base>...HEAD`
does not, because a net diff cannot see an identifier introduced and removed inside the branch, and
`_AGENT_ARTIFACTS` and `has_shebang` were precisely that. My first attempt used the net diff and
missed both — the two the reviewer had named.

**Raised, not decided: can this be enforced in a gate?** It is mechanism, so it is a real design
question and does not belong in the margin of an already-long milestone. Three candidate shapes,
recorded so the question is not lost:

1. **A replacements registry** — a data file of `old name → new name, when, why`, with an assertion
   that every occurrence of an old name sits inside a block marked historical. Honest and simple to
   check; its cost is that the registry is itself a list someone must remember to append to, which
   is the failure mode this whole rule exists to answer.
2. **Derive from git in the assertion** — no registry. The check computes removed identifiers from
   the branch's commits and fails on any unmarked occurrence in the working tree. Nothing to forget;
   its cost is that it needs a base ref, so it covers one branch's replacements rather than the
   project's whole history, and it would need a convention for marking prose as historical anyway.
3. **Mark historical prose explicitly** — a convention (a leading `Was:`, or a marker comment) with
   an assertion that any deleted identifier appears only inside such a block. The lightest to
   implement and the easiest to drift, since nothing makes the marker appear.

All three need the same missing piece: a machine-readable way to say "this sentence is a record,
not an instruction". That is the decision, and it is the owner's.

## The sixth review, 2026-09-18 — the method was written correctly and then run narrowly

The rule added in the fifth commit says "search the old name across the whole tree — not only the
diff, and not only `src/`". The pass that introduced it ran **two** searches: the identifier search
included `*.md`, which is how it reached this ledger; the *concept* search — `NUL byte`, `shebang` —
was restricted to `*.py` and `*.sh`. So the search that exists to catch **prose** was the one
limited to code, and `.claude/skills/` and `tests/fixtures/` were never looked at.

The reviewer ran `git grep -n "NUL byte in the first 8 KiB"` from the root, exactly as the rule
says, and got two live hits. **The command is now written into the rule**, because what failed was
not understanding what to search for — it was the scope of the search, and seven words close that
exact failure.

**Reading the skills found three more that no mechanism-name search could have reached**, because
they are not about this milestone's mechanisms at all:

- **`secrev-invariants` stated the candidate id as `(relative_path, line, rule_id, ordinal)`.** The
  derivation is `(relative_path, rule_id, window_sha256, ordinal)` and `line` is *deliberately
  absent* — `derive()` rejects it rather than ignoring it, per FR-4.5. A core NFR-3 claim, stated
  backwards, in the file whose own opening line calls these rules "not revisable". An M1-era error,
  not a drift from this milestone.
- **`debugging` carried the identical wrong derivation.** Two files, one error, and the same
  sentence — so it was copied once and has been read as instruction ever since.
- **`pattern-author`'s schema example wrote `severity_hint`.** The catalog requires
  `default_severity_hint` and refuses unknown fields, so following that example produces *two*
  exit-2 failures: an unknown field and a missing required one. A skill that teaches pattern
  authoring, teaching a catalog that will not load.

Also in `secrev-invariants`: the exclusions list named seven directories where the code has
fourteen and says nothing about `--exclude` replacing the set; and "writes outside the workspace"
sat under **"Enforced three ways"** — which is the exact claim M3.5's E2 removed from the README,
because nothing enforces it and `cli.py` writes by design.

**F1 is not reopened a third time, and the reason is worth stating rather than assumed.** Its
wording is scoped — "every document claim in §1F" — and `.claude/skills/` was never in §1F. The box
is literally true. What is true *and* uncomfortable is that every sweep this milestone ran,
including F1's, stopped at the repository's own documents and never entered the directory of files
that load into a session **as instruction**. That is a scope gap, not a false box, and mechanically
reopening F1 would blur the difference. **Raised for the owner: should `.claude/skills/` be inside
F1's scope, or inside a box of its own?**

**Still open — a deliberate pass over `.claude/skills/`.** Four of the nine are project-specific and
were read here; three of those four carried false claims. The remaining five were **not** read,
which is stated rather than counted as covered — but they were checked for project-specific claims,
and the result is worth recording: `skill-developer` and `eval-harness` each open with a
"Project note (secrev)" saying the skill was written for another stack and naming what does not
apply here. That is the honest form — a foreign skill that flags its own foreignness rather than
asserting a contract it does not know. `iterative-retrieval`, `strategic-compact` and
`skill-rules.json` mention nothing project-specific at all.
(An earlier draft of this paragraph called all five "generic tooling" without checking. Two of them
matched a grep for project terms, and the check ran before this entry shipped — in the ledger whose
subject is exactly that failure.) The case for the
pass is that these files describe contracts from M1 through M3, so mechanism-name search cannot
reach them — only reading can, which is how all three above were found.
