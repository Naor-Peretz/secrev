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

- [ ] **The single-read architecture, and its TOCTOU window — and M5 makes it worse.** Four
      consumers re-read every file after `inventory` has already read it: the decisions travel on
      the entry, the bytes do not, so a file replaced between the two reads is a window. `closure.py`
      is the **fifth**. M4 recorded that it added the fourth; recording the fifth and moving on is
      the consistent choice, and it is also how a window stays open across three milestones.
      **Raised with the owner and not yet answered**, deliberately left here rather than decided:
      closing it touches `inventory.py`, `sweep.py`, `surfaces.py` and `recon.py`, four files
      `BRIEF_M5.md` §2 does not list, so admitting it is a brief edit and not an implementation
      detail. Until it is answered, M5 records that it adds a fifth consumer.
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
