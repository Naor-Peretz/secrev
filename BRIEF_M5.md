# BRIEF_M5 — the closure, and the two layers that make this review agentic

> Status: **current**. Written before any M5 code exists, and before the marker moved —
> `scope-guard.sh` ends in `*) refuse_no_rules`, so moving the marker first write-locks the scoped
> tree against a milestone nobody has scoped (H-6, and the mistake M1→M2 actually made).
>
> Precedence: a brief loses to `STACK.md`; `STACK.md` loses to the PRD on intent and wins on
> mechanism. Where this brief and the PRD disagree, **raise it** — a conflict usually means the PRD
> needs a correction, and resolving it quietly loses that signal (`BRIEF_M1.md` §8).

---

## 1. Scope

**In:** `closure.py` → `closure.json` (FR-1.2), `patterns/_instruction.yaml` (FR-3.13),
`patterns/_manifest.yaml` (FR-3.14), the `secrev closure <target>` command, their fixtures and
goldens, the determinism coverage for the new artifact, and M5's own `scope-guard.sh` rules.

**Why these three together.** They are the milestone the PRD's own table calls *"the layers that
make agentic review real rather than ordinary code review"* (§13). An ordinary scanner reads the
files it is given; this one has to answer what the artifact can **pull in later** (P9), treat prose
reaching an agent's context as **behaviour-defining** (P8), and read a capability grant as a
**claim about authority** (P10). The three are one idea in three places: the unit of review is not
the entry file.

**The catalog grows for the first time since M1, and that is the milestone's main risk.** Nine
patterns shipped in M1 and nothing has been added since — M2, M3, M3.5 and M4 all refused catalog
writes by name in `scope-guard.sh`, and M3's brief recorded *"an overlay wanting a pattern that does
not exist is a finding about the catalog, recorded as a coverage gap — not a pack added here."*
Those recorded gaps are the input to this milestone. **Read them before writing a pattern**; a pack
written from the FR list alone would be a pack written against a guess, when this repository has
spent three milestones accumulating the evidence.

| Not now | Why it would be got wrong early | When |
|---|---|---|
| Triage, severity, or any verdict on an instruction-layer hit | FR-3.15 is explicit that these patterns *raise questions for manual review and never auto-classify*. Code that decides would be built against the four examples in front of us | M7 (gate), M6 (phase ordering) |
| Following a remote closure member | `STACK.md` §2.1 forbids runtime network calls, and FR-1.2 already says the answer: an unresolvable member is **itself a finding candidate**, not an omission | never, by design |
| A second language in the closure walker | `STACK.md` §7: Python-only is an acceptable v1 position, a half-built multi-language layer is not. Every closure member in another language is a recorded coverage gap (FR-3.8) | M10, with the parser seam M4 built |
| `SKILL.md`, phase ordering, the Phase 2 gate | Writing the enforcement before the thing enforced is a procedure written against a guess (`BRIEF_M3.md` §1) | M6 |
| The `subagent.md`, `hook.md`, `agent-config.md` overlays | AC-4 says adding an archetype is cheap; proving it with three more overlays inside one milestone proves nothing about the seam | M8 |
| Harness hardening of any kind | Not a source milestone's business. `BRIEF_M4.md` §6 Q5 said so and M4 did it anyway, which cost that milestone eighteen of its twenty-two commits. HARNESS-FS and HARNESS-CI in `.claude/TASKS_M2.md` own what is left | their own milestone |

**The harness rule, set in advance by owner decision (2026-10-07) rather than discovered under
pressure.** A harness finding that arises during M5 is **recorded in `.claude/TASKS_M5.md` and not
fixed**, unless it is a defect in something M5 itself adds. The reasoning is M3.5's, which the owner
and I agreed on at the end of PR #16: M4 took eighteen of twenty-two commits on the harness because
each finding was fixed "before `main`", and five review rounds became eight. The exception is
deliberately narrow and testable — *did this milestone introduce it?* — because a milestone that
breaks a guard and leaves it broken is worse than one that stops to fix it.

---

## 2. Deliverables

| File | Owns | Must not know about |
|---|---|---|
| `src/secrev/closure.py` *(new)* | The reachable artifact set from a declared entry point: files referenced, progressively or conditionally loaded resources, bundled scripts and binaries, and resources fetched at load or run time — the last recorded as **unresolved**, never followed | `sweep`, `surfaces`, `structure`. Its unresolved members reach `hits.jsonl` through `ledger.py` under `source: closure` (§6 Q1, answered), exactly as the three detection sources do — never by importing one of them |
| `patterns/_instruction.yaml` *(new, §6 Q2 answered)* | FR-3.13's seven classes as prose patterns, each with the question it raises. Holds `layer: [instruction]` patterns and only those | Anything that concludes. FR-3.15 is a permanent constraint, not a gap |
| `patterns/_manifest.yaml` *(new, §6 Q2 answered)* | FR-3.14's five classes over capability grants and configuration. Holds `layer: [manifest]` patterns and only those | The archetype. A wildcard grant is a question about *this* manifest, not about what kind of artifact it is |
| `src/secrev/catalog.py` | The Q2 rule: a pack's filename and its patterns' `layer` must agree, exit 2 naming the offending id | Which milestone added which pack |
| `src/secrev/inventory.py` | `is_prose(path)` beside `language_of` — one definition of what reaches an agent's context (§6 Q3) | The packs, and the closure |
| `src/secrev/cli.py` | `secrev closure <target>` → `closure.json`, and the `run.json` that records it | The closure algorithm |
| `src/secrev/recon.py` | A `coverage_gaps` line for every closure member in a language with no coverage, and for every unresolved member | `closure` — recon is a peer (P11) |
| `tests/test_closure.py`, goldens, fixtures | Byte-identical `closure.json`, a non-ASCII filename in the fixture tree, and a positive **and** negative fixture per new pattern | — |
| `.claude/hooks/lib/paths.sh`, `tests/harness/attack.py` | `is_nfr3_path` += `closure.py`, **before the file exists** — a new generator of deterministic output is silent under `determinism-guard.sh` until it is named there | — |
| `.claude/hooks/scope-guard.sh` | M5's own rules, answering every scoped directory **by name** | — |
| `scripts/determinism_check.py` | `closure.json` in the artifact comparison, derived from `cli.COMMANDS` rather than listed again | — |

---

## 3. The shape of the work

**`closure.py` is a fourth consumer of the walk, and the third thing to learn this.** `inventory.py`
was written first in M1 precisely because traversal order, NFC normalisation, exclusions and symlink
handling cannot be changed afterwards; `surfaces.py` (M2) and `structure.py` (M4) each inherited it
free. Closure is a *graph* over that walk rather than a filter of it, which is new — but the nodes
are inventory entries and the identity rules are `ids.py`'s. Nothing here invents a second notion of
what a file is.

**Order, and the reason — not alphabetical.**

1. **`is_nfr3_path` gains `closure.py` before `closure.py` exists**, so the determinism guard
   speaks on the first write. A determinism check written after the generator is a retrofit onto
   code composed without it, and NFR-3 is the one requirement that does not survive being
   retrofitted (D-4). The same first step M1, M2 and M4 each took. **`cli.SOURCES` does *not* gain
   `closure` yet** — the determinism stage derives its required blocks from `SOURCES`, so adding
   the entry before anything emits that block turns the stage red for a block that does not exist.
   It lands with the emitter, in step 2.
   *What cannot precede the file, against this brief's first draft: the golden test.* A golden with
   no generator is a red gate rather than a guard, since nothing here uses expected-failure
   markers. It lands in the same commit as `closure.py`, written before the code inside it.
2. **`closure.py`, its command, and the fourth ledger block — before the packs.** It changes the
   ledger's shape, and everything after it leans on that; a structural change is cheapest to review
   while the diff is still small. The fixture tree carries **a deliberate cycle**: a skill that
   references a file that references the skill is not exotic, it is how progressive disclosure is
   written. The walk must terminate and the output must not depend on where the cycle was entered.
3. **`_instruction.yaml` and `_manifest.yaml`, as data-only commits, from the recorded coverage
   gaps** — each pattern with a positive and a negative fixture, and Q2's loader rule
   (filename agrees with `layer`) in the first of them. M1's conventions unchanged: `id` is
   `namespace.name`, `layer` is always a list, `flags` is a fixed subset, line-oriented matching
   only, strict validation, exit 2 naming the offending pattern id. `precision: low` is a
   first-class expected value here more than anywhere — paraphrase defeats regex, and under P4
   every candidate is resolved anyway, so a false positive costs a paragraph while a miss is a
   silent gap.
4. **The prose inventory and `is_prose` last**, because it depends on both of the above: the
   inventory in `closure.json` and the pack's applicability must come from the same function (Q3,
   Q4).

**Two things the catalog conventions already settle, restated because they will be tempting here.**
No `multiline` field: anything needing cross-line reasoning is a structural rule by definition, and
M4 built the seam for it. And two hits on one line stay two hits (D-6) — prose will produce them.

---

## 4. Definition of done

Each box names its evidence. A box ticked from memory is the failure mode this list exists to
prevent, and M4's F2 found three documents asserting mechanisms that had been replaced.

- [ ] **A1 — The closure of the fixture tree is correct and complete**, with a positive case per
      member kind: a direct reference, a progressively loaded resource, a bundled script, a bundled
      binary, and a resource named for fetching. Evidence: `closure.json` beside a hand-written
      expectation in the test, not only a golden.
- [ ] **A2 — A cycle terminates, and the output does not depend on the entry order.** Evidence: the
      fixture contains one, and the test enters it from both ends and compares bytes.
- [ ] **A3 — An unresolved member is a finding candidate, not an omission** (FR-1.2, and §6 Q1 as
      the owner answered it). Evidence: the record is in `hits.jsonl` under `source: closure`, so
      FR-4.3 refuses to render a report while it is `unresolved`; it says why it could not be
      resolved; and nothing in `closure.py` attempts the fetch — asserted by the self-application
      check, which forbids runtime network calls. A `coverage_gaps` line instead of a ledger record
      would leave it through a *passing* gate, which is the omission FR-1.2 forbids.
- [ ] **A4 — `cli.SOURCES` gains `closure`, in the same commit as the emitter and not before.**
      Evidence: the determinism stage's artifact half derives the blocks it requires from
      `cli.SOURCES`, precisely so a new source is covered by adding it in one place — so removing
      the entry must turn that stage red, and adding it *ahead* of the emitter would turn it red for
      a block nothing produces. The owner caught that order in review of this brief's first draft.
- [ ] **A5 — A pattern's file and its `layer` cannot disagree** (§6 Q2). Evidence: a pattern with
      `layer: [instruction]` in `_manifest.yaml` is exit 2 naming the offending id, and the reverse
      too; plus the permit, since a rule that only refuses passes by refusing everything.
- [ ] **A6 — `is_prose` is one function and both consumers use it** (§6 Q3, Q4). Evidence: the
      instruction pack's applicability and `closure.json`'s prose inventory are derived from the
      same call, and `.mdc` is covered — a pattern restricted to `languages: [markdown]` would have
      skipped Cursor's rules files in silence, because `language_of` does not map that suffix.
      Comments and docstrings are an explicit `coverage_gaps` line stating why the gap is
      deliberate, not an omission.
- [ ] **B1 — Every FR-3.13 class has a pattern, and every pattern has a positive and a negative
      fixture.** Evidence: the seven classes listed against the pattern ids that cover them, with
      the gaps named where a class has no regex worth shipping.
- [ ] **B2 — Every FR-3.14 class has a pattern**, on the same terms.
- [ ] **B3 — No instruction-layer or manifest-layer record concludes anything.** Evidence: the
      `question` field of each new pattern reads as a question, and no new code assigns a severity
      or a verdict. FR-3.15 is the citation.
- [ ] **B4 — The recorded coverage gaps that motivated each new pattern are named**, and the ones
      this milestone does *not* close are still recorded. Evidence: the gap list before and after.
- [ ] **C1 — `closure.json` is byte-identical across two runs**, and adding an unrelated file to the
      target moves nothing in it.
- [ ] **C2 — `closure.py` is in `is_nfr3_path` before it exists**, so the determinism guard speaks
      on the first write. Evidence: the ordering in the commit history, and the assertion that
      fails when the line is removed.
- [ ] **C3 — The cross-platform digest comparison covers `closure.json`**, derived from
      `cli.COMMANDS` rather than from someone remembering this stage exists.
- [ ] **D1 — A non-ASCII filename appears in the closure fixture tree** (`STACK.md` §9), so the NFC
      rule stays honest in the one artifact that maps names to names.
- [ ] **E1 — Every closure member in a language with no coverage is a `coverage_gaps` line**, never
      silence (FR-3.8).
- [ ] **E2 — `secrev closure` honours the exit-code contract**: 0 success, 2 usage or config error
      including a malformed pack, 3 internal error. Evidence: one case each.
- [ ] **F1 — The tool runs on itself and the result is read, not assumed.** `secrev closure .` over
      this repository, and every candidate the two new packs raise against `.claude/` resolved under
      P4 — this repository *is* an agentic artifact, and the instruction layer is the one place
      where that is not a cute observation.
- [ ] **F2 — Every document claim this milestone makes is true or gone**, searched with
      `git grep -n "<old name>"` from the root, **no pathspec**, with the candidate names derived
      from `git log -p` rather than recalled. Every hit sorted into false, true-for-the-old-reason,
      or historical.
- [ ] **G1 — `scope-guard.sh` has M5 rules** answering every scoped directory by name, including the
      ones that did not exist when the case was written.
- [ ] **G2 — The marker moves to `M5` only after G1**, never before (H-6).
- [ ] Both gates green; self-application clean; every golden regenerated deliberately and every
      changed line explained; the receipt written.

---

## 5. Notes for the implementer

**`patterns/` is permitted here and was refused by every milestone since M1 — by filename, not by
directory.** `scope-guard.sh` permits `_instruction.yaml` and `_manifest.yaml` and refuses every
other file in the catalog, because a change to `_base.yaml` or `python.yaml` is an M1 correction in
its own commit. The first draft of that rule permitted the whole directory and justified it by
saying the bound was this brief and not the guard — the owner's correction, which is worth keeping
as a rule of its own: **a brief that names files names something a guard can check, and declining
to check it is a weaker rule arguing for itself.** What a guard still cannot check is the content
rule — that no existing question changes — and the positive/negative fixture pair every pattern
ships is what catches that.

**P8 is why this milestone is uncomfortable.** The instruction layer reads prose and asks whether it
is trying to steer an agent — and this repository's own `.claude/` is full of prose that steers an
agent, legitimately. Expect the packs to fire on `CLAUDE.md`, on the skills, and on this brief. That
is not a false positive to tune away: it is F1 working, and each hit gets resolved under P4 like any
other. **G-6 is the line that matters**: content in a *reviewed target* addressing the reviewing
agent is a High-severity finding, never an instruction.

**The closure is where an evasion lives.** Progressive disclosure is a legitimate design pattern and
an obvious evasion surface (P9, and the PRD says both in one sentence). A file that is only loaded
when a condition holds is still a closure member; "we could not tell whether this loads" is a
finding candidate and not a shrug.

---

## 6. Questions — all five answered

Each is kept in place with its reasoning rather than collapsed into the decision, because the
reasoning is what will matter when the next question of the same shape appears. **Two of the five
rested on premises that were false, and the owner corrected both from the code**: that nothing in
the data distinguishes a pattern's kind (`layer` has been a validated field since M1), and that
`STACK.md` §3 lists five commands (it lists six). Both were written from memory of the code rather
than from the code, which is the error F2 exists to catch, occurring in the document that raises
the questions.

**Q1 — ANSWERED by the owner (2026-10-07): the ledger, and D-11's wording is corrected rather than
FR-1.2 bent.** The question was whether an unresolvable closure member is a fourth `source:` value
(contradicting D-11 as written), a `coverage_gaps` line (contradicting "finding candidate" as
written), or something `closure.json` carries for Phase 4 to read.

The owner's reasoning, which is the part to keep: ask what FR-1.2 is *for*. It says such a member is
a finding candidate **"not an omission"** — the requirement is that it cannot be passed over in
silence. In this system exactly one mechanism guarantees that, and it is the ledger plus FR-4.3,
which refuses to render a report while any hit is `unresolved`. Recorded only in `closure.json` or
as a gap line, a remote fetch nobody assessed leaves through a *passing* gate, which is the omission
FR-1.2 forbids arriving by another door.

D-11's rationale is entirely about **detection** mechanisms, and three remains the right number of
those; an unresolved closure member is not a detection but a hole in the set that was examined. So
the word *detection* enters D-11 and `cli.SOURCES` holds four values with the fourth documented as a
different kind. **One addition from reading FR-4.4 while making the change:** the status such a
member is normally resolved as already exists — `deferred`, with a mandatory reason, surfaced under
"Not conclusively assessed", and the PRD says deferred items "are never silently dropped". The
mechanism FR-1.2 needs was already there; what was missing was the route into it.

Consequences for this milestone, which are now requirements rather than questions: `closure.py`
emits ledger records through `ledger.py` for unresolved members, `cli.SOURCES` gains `closure`, and
every check that derives its block list from `cli.SOURCES` — the determinism stage's artifact half
among them — covers the fourth block by construction rather than by someone remembering.

**Q2 — ANSWERED (2026-10-07): `patterns/`, and the loader enforces filename-to-`layer` agreement.**

**The question's premise was wrong, and the owner corrected it from the code.** I wrote that if the
packs sit beside the code patterns "nothing in the data says which kind a pattern is". `layer` is a
mandatory field: `catalog.py` validates it against `ledger.LAYERS`, which is
`frozenset({"code", "instruction", "manifest"})`, `kinds.py` and `structure_rules.py` validate the
same set, and the value is written onto every ledger record. FR-3.11 defines `layer[]` as a field of
a *pattern* — the PRD planned one catalog with this field separating it from the inside. Verified:
`LAYERS` is at `ledger.py:31` and checked at `catalog.py:164`.

**The M2/M4 precedent does not apply**, and seeing why is the useful part. `surfaces/` and
`structure/` got directories because they have a different **schema and engine** — `files` and
`declaration` for a kind, `shape` for a structural rule. Instruction and manifest patterns are the
*same* schema (a regex and a question), load through the same loader, and run in the same `sweep`.
What differs is the **resolution** semantics (FR-3.15: never auto-classify), which is an M7 rule
reading `layer` off the record. That needs no directory.

**One rule added by the decision:** a pattern with `layer: [instruction]` may live only in
`_instruction.yaml`, and that file holds only such patterns; the same for manifest. So the filename
— which `scope-guard.sh` now checks — and the semantics — which the loader checks — cannot come
apart. That is the same shape as the catalog permit correction: where a boundary can be checked
mechanically, check it.

**Q3 — ANSWERED (2026-10-07): by what reaches an agent's context, not by file format, and through
one function rather than a `languages` list.**

**The accident the question warned about is already loaded and aimed.** `sweep.applies_to` keys on
`inventory.language_of`, and `.mdc` — Cursor's rules files, prose that an agent reads as
instruction — is **not** in `LANGUAGE_BY_SUFFIX`, so `language_of` returns `None` for it. A pattern
shipped with `languages: [markdown]` would skip every one of them in silence. Verified: the map is
at `inventory.py:118` and the filter at `sweep.py:73`; `tests/test_recon.py` already parametrises
over `notes.mdc` for a neighbouring reason.

**In M5:** the instruction pack applies to markdown (including `.mdc`), text, JSON, YAML and TOML.
No extractors — `sweep` is line-oriented, so a `description:` line in YAML or a `"description":` line
in JSON is examined like any other, which covers MCP tool descriptions, skill frontmatter and plugin
manifests with no new code. The cost is false positives on strings that are not descriptions, and
that cost is acceptable precisely because FR-3.15 already requires a human read: a pattern that may
never auto-classify loses much less to a false positive than to a miss.

**Outside M5, as an explicit `coverage_gaps` line:** comments and docstrings in code. The line must
say what makes the gap deliberate rather than forgotten — in FastMCP a tool's **docstring is the
description sent to the model**, and it already falls inside the `surface.mcp_tool` window, so it
reaches the manual read rather than vanishing.

**The decision is one function, `is_prose(path)`, beside `language_of`** — not a `languages` list in
the YAML. One place to correct when the next format appears, and Q4 derives from the same function.

**Q4 — ANSWERED (2026-10-07): yes, in `closure.json`, derived from the same `is_prose`.**

`closure.json` carries the closure members that are prose, with a line count each. Cheap here, and
M7 needs it to decide what "substantial" means. **M5 does not set that threshold** — that is M7's
call, and choosing it here would be this milestone deciding a later one's rule.

The inventory and the pack must come from the *same* `is_prose`, or the inventory lists files the
instruction pack never ran on, or the reverse — a discrepancy nothing would report. That is the
reason `language_of` and `split_lines` live in `inventory.py` rather than in each consumer.

**Q5 — ANSWERED (2026-10-07): its own command, with `STACK.md` §3 amended.**

**And the question's own arithmetic was wrong**, which the owner caught: §3 lists **six** commands,
not five, so `closure` is the seventh. That sentence was written from memory of the table rather
than from the table — the error class F2 exists to catch, in the document raising the question.

Four reasons, none of them preference. The PRD defines `closure.json` as an artifact in its own
right. `recon` defines itself as declared metadata only and says deeper enumeration is not to be
attempted there, while a closure is exactly the resolution of references. After Q1 the closure
writes ledger records, so folding it into `recon` would make `recon` a candidate source and break
the boundary P11 exists to keep. And everything else that writes to the ledger has its own command
and its own block.

`STACK.md` §3 gains one row: `secrev closure <target> → closure.json + hits.jsonl (M5)`.

---

## 7. What M4 left on the table, and where it went

Recorded so that M5 does not inherit it silently:

- **HARNESS-FS** (`.claude/TASKS_M2.md`) — a confined test run. Until it exists, `.venv/bin` and the
  interpreters the gate executes are *detected* rather than prevented, and the protected-path check
  says so in its own docstring.
- **HARNESS-CI** — the approval gate for workflow changes, accepted in M3.5 and unbuilt.
- **A symlinked ancestor** of an interpreter is outside the replaceability walk, with the reasoning
  written beside the walk rather than here.
- **The five findings the M4 freeze deferred are closed** (`BRIEF_M4.md` §6, the (i)–(v) list), so
  they are *not* inherited: unreadable files, child exit codes, system git configuration, path
  normalisation, and a failed `ask`.
