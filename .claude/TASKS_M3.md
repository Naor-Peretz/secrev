# M3 task ledger — the threat-model layer

Scope: `BRIEF_M3.md`. Mechanism: `STACK.md`. Source of the structure: PRD §8 in full, FR-1.5,
FR-2.1–2.3, AC-4. Receipts go in `.claude/receipts.md`.

M3 writes prose. Nothing here produces a deterministic artifact, so NFR-3 has no claim on it and
the golden tests are unaffected — which also removes the safety net M1 and M2 leaned on. What
replaces it is the Definition of done's demand that every mandatory question be answerable from
something the tool already emits, or be marked as waiting for a phase that does not exist.

## Decided by the owner, 2026-09-16 — with four corrections to my reasoning

**D-1 — `threat-models/` is protected, in the change that creates it.** Agreed. Two corrections:

- **The branch was the `surfaces` collision again.** I wrote that `threat-models` is unlikely to
  appear as a command word, and the branch it would land on was called `m3/threat-models`. Once the
  word is protected, `git log main..m3/threat-models`, `gh pr create --head …` and checking the
  branch out by name are all refused, exactly as `m2/surfaces` was. Renamed to `m3/overlays` before
  the protection commit, while nothing was pushed and the rename was free.
- **Protection gates a change; it does not make a removal visible.** The stated failure mode is
  "an unreviewed edit narrows the review with nothing reporting it", and protection only answers
  the *unreviewed* half. An approved edit that drops a mandatory question is still silent. So every
  mandatory question carries a stable id (`CORE-03`, `MCP-07`), and a test fails when an id
  disappears without the golden being updated deliberately — the discipline the goldens already
  use. The ids pay off twice more: M9's report can say which questions were asked and answered,
  and a finding can cite the question it came from. `threat-models/**` also joins HARNESS-CI's
  sensitive-path list, so the guarantee is not only local.

**D-2 — `_classifier.md` stays in M3 and is written last.** Agreed, with one correction: writing
it last prevents the *first* divergence, not the next one. If the classifier restates signals
copied from each overlay, the two lists drift the first time an overlay is edited. So there is one
source of truth — **the signals live in each overlay's applies-when section, and the classifier
holds only the procedure**: how to read them, what to do with several matches, what to do with
none. A test asserts every overlay has an applies-when section.

The procedure fails toward inclusion, because misclassification is silent narrowing of exactly the
kind P11 exists to prevent — an artifact tagged "skill" that also exposes an MCP server never gets
the MCP questions:

- apply **every** overlay that plausibly matches, not the best one;
- if nothing matches, apply the core alone and record the result as a gap.

**D-3 — the archetype does not go in `recon.json`.** Agreed, with one correction: "a judgment the
agent records in its own phase" is not a record until it has a shape. Free-form prose cannot be
checked by M7's gate or read by M9's report, and an agent that quietly skips an overlay leaves no
trace — H-4's failure one level up. Without touching `recon.json`, the review phase's own output
states: the archetypes chosen **and the evidence for each**, the overlays applied, and the question
ids answered. That shape goes to M7 with the FR-1.5 placement question, so the freeze has something
concrete to decide.

**On the order — settled in advance so it cannot be settled under pressure.** `mcp-server.md`
proves AC-4 only if the core is genuinely complete. If writing that overlay reveals a question that
belongs in the core, the temptation is to put it in the overlay so the diff shows the core
untouched and AC-4 stays green. **A core gap is a finding:** fix the core in its own commit, then
re-prove AC-4 with an overlay that did not require touching it. The overlay is never bent to pass
the test — that is the H-1 shape applied to an acceptance criterion.

**Found while asserting D-1, and worth more than the assertion.** The test that a closed milestone
may not rewrite an overlay failed with `rc=0`: `scope-guard.sh`'s M2 branch refuses `*patterns/*`
by name and passes everything else, so adding a directory to `is_scoped_path` does **not** make
every milestone police it. Scoping decides which paths the guard is consulted about; each
milestone's branch decides the answer, and a branch written before the directory existed answers
"permit" by omission. The guard was changed rather than the assertion weakened — the alternative
was a test that matched the code and left the hole. Every milestone branch added later has to
answer for every scoped directory, which is the cost of `case` over a default-deny table and is
now written down instead of rediscovered.

## Open, for the owner — raised in `BRIEF_M3.md` §6, before implementation

- **D-1 — Does `threat-models/` join the protected set (H-4)?** `patterns/` and `surfaces/` are
  protected because they are tool input and an unreviewed edit narrows the review with nothing
  reporting it. The failure mode transfers; the mechanism does not — those are machine-read data,
  these are prose a reviewing agent reads. A `STACK.md` §8 amendment either way, and M2's C-1
  lesson says decide it **before** the directory exists, because protecting an input afterwards
  leaves a window in which it is not.
- **D-2 — Does `_classifier.md` belong to M3?** The PRD's build order says yes; FR-1.5 puts
  classification in Phase 1, whose scripts are M1's, and FR-1.4's capability manifest — one of the
  signals a classifier would want — is not built. Shipping the core and two overlays and deferring
  the sorting is the alternative.
- **D-3 — Is the archetype supposed to reach `recon.json`?** FR-1.5 sits in Phase 1, but
  `recon.json`'s contract has no field for it. If the classifier's output is machine-readable
  rather than a judgment the agent makes, that is a data-contract change and belongs to M7's
  freeze.

## Raised during implementation — not resolved here

**FR-1.4's capability manifest is owned by no milestone.** Found while writing `_agentic-core.md`
§4, the section PRD §8.1 devotes to capability grants and the one that leans on FR-1.4 hardest.
FR-1.4 requires extracting "declared tool grants, permission entries, allow/deny lists, filesystem
scopes, network scopes, and any request for elevated access", and PRD §13's build-order table names
it in no row — M1 is recon and the sweep, M2 the surfaces, M4 structure, M5 the closure and the
instruction and manifest packs. P10 makes capability grants the privilege boundary and says an
unbounded grant is a finding before a line of implementation is read, so the gap is not cosmetic:
it is the evidence base for four mandatory core questions.

Raised, not resolved (`BRIEF_M1.md` §8). It looks like a PRD correction rather than a brief
conflict, and picking a milestone here would lose the signal. What M3 does meanwhile is what the
Definition of done asks for — CORE-11 states in the file itself that no phase produces this
evidence yet, and names reading the manifests as the interim answer.

**C-1 — AC-4's "no script changes" against the test that H-4 requires. Needs the owner before
TASK-M3-003.** Found by the `plan-reviewer` catch-up pass. AC-4 reads: "a new archetype can be
added by adding one overlay file, **with no script changes** and no edit to `_agentic-core.md` —
proven by doing it once", and NFR-6 agrees ("new archetype = new or edited data file").
`BRIEF_M3.md` §4 box 5 repeats it. But `tests/test_threat_models.py` pins the overlay set in
`OVERLAYS`, and asserts it in both directions, so adding `mcp-server.md` **requires editing a
Python file** — and AC-4's demonstration cannot then be shown as "one new file, nothing else".

Both cannot hold as written, and the pin is not optional: `STACK.md` §8 H-4 now requires that a
test fail when a question vanishes, which is the owner's own second correction to D-1. So deleting
the pin is not on the table. The visible options are to rule that `tests/` is not "a script" for
AC-4's purposes and say so in the brief, or to make the test discover overlays as data. Precedent
worth weighing, and it cuts toward the first: `tests/test_patterns.py` already hardcodes a pattern
count and a language-scoped set, so adding a pattern has edited a test file since M1 — but M1 never
had to *demonstrate* a matching acceptance criterion, and AC-4 has the word "proven" in it.

Raised, not resolved (`BRIEF_M1.md` §8). Recorded before TASK-M3-003 rather than after, because
that task's commit is where the conflict becomes evidence.

**Decided by the owner, 2026-09-16: discovery in code, the pin in data.** Neither of my two
options was taken, and the correction to the first is the important part — ruling that `tests/` is
not "a script" would make AC-4 pass **by redefining a word**, when AC-4 exists to serve NFR-6:
adding an archetype should be a content change, not a code change, whatever the directory is
called. The `test_patterns.py` precedent does not license it; it is the same defect one milestone
earlier, and M1 never had to *demonstrate* a matching criterion.

Pure discovery was rejected for the opposite reason, and it is the trap the obvious fix walks into:
if the expected set is simply whatever the glob finds, then deleting an overlay — or a question
inside one — shrinks the expected set and the actual set together, and the test stays green. That
is exactly the silent narrowing H-4 exists to prevent, so the pin cannot be computed.

What lands: `tests/golden/question_ids.json` holds every file and its ids;
`tests/test_threat_models.py` names no overlay and compares glob against golden **in both
directions**. Adding an archetype is then one overlay plus one golden entry, with no Python
touched. Two owner conditions, and their honest status:

- **Protect the golden.** Done. `STACK.md` §8 H-4 amended through spec-guard to carry
  `tests/golden/`, `bash_guard.py` extended, three assertions added and H-8 defeat-verified. The
  artifact goldens inherit the protection, which is right rather than incidental — a golden edited
  without review is a comparison that stops comparing — and the cost is stated: regenerating any
  golden now needs the owner to stage it. Found while doing it: the guard's refusal message spelled
  the protected set out and had already drifted, omitting `threat-models/`, so it is now derived
  from `PROTECTED` and cannot drift again (H-7 in the smallest possible form).
- **On the CI sensitive-paths list.** **Only half possible, and said plainly rather than ticked.**
  There is no such list: HARNESS-CI is an unticked task in `TASKS_M2.md` and its path list is plan
  text, which `rg -n "threat-models" .github/` confirmed by returning nothing. What was done
  instead is live but weaker — `harness.yml`'s `paths:` now includes `tests/golden/**`,
  `patterns/**`, `surfaces/**` and `threat-models/**`, so a change to any of them runs the guard
  suite in CI, where nothing ran before. It decides which pushes *run* a check; it cannot refuse
  one and has no notion of review. The workflow says so in a comment, because a paths filter that
  looks like enforcement is worse than none — it invites the assumption that someone is watching.
  The approval gate remains HARNESS-CI, still carried, still unticked.

**On the second condition — the migration does not need its own commit, and the reason is better
than the condition.** Its purpose was a clean AC-4 diff. Nothing is committed yet, so the
Python-pinned form never enters history at all: commit 1 carries the data pin from birth, and the
repository never contains the arrangement AC-4 forbids. The golden was staged for commit 1 without
its `mcp-server.md` entry, so the overlay's own commit shows one markdown file and one added golden
line — earned rather than flattered by having landed the entry early.

**C-2 — is `threat-models/README.md` a deliverable?** It is not in `BRIEF_M3.md` §2's four-file
tree and is not a task here, yet both new files cite it as **normative** for the id convention
(`_agentic-core.md` "append-only", `skill.md` §4). A fifth document inside a protected directory
that the overlays treat as their rule source should either be a declared deliverable or have its
rules live where they already bind — `STACK.md` §8 H-4 now carries the id-and-test rule, so the
README duplicates it. Raised rather than settled: removing text from a protected directory to
resolve a tidiness question is exactly the kind of edit H-4 exists to slow down.

**Settled 2026-09-16, and the framing was wrong.** I had been treating this as raise-don't-resolve,
but `BRIEF_M1.md` §8 governs a conflict *between binding documents*, and there is none here: the
PRD and `STACK.md` say nothing about this file, and a brief is the lowest-precedence document of
the three. What the brief had was a tree that stopped describing its own directory — the same
defect `BRIEF_M2.md` C-4 and C-5 fixed by correction rather than escalation. So: `README.md` joins
§2's deliverable tree with a dated note, and its normative half now cites H-4 as the binding
statement instead of restating it (H-7), which removes the duplication that made the question worth
asking. Both halves matter — declaring it stops an undeclared file being a rule source, and the
citation stops two copies of one rule agreeing only until one is edited.

---

- [x] **TASK-M3-000 — The marker moves, and the guard has rules first.** `scope-guard.sh` gains an
      M3 branch that refuses the scoped tree with M3's own reason rather than falling through to
      `refuse_no_rules`, whose message ("this milestone needs its own rules added here") is false
      once the rules exist. `attack.py` asserts the refusal and its message, reading stderr rather
      than stdout — the first draft read stdout, which carries `ask` payloads, and passed nothing.
      Marker `M2` → `M3` only after the rules landed: moving it first write-locks the scoped tree
      (H-6), which is exactly what happened between M1 closing and `BRIEF_M2.md` being written.
      *Accept:* 108 guard assertions; M3 refuses `src/` and `patterns/` naming its own remit.

- [x] **TASK-M3-001 — `_agentic-core.md`.** The eight mandatory sections of PRD §8.1, and nothing
      archetype-specific. The expensive file: written badly, every overlay restates it and they
      drift, which is §8's own reason for two layers.
      *Accept:* all eight sections present, each specific enough that two reviewers would look at
      the same places; no sentence that only applies to skills or only to MCP servers.
      *Done:* 27 questions, `CORE-01`…`CORE-27`, across the eight sections in §8.1's order. Each
      names its evidence — a `recon.json` field or a `hits.jsonl` `rule_id` that exists today, or
      the phase that would produce it and does not exist yet. Neutrality is mechanical, not
      claimed: the file contains no occurrence of "skill" or "mcp" in any casing.
      `tests/test_threat_models.py` pins the id set as the golden, asserts the eight headings are
      present **and in order**, and fails a question that carries no evidence line — the three
      ways the file could quietly stop meaning what it says. 372 tests, both gates green.

- [x] **TASK-M3-002 — `skill.md`.** The six sections of §8.2 in order. §8.2 item 3 requires the
      activation description's breadth by name. M2's own run is the evidence: ten skill activations
      found in this repository, one of them a false positive — a `description:` line inside a
      documentation template — which is precisely what the applies-when section has to
      disambiguate.
      *Accept:* six sections in order; known-good implementations present, not deferred.
      *Done:* six sections in §8.2's order, ten questions `SKILL-01`…`SKILL-10`, each naming its
      evidence. **This ledger's own description of the false positive was too coarse and the
      overlay corrects it:** the record at `.claude/skills/skill-developer/SKILL.md:143` sits inside
      a fenced ```markdown block showing a skill template, but *that file is a skill* — its
      frontmatter is at the top. So the discrimination the applies-when section makes is **per
      record, not per file**, and it is made by reading the head of the file rather than by
      discarding the file. Getting that backwards would drop a real skill from review, which is the
      more expensive error of the two. §5 states the mechanism before naming packs: `--catalog`
      takes a file or a directory and every pack in a run shares one `version`, so there is no
      per-pack enable switch, and the selective enabling FR-2.3 implies is itself recorded as a
      gap. `_instruction.yaml` and `_manifest.yaml` are named as not existing (M5) with the
      consequence spelled out — the ledger's silence over a skill's prose is coverage that does not
      exist, not coverage that passed. Known-good §6 is present and concrete, and deliberately
      stops short of clearing its own example: `secrev-invariants` is offered as a *shape*, with
      the note that it is this project's harness, in scope for its own review under AC-10, and not
      cleared by one. 380 tests (was 372), both gates green.

- [ ] **TASK-M3-003 — `mcp-server.md`, and AC-4 demonstrated.** §8.2 item 3 requires *tool return
      values* by name as a sink: they land in an agent's context and become instructions (P8).
      Written after `skill.md` so the diff can show `_agentic-core.md` untouched — AC-4 proven by
      doing it, not asserted.
      *Accept:* the core is byte-identical across this task's commit; no script changed.
      *Written, accept pending the commit.* The file exists, ten questions `MCP-01`…`MCP-10`, and
      `_agentic-core.md` was not touched while writing it — so no core gap was found, which is the
      outcome the pre-settled rule above was written for and not a claim that the rule went untested.
      The box stays open deliberately: its criterion is a property of a **diff**, and asserting it
      from a working tree is exactly the substitution AC-4's "proven by doing it once" forbids.

- [x] **TASK-M3-004 — `_classifier.md`, per D-2.** If it lands here: sorts by hand the three shapes
      this repository already knows — a skill with a `SKILL.md`, an MCP server declared in
      `.mcp.json`, and one artifact that is both. Composition is the norm (FR-1.5, §8.3).
      *Done:* procedure only, no signals — it directs the reader to each overlay's applies-when
      section rather than restating it, which is D-2's one source of truth. Written last, after both
      overlays, so the "both" example could be sorted for real rather than imagined. Carries the
      fail-toward-inclusion rule with its reason (misclassification is silent narrowing, P11 one
      level up; an overlay applied needlessly costs a few quick resolutions, one not applied costs
      the whole class it was written for). Two things added beyond the brief's list because their
      absence would have been a hole: **what is not a signal** — the artifact's own prose about
      itself, which is content to be reviewed (P8) and never an input to deciding what is asked of
      it — and **step 7, the seams** (FR-0.8), which no single overlay owns. Closes with D-3's
      output shape: archetypes with evidence, overlays applied, question ids carried forward, going
      to M7 with the FR-1.5 placement question. Its golden entry is an empty id list, which is the
      honest encoding of "procedure, not questions", and the file is still pinned — so adding a
      question to it later fails until the golden says so. 371 tests, both gates green.

- [ ] **TASK-M3-005 — Close.** DoD ticked; `STACK.md`/PRD corrections raised during the work go
      through spec-guard; receipts. The marker moves only after `BRIEF_M4.md` and its scope-guard
      rules exist.
