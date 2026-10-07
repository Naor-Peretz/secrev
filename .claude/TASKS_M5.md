# M5 task ledger — the closure, and the two layers that make the review agentic

Scope: `BRIEF_M5.md`. Mechanism: `STACK.md`. Receipts in `.claude/receipts.md`.

**Why this file exists at all, and why there is no `TASKS_M4.md`.** The owner asked whether
everything open was actually recorded anywhere. It was not: M4 kept its decisions and its carried
obligations in `BRIEF_M4.md` §6, which worked while M4 was open and stopped working the moment it
closed — and `BRIEF_M5.md` §1 named this file for the harness rule before this file existed, a rule
pointing at nothing. Opening a ledger for M4 retroactively was considered and declined (owner
decision, 2026-10-07): a ledger written for a closed milestone is archaeology, and an obligation
needs a **live** home. So the obligations move here and M4's brief stays as the record of M4.

CLAUDE.md's own version of this rule came from TASK-M1-010: *a carried obligation that lives only in
a commit message stops being one.* A closed brief is the same thing with a longer shelf life.

---

## Decided before implementation

All five of `BRIEF_M5.md` §6 are answered and the reasoning lives there rather than being copied
here — two places holding the same argument is how they drift apart. In one line each:

| | Decision | Where |
|---|---|---|
| Q1 | An unresolvable closure member enters `hits.jsonl` under `source: closure`; D-11's wording gains the word *detection* | PRD D-11, §6 Q1 |
| Q2 | Both packs live in `patterns/`, and the loader enforces filename-to-`layer` agreement | §6 Q2 |
| Q3 | Prose is decided by what reaches an agent's context, through one `is_prose(path)` beside `language_of` | §6 Q3 |
| Q4 | `closure.json` carries the prose inventory, derived from that same function; the "substantial" threshold is M7's | §6 Q4 |
| Q5 | `secrev closure` is its own command; `STACK.md` §3 amended | §6 Q5, STACK §3 |
| Q6 | A rule *file* is versioned, not the catalog; a record carries its own pack's version. FR-3.12's wording corrected | PRD FR-3.12, below |

**Q6 was not in the brief's §6 — it arrived while implementing step 3** and is recorded here
because the ledger is where a live decision belongs. The question: `catalog.load` required every
pack to declare the same `version`, so adding `_instruction.yaml` would have forced an edit to
M1's closed `_base.yaml` and `python.yaml` — files `scope-guard.sh` refuses by name — for a change
that corrects no pattern in them.

Three routes were put to the owner: permit `patterns/*.yaml` again with a committed pin on M1's
nine patterns; have the owner make the two version edits by hand; or derive one catalog version
from the packs. **The owner took the third direction and corrected its mechanism: per-pack version
carried on the record, not `max`.** The defect in `max` is theirs and is the part to keep: with
`_instruction.yaml` at 2026.10.1, correcting a pattern in `_base.yaml` and bumping it to 2026.09.4
leaves the maximum unchanged, so `catalog_version` does not move, FR-4.6 never fires, and the
verifications the corrected pattern now reaches stay in force. Every bump would have to clear the
highest version in the catalog — a convention no loader can enforce, because it cannot know what
was there before.

Why per-pack is right rather than merely workable, in the owner's terms: it is what
`ledger.Hit.catalog_version` already says the field means — "the version of the ruleset that
produced this record" — and what the other two sources already do, a surface record carrying the
kinds file's version and a structural record the rule file's. The pattern source was the odd one
out because it is the only source reading several files. It gives FR-4.6's second trigger the
granularity it asks for. It needs no version grammar. The goldens do not move, because every
existing record already carries `2026.09.3`, which is its pack's version — verified: `hits.jsonl`
is byte-unchanged. M1's packs stay closed and the guard is untouched.

The cost, accepted: `run.json` records a pack-to-version mapping rather than one value, and
FR-3.12's wording needed the correction, which is now in the PRD on the same footing as D-11's —
the requirement's intent is unchanged and the sentence that stated it described one file.

**One thing worth recording about the rule that was removed: nothing asserted it.** The
"every pack declares the same version" check could be deleted without a test turning red; the only
thing holding it was the docstring arguing for it. Its replacement has four assertions, including
one that fails if a bump to one pack moves another pack's records.

**Two of those questions rested on premises that were false**, both corrected by the owner from the
code: that nothing in the data distinguishes a pattern's kind (`ledger.LAYERS` has been validated
since M1), and that `STACK.md` §3 lists five commands (it lists six). Recorded because the lesson is
not the correction — it is that both were written from memory of the code while the code was one
`grep` away.

## The harness rule for this milestone

**A harness finding that arises during M5 is recorded here and not fixed**, unless it is a defect in
something M5 itself adds. Owner decision, 2026-10-07, set in advance rather than discovered under
pressure: M4 spent eighteen of its twenty-two commits on the harness because each finding was fixed
"before `main`", and five review rounds became eight. The exception is narrow and testable — *did
this milestone introduce it?*

New findings go under the heading below. The heading exists now so that nobody has to decide where
to put the first one while deciding whether to fix it.

## Decided during implementation, because the brief left them to mechanism

Each is recorded here rather than in `BRIEF_M5.md`, because the brief states
requirements and these are how they were met. None of them is a question for the
owner; each is noted because a later reader would otherwise have to re-derive it.

- **An unresolved closure record is anchored on the referring line, with
  `lines-20`.** The member has no content — that is why it is unresolved — so
  the span a reviewer reads is the line that pulls it in. FR-4.6 then expires
  the verification when that line changes, which is the right trigger. Not a
  window name of its own: C-2 keeps differently *shaped* spans from being
  compared, and this is `lines-20`'s shape anchored on a line in a file exactly
  as a pattern record's is. `decl-20` exists because FR-4.1 says a surface is
  traced rather than windowed, so a surface verification is not a judgment of
  its span; a closure verification is a judgment of this one.
- **The content-mismatch record (A5) carries a new spec, `digest-pair`.** Its
  span is the two digests, not lines, because there is no line to anchor on and
  windowing the file would identify the very bytes whose provenance is the
  finding. The digests are redacted out of `match_excerpt` — a 64-character hex
  run is credential-shaped and G-3 is deliberately blunt — and that was left
  alone rather than fixed by weakening the credential rule or shortening a
  digest below its floor. The full pair survives in `closure.json` and in the
  unredacted window the id is derived from, so two different replacements
  produce two different candidates; a test holds exactly that.
- **`layer` is `code` on every closure record.** `ledger.LAYERS` is
  `{code, instruction, manifest}` and FR-3.11 defines `layer` as a field of a
  *pattern* — the three values say what kind of question a pattern asks. A
  closure record asks about composition, which is a property of the artifact's
  structure rather than of its prose or its grants, whichever file the reference
  sits in. That the field's name and value set fit patterns better than they fit
  this is the same PRD naming question already raised for `catalog_version` in
  `.claude/TASKS_M2.md`, and it is raised rather than resolved.
- **`status` is `unresolved`, not `deferred`.** §6 Q1 noted that FR-4.4's
  `deferred` with its mandatory reason is where most of these will land. That is
  a *triage* status, which M7 assigns; emitting it at the source would be this
  milestone resolving its own candidates (FR-3.2, FR-3.11).
- **The entry set defaults to every readable file, and `closure.json` records
  which question was asked.** `--entry` is repeatable, because FR-1.5 says
  multiple archetypes are the norm and a plugin bundle has several entry files.
  With no `--entry` the question becomes "what does this tree pull in that is
  not in it", which can be asked of a target that declares no entry point
  anywhere and which never under-reports. An entry the target lacks is a ledger
  record; an entry *outside* the target is exit 2, because that is a hole in the
  invocation rather than in the artifact.
- **`STACK.md` §7 and `BRIEF_M5.md` §2 looked contradictory and are not.** §7 is
  binding and says `recon.json` records a closure member in a language with no
  structural coverage; the brief's deliverable row asks for the same line and in
  the same row says `recon.py` must not know about the closure (P11). The two
  are compatible exactly one way, which is how the surface and structural lines
  already work: `recon.json` states the *class*, derived from the languages the
  walk found, and `closure.json` names the individual members. Raised here
  rather than resolved silently, and both documents are satisfied as written.

## Consequences for later milestones, found by running the tool

- [ ] **`secrev closure .` over this repository produces 1,153 ledger records,
      and FR-4.3 refuses to render a report while any hit is unresolved.** That
      is an M7 problem, stated now because M7 will meet it on its first run and
      the arithmetic should not be a surprise. The distribution:
      `closure.missing_reference` 1,022, `closure.ambiguous_reference` 76,
      `closure.remote_resource` 50, `closure.escaping_reference` 5. The bulk is
      documentation naming example files — `run.json`, `install.sh`,
      `package.json`, `src/secrev/x.py` — which is honest low precision under
      P4, where a false positive costs a paragraph and a miss is a silent gap.
      **The question M7 has to answer is whether P4's "every candidate is
      resolved" admits resolving a *class* in one paragraph.** It is not a
      question M5 may answer, because the answer is a triage rule.
      The first measurement was 3,692, every one a document citing another by
      name — `STACK.md` alone 415 times, because a mention inside `src/secrev/`
      resolved to `src/secrev/STACK.md`. That was fixed in M5 rather than
      deferred: a reference is now resolved relative to the referring file, then
      relative to the target root, then by filename when it names no directory,
      because those are the three conventions that actually exist. A signal that
      is always on is H-1's habit in a new place.

### Harness findings raised during M5

- [ ] **Nothing asserts that the current milestone has a ledger, or that a named one exists.**
      Found by the owner's question "is everything in the milestone?", and the proof is this file:
      `BRIEF_M5.md` §1 named `.claude/TASKS_M5.md` as the home of the harness rule for a full commit
      before the file existed — a rule pointing at nothing, in the document that sets the rule. The
      dangling reference is fixed by this file existing. **The assertion that would stop it
      recurring is not written**, and under the rule above it should not be: it is new harness work,
      not a defect in what M5 adds. The shape it would take, so whoever builds it does not have to
      rediscover it: `attack.py` already reads every brief for unticked boxes, so reading each
      brief's `.claude/TASKS_M*.md` references and asserting the targets exist is the same walk —
      and the stronger version also asserts a ledger exists for the milestone the marker names,
      which is the half that would have caught this one.

---

## Carried into M5, open, and not scheduled

Each of these was live in `BRIEF_M4.md` §6 Q5 when M4 closed. They are restated here with what
changed, because "still open" written in a closed milestone's brief is a sentence nobody reads
again.

- [x] **The single-read architecture and its TOCTOU window — DECIDED (2026-10-07, delegated by the
      owner). M5 records the class and closes it for the consumer M5 itself adds.**

      The window: four consumers re-read every file after `inventory` has already read it. The
      *decisions* travel on the entry — language, binary, size, digest — but the bytes do not, so a
      file replaced between the two reads is swept as content the inventory never classified. In a
      tool whose thesis is that a hostile target must not be able to hide code, the damage is not
      abstract: `window_sha256` would identify content the reviewer never saw. `closure.py` makes
      it a fifth consumer.

      **Three options, and why the middle one is wrong for M5.**

      1. *Record and move on*, as M4 did for the fourth consumer. Consistent, and it is also how a
         window stays open across four milestones while each one notes it.
      2. *The single-read architecture* — bytes travel on the entry. Its blocker is not effort but
         an unbounded claim: `--max-file-bytes` bounds a single file at 5 MiB and **nothing bounds
         the total**, so "hold the bytes" is a memory design with a streaming alternative, not a
         patch. That is why M4 declined it and why M5 declines it too.
      3. *Verify on read* — the consumer recomputes `inventory.content_sha256` over the bytes it
         just read and compares against `entry.sha256`. A mismatch means the file changed under the
         review. This closes the half that matters, which is the **silence**, for one hash pass over
         bytes already in memory, and `FileEntry.sha256` already exists for it
         (`inventory.py:242`, computed at `:496`).

      **The decision: (1) for the four existing consumers, (3) for `closure.py`.** Retrofitting (3)
      into `sweep.py`, `surfaces.py`, `recon.py` and `structure.py` is four files `BRIEF_M5.md` §2
      does not list, and the owner set this milestone's narrow rule hours before this question was
      asked — M4 lost eighteen of twenty-two commits to exactly the reasoning "it is cheap and we
      are here anyway". But `closure.py` is *new*, and the harness rule's own exception is "a defect
      in something M5 itself adds". A fifth silent window, added knowingly, is that defect. So the
      newest consumer verifies its own read from the first commit, which costs no other file and
      leaves a **worked example** rather than a proposal for whoever retrofits the rest.

      On a mismatch `closure.py` reuses Q1's mechanism rather than inventing one: the member is an
      unresolvable closure member, recorded in `hits.jsonl` under `source: closure` with the reason
      that its content changed during the review, so FR-4.3 refuses to render a report while nobody
      has looked at it. That is the same argument Q1 settled — the ledger is the only mechanism here
      that makes skipping impossible.

- [ ] **Retrofit verify-on-read into the four existing consumers.** The shape is decided above and
      `closure.py` is the precedent; what remains is four files and one sub-question the owner or a
      later milestone should answer rather than have assumed: whether a mismatch in a *detection*
      source is a ledger candidate (as for closure), a `coverage_gaps` line, or exit 3. It has
      exit-code and contract consequences, which makes it `STACK.md` §3 territory rather than an
      implementation detail.
- [ ] **Whether `src/secrev` is *held* to importing no process module.** A `STACK.md` §2.1
      amendment, and the owner's to take: §2.1 forbids a shell *string*, not the module, and
      `self_check.py` needs `subprocess` in `ALLOWED_IMPORTS` to pass its own control test. The
      stricter reading is defensible. Nothing in M5 depends on the answer.
- [ ] **HARNESS-CI — the approval gate for protected paths after the code leaves the machine.** An
      open M2 task (`.claude/TASKS_M2.md`, HARNESS-CI). Accepted in M3.5, unbuilt.
- [ ] **HARNESS-FS — confinement of the test run.** The same ledger. Until it exists, the
      interpreters and tool directories the gate executes are **detected rather than prevented** —
      `scripts/protected_snapshot.py` watches `bin/` and `pyvenv.cfg` of both environments, and says
      in its own docstring that watching is not confining. This is the task that closes the class M4
      spent eighteen commits narrowing.
- [ ] **The stale-mechanism lint, fourth enforcement shape.** The owner's proposal: once a
      deprecated name is on a derived list, require it to appear only on a line carrying a record
      marker, so "historical" becomes machine-readable. Three earlier shapes are in
      `.claude/TASKS_M3.5.md`. Its stated limit is the reason it is not a complete answer and is
      recorded with it: **it cannot catch a claim that is true for the old reason and phrased
      without the old name** — the `big.js` comment, which no name-based search reaches. Harness
      work, so the rule above applies: not scheduled into M5.
- [ ] **A symlinked *ancestor* of an interpreter is outside the replaceability walk.** The reasoning
      sits beside the walk in `.claude/hooks/lib/syspy.sh` rather than only here: the configuration
      cannot be created by the reviewed code, and a component-by-component canonicaliser in `sh` is
      code whose bugs are silent in the dangerous direction, in the one function every guard's
      integrity rests on, which could not be tested by an unprivileged test.

## Closed in `m4/close`, listed so they are not re-raised

The five findings M4's scope freeze deferred are **fixed**, with the detail in `BRIEF_M4.md` §6
(i)–(v): a watched file made unreadable, the child's exit status, system git configuration,
path normalisation in the guards, and a failed `ask` exiting non-blocking.
