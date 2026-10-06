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

---

## 2. Deliverables

| File | Owns | Must not know about |
|---|---|---|
| `src/secrev/closure.py` *(new)* | The reachable artifact set from a declared entry point: files referenced, progressively or conditionally loaded resources, bundled scripts and binaries, and resources fetched at load or run time — the last recorded as **unresolved**, never followed | `sweep`, `surfaces`, `structure`. Its unresolved members reach `hits.jsonl` through `ledger.py` under `source: closure` (§6 Q1, answered), exactly as the three detection sources do — never by importing one of them |
| `patterns/_instruction.yaml` *(new, see §6 Q2)* | FR-3.13's seven classes as prose patterns, each with the question it raises | Anything that concludes. FR-3.15 is a permanent constraint, not a gap |
| `patterns/_manifest.yaml` *(new, see §6 Q2)* | FR-3.14's five classes over capability grants and configuration | The archetype. A wildcard grant is a question about *this* manifest, not about what kind of artifact it is |
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

1. **`is_nfr3_path` gains `closure.py`, and the golden test for `closure.json` is written, before
   `closure.py` exists.** A determinism check written after the generator is a retrofit onto code
   composed without it, and NFR-3 is the one requirement that does not survive being retrofitted
   (D-4). This is the same first step M1 and M2 took, and M4 took it for `structure.py`.
2. **`closure.py`, on a fixture tree with a deliberate cycle.** A skill that references a file that
   references the skill is not exotic; it is how progressive disclosure is written. The walk must
   terminate and the output must not depend on where the cycle was entered.
3. **`_instruction.yaml` and `_manifest.yaml`, from the recorded coverage gaps**, with the M1
   conventions unchanged: `id` is `namespace.name`, `layer` is always a list, `flags` is a fixed
   subset, line-oriented matching only, strict validation, exit 2 naming the offending pattern id.
   `precision: low` is a first-class expected value here more than anywhere — paraphrase defeats
   regex, and under P4 every candidate is resolved anyway, so a false positive costs a paragraph
   while a miss is a silent gap.
4. **The CLI subcommand last**, as in every previous milestone.

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
- [ ] **A4 — `cli.SOURCES` gains `closure`, and every check deriving its block list from it covers
      the fourth block without being told.** Evidence: the determinism stage's artifact half, which
      derives the blocks it requires from `cli.SOURCES` precisely so that a new source is covered
      by adding it in one place — remove the entry and that stage must go red.
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

## 6. Questions — Q1 answered, four open

Raised rather than resolved, each naming what would be lost by deciding it the wrong way. Q1 is
answered and kept in place with the reasoning, because the reasoning is the part that will matter
when the next conflict of this shape appears.

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

**Q2 — Do the two new packs live in `patterns/`?** The PRD §7 tree says yes. But M2 set the opposite
precedent for data read by a different mechanism — surface kinds went to `surfaces/`, structural
rules to `structure/` (M4 Q1) — and FR-3.15 gives instruction patterns different *semantics*: they
may never auto-classify. If they sit beside the code patterns, nothing in the data says which kind a
pattern is. Options: `patterns/` with a mandatory field distinguishing them; `instruction/` and
`manifest/` directories on the M2 precedent; or `patterns/` and a `layer` value that the loader
enforces.

**Q3 — What counts as "prose in the closure"?** FR-3.13 says *all prose*. Markdown is obvious. A
tool description inside a JSON manifest, a YAML `description:` field, a docstring, a comment —
each is prose that reaches an agent's context, and each needs a different extractor. Deciding this
narrowly makes M5 shippable; deciding it narrowly *by accident* is how the instruction layer ends up
covering only `.md` files while the real payload sits in a manifest field.

**Q4 — Does M5 emit the prose inventory FR-3.15's Phase 4 obligation needs?** FR-3.15 requires a
full read of the prose closure where the instruction layer is substantial. That read happens in M7,
but it needs to know *what* the prose closure is and how large it is. Emitting that here is cheap;
discovering in M7 that nothing produces it is not.

**Q5 — Is `secrev closure` its own command, or part of `recon`?** `STACK.md` §3 lists five commands
and `closure` is not among them, while FR-1.2 names `closure.py` as its own module in Phase 1. A
sixth command is a `STACK.md` amendment; folding it into `recon` makes `recon.json` the artifact and
leaves `closure.json` unproduced, against the PRD's §7 tree.

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
