# M3 task ledger — the threat-model layer

Scope: `BRIEF_M3.md`. Mechanism: `STACK.md`. Source of the structure: PRD §8 in full, FR-1.5,
FR-2.1–2.3, AC-4. Receipts go in `.claude/receipts.md`.

M3 writes prose. Nothing here produces a deterministic artifact, so NFR-3 has no claim on it and
the golden tests are unaffected — which also removes the safety net M1 and M2 leaned on. What
replaces it is the Definition of done's demand that every mandatory question be answerable from
something the tool already emits, or be marked as waiting for a phase that does not exist.

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
