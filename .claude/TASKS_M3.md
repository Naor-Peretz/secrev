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

---

- [x] **TASK-M3-000 — The marker moves, and the guard has rules first.** `scope-guard.sh` gains an
      M3 branch that refuses the scoped tree with M3's own reason rather than falling through to
      `refuse_no_rules`, whose message ("this milestone needs its own rules added here") is false
      once the rules exist. `attack.py` asserts the refusal and its message, reading stderr rather
      than stdout — the first draft read stdout, which carries `ask` payloads, and passed nothing.
      Marker `M2` → `M3` only after the rules landed: moving it first write-locks the scoped tree
      (H-6), which is exactly what happened between M1 closing and `BRIEF_M2.md` being written.
      *Accept:* 108 guard assertions; M3 refuses `src/` and `patterns/` naming its own remit.

- [ ] **TASK-M3-001 — `_agentic-core.md`.** The eight mandatory sections of PRD §8.1, and nothing
      archetype-specific. The expensive file: written badly, every overlay restates it and they
      drift, which is §8's own reason for two layers.
      *Accept:* all eight sections present, each specific enough that two reviewers would look at
      the same places; no sentence that only applies to skills or only to MCP servers.

- [ ] **TASK-M3-002 — `skill.md`.** The six sections of §8.2 in order. §8.2 item 3 requires the
      activation description's breadth by name. M2's own run is the evidence: ten skill activations
      found in this repository, one of them a false positive — a `description:` line inside a
      documentation template — which is precisely what the applies-when section has to
      disambiguate.
      *Accept:* six sections in order; known-good implementations present, not deferred.

- [ ] **TASK-M3-003 — `mcp-server.md`, and AC-4 demonstrated.** §8.2 item 3 requires *tool return
      values* by name as a sink: they land in an agent's context and become instructions (P8).
      Written after `skill.md` so the diff can show `_agentic-core.md` untouched — AC-4 proven by
      doing it, not asserted.
      *Accept:* the core is byte-identical across this task's commit; no script changed.

- [ ] **TASK-M3-004 — `_classifier.md`, per D-2.** If it lands here: sorts by hand the three shapes
      this repository already knows — a skill with a `SKILL.md`, an MCP server declared in
      `.mcp.json`, and one artifact that is both. Composition is the norm (FR-1.5, §8.3).

- [ ] **TASK-M3-005 — Close.** DoD ticked; `STACK.md`/PRD corrections raised during the work go
      through spec-guard; receipts. The marker moves only after `BRIEF_M4.md` and its scope-guard
      rules exist.
