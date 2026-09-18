# Brief — M4: The Structural Source

The third and last of the three peer candidate sources (D-11). `sweep.py` asks whether a token is
present; `surfaces.py` asks what is reachable; `structure.py` asks what *shape* the code has.

**This is a core capability of v1, not a deferred gap** (FR-3.5). The three highest-value questions
from the founding review — is this validation a denylist, is a permission set after creation rather
than atomically, does this write reach a location an agent auto-loads — are all questions about
shape. A regex catalog cannot answer any of them. Treating structural analysis as a later
enhancement would leave the system's most important checks permanently unowned, and the founding
finding of this project was itself a denylist bypass.

`BRIEF_M3.md` §1 deferred this milestone with a reason worth carrying into it: *"writing the
analysis while writing the questions produces rules shaped by what is easy to detect — P11 in the
small."* The questions are now fixed in `threat-models/` and in FR-3.6. **The analysis is written
against them, never the reverse.** If a rule is hard to implement, that is a finding about the
rule's cost, recorded — not a reason to narrow the question until the implementation is easy.

Binding text, read before this was written: PRD FR-3.5, FR-3.6, FR-3.7, NFR-3, NFR-6, §13's M4 row;
`STACK.md` §7 (the `Parser` interface) and §5 (determinism).

---

## 1. Scope

**In:** `structure.py`, `_structure.yaml`, `secrev structure <target>`, the four FR-3.6 rules, their
fixtures and goldens, the determinism coverage, and the scope-guard rules for this milestone.

**Python only.** `STACK.md` §7 is explicit: *"Do not adopt tree-sitter in v1 — Python-only is an
acceptable v1 position; a half-built multi-language layer is not."* Every closure member in another
language is a **recorded coverage gap** (FR-3.8), never silence.

| Not now | Why | When |
|---|---|---|
| `closure.py`, `_instruction.yaml`, `_manifest.yaml` | The closure is a larger question than an entry point, and the packs are a catalog change | M5 |
| `SKILL.md`, phase ordering, the Phase 2 gate | Writing the enforcement before the thing enforced is a procedure written against a guess | M6 |
| `verify_ledger.py` and the frozen data contracts | The gate that blocks a report on unresolved candidates needs all three sources emitting first | M7 |
| `subagent.md`, `hook.md`, `agent-config.md` | AC-4 says adding an archetype is cheap; proving it inside the milestone that adds a *source* proves nothing about either seam | M8 |
| tree-sitter, or any second language | `STACK.md` §7. Adding it later must not touch rule logic — that is what the `Parser` interface is for, and an unused interface with one implementation is the correct v1 state | v2 |
| Cross-function dataflow | FR-3.7 is explicit: FR-3.6 operates **within a function body**. Tainted input reaching a sink through intermediate calls stays invisible, and the report's caveats section says so until it ships | v2 |
| Severity, triage, or deciding whether a hit is real | A structural candidate is a question, exactly as a pattern hit is (FR-3.2). Nothing here concludes | M7+ |

**No new patterns and no new surface kinds.** If a structural rule wants a pattern that does not
exist, that is a finding about the catalog, recorded — not a pack edited here.

---

## 2. Deliverables

| File | Owns | Must not know about |
|---|---|---|
| `src/secrev/structure.py` *(new)* | The four FR-3.6 checks as AST visitors, over `inventory.walk`. Ids via `ids.assign`. Returns records. | `sweep`, `surfaces`, `catalog`, `kinds` — the sources are peers and none imports another (D-11, Q2 of M2) |
| `src/secrev/parser.py` *(new, see §6 Q3)* | The `Parser` interface `STACK.md` §7 requires, with `ast` as the sole implementation | Any rule logic. The whole point is that a second parser changes nothing above it |
| `structure/_structure.yaml` *(new, see §6 Q1)* | Rule id, layer, precision, question, references — and the **parameters** each check reads | How any check works |
| `src/secrev/structure_rules.py` or equivalent loader | Strict validation, exit 2 naming the offending rule id, as `catalog.py` and `kinds.py` do | — |
| `src/secrev/cli.py` | `secrev structure <target>`, its own block of `hits.jsonl`, the correct `run.json` | The rules |
| `src/secrev/recon.py` | A `coverage_gaps` line for every language present with no structural coverage | `structure` — recon is a peer (P11) |
| `tests/test_structure.py`, goldens, fixtures | Determinism, stable ids, a positive **and** negative fixture per rule | — |
| `.claude/hooks/lib/paths.sh`, `tests/harness/attack.py` | `is_nfr3_path` += `structure.py`, **before the file exists** | — |
| `.claude/hooks/scope-guard.sh` | M4's own rules, and the `ast` objection scoped so it does not fire on the milestone that owns the AST | — |

---

## 3. The shape of the work

**The data/code split is hybrid, decided by the owner before implementation.** `_structure.yaml`
holds the id, layer, precision, question, references, and the **parameters** — which function names
count as validating, which calls are sinks, which resource-creating calls pair with which
permission-setting ones. `structure.py` holds four AST visitors that read those parameters.

That satisfies NFR-6 in the sense that matters: **a fifth rule of an existing shape is a data
edit**, and tuning any of the four is a data edit. It stops short of inventing a description
language for AST shapes, which would be a milestone in itself — and one designed around four known
rules, which is P11 in the small, exactly what `BRIEF_M3.md` warned this milestone against.
**Where it stops short is stated rather than implied:** a rule of a genuinely new *shape* needs
Python. That limit belongs in the file, not in a reviewer's head.

**The four rules (FR-3.6), each a question and not a verdict:**

1. **Order-of-operations** — a permission-setting call following, rather than fused with, the
   creation of the same resource. The TOCTOU shape.
2. **Decision shape** — a validation function whose control flow branches over a literal collection
   and returns a boolean. The syntactic signature of a denylist (P3).
3. **Unvalidated reach** — a write or execution call whose path argument does not pass through a
   function identified as validating.
4. **Sink adjacency** — an interpolated or concatenated value flowing into a dangerous call within
   a single function body.

**Determinism is not negotiable here.** `structure.py` is named in NFR-3's list. AST traversal order
is deterministic for one Python version, but *rule* order, node ordering within a rule, and the
ordinal grouping are all this milestone's to fix — and fixing them wrong invalidates every
verification recorded above (D-4). The golden test comes **before** the generator, as it did for
`sweep.py` and `surfaces.py`, and `is_nfr3_path` gains `structure.py` before the file exists.

**One read per file, and the walk's decisions honoured.** `structure.py` is the fourth consumer of
`inventory.walk`. It skips exactly what the other two skip — binary, symlink, unreadable,
non-regular, oversized — or the three sources disagree about scope and only one of them says so.
The TOCTOU window between `inventory`'s read and a source's read is recorded at the other two sites
and applies here identically; see §6 Q5.

---

## 4. Definition of done

- [ ] **A1 — Each of the four FR-3.6 rules detects its shape**, with a positive fixture that matches
      and a negative fixture that does not. Evidence: the fixture pair per rule, and the negative
      failing first against a deliberately over-broad draft.
- [ ] **A2 — The negative fixture separates the shape from its neighbours.** Order-of-operations
      must not fire on a fused create-with-mode call; decision shape must not fire on an allowlist
      that happens to branch over a literal; unvalidated reach must not fire where the validator is
      called; sink adjacency must not fire on a literal string.
- [ ] **A3 — A rule is a question.** No record concludes anything, and the `question` field reads as
      one (FR-3.2). A rule whose question can be answered from the record alone is misfiled.
- [ ] **B1 — Adding a fifth rule of an existing shape is a data edit only.** Evidence: add one, show
      the diff touches no `.py`. This is NFR-6's actual test, and it is the one AC-4 uses for
      archetypes.
- [ ] **B2 — The loader refuses a malformed rule file with exit 2, naming the offending rule id**,
      as `catalog.py` and `kinds.py` do. A silently ignored typo is a check that disappeared.
- [ ] **B3 — The `structure.` namespace is closed from both sides**, as `surface.` is: the loader
      requires it, and `catalog.py` refuses it. A `rule_id` in `hits.jsonl` names one question.
- [ ] **C1 — Two runs are byte-identical**, and adding an unrelated file moves no existing candidate
      id. Automated in `scripts/determinism_check.py`, which the gate runs.
- [ ] **C2 — `structure.py` is in `is_nfr3_path` before it exists**, so the determinism guard is not
      silent on the file it most needs to watch.
- [ ] **C3 — The cross-platform digest comparison covers the structure block**, as it covers the
      pattern and surface blocks.
- [ ] **D1 — Records carry `source: structure`** and join the one ledger as a third block, replacing
      only their own (M2's Q1 answer).
- [ ] **D2 — `structure.py` imports no other source.** Evidence: the import list.
- [ ] **E1 — Every language present with no structural coverage is a `coverage_gaps` line**
      (FR-3.8). Python-only is a stated position, and silence about the rest is the false assurance
      this project exists to prevent.
- [ ] **E2 — FR-3.7's limit is stated in the artifact, not only here.** Cross-function dataflow is
      invisible; a reader of `recon.json` must see that without reading this brief.
- [ ] **F1 — The tool runs on itself** and the result is read, not assumed: `secrev structure .`,
      with every candidate resolved or recorded.
- [ ] **F2 — Every document claim this milestone makes is true or gone**, searched with
      `git grep -n "<old name>"` from the root, no pathspec — the rule `CLAUDE.md` carries, applied
      to this milestone's own mechanism names.
- [ ] **G1 — `scope-guard.sh` has M4 rules**, and the `ast` objection does not fire on the milestone
      that owns the AST. A guard that objects to the work it exists to permit teaches people to
      click through it, which is the reasoning M2 already recorded for `surfaces`.
- [ ] **G2 — The marker moves to `M4` only after G1**, never before (H-6).
- [ ] Both gates green; self-application clean; every golden regenerated deliberately and every
      changed line explained.

---

## 5. Notes for the implementer

**Order matters, and it is not the alphabetical order of §2.** The determinism decisions come
first: `is_nfr3_path`, then the golden test, then the rules, then `cli.py`. A determinism check
written after the generator is a retrofit onto code composed without it, and NFR-3 is the one
requirement that does not survive being retrofitted (D-4).

**The `ast` guard fires today.** `scope-guard.sh` refuses `import ast` outside `scripts/` with the
note *"that is structure.py, M4"*. Lifting it is part of G1 and must be scoped to M4 rather than
removed — the objection is still right for M1, M2 and M3.

**Write the negative fixture first where you can.** M1's `net.bind_all` was found broken by its
negative fixture one commit after it was written; M3.5's two rejected `log.sensitive` repairs both
agreed with all seven positives. A rule is demonstrated by what it declines.

**Do not tune toward precision.** `precision: low` is first-class (BRIEF_M1.md §4). Under P4 every
candidate is resolved anyway, so a false positive costs a paragraph and a miss is a silent gap.

---

## 6. Raised before implementation, for the owner

Named, not resolved (`BRIEF_M1.md` §8).

**Q1 — Where does `_structure.yaml` live?** The PRD's §7 tree puts it at `patterns/_structure.yaml`.
M2 set the opposite precedent: surface kinds went to `surfaces/` of their own, decided in
`TASKS_M2.md` C-1, because they are a different question with different semantics under the same
loader discipline. Structural rules are a third such question. Following the PRD tree puts three
unrelated schemas in one directory that `catalog.py` owns; following M2's precedent contradicts the
PRD tree. **Either way it is a document correction, not a code decision.**

**Q2 — What window does a structural candidate carry?** `lines-20` on pattern records, `decl-20` on
surface records, both ±20 lines under names that keep them incomparable (`STACK.md` §5, M2's C-2). A
structural finding's natural span is the **function body** — which is what makes it structural. A
third name (`body`?) is a `STACK.md` §5 amendment, and choosing `lines-20` instead would make two
different spans comparable, which is the exact defect C-2 exists to prevent.

**Q3 — Where does the `Parser` interface live?** `STACK.md` §7 requires it but does not place it. Its
own module keeps `structure.py` free of parsing concerns; inside `structure.py` avoids a module with
one class and one implementation. The test that matters is Q3's own premise: *adding tree-sitter
later must not require touching rule logic.*

**Q4 — Does `recon.json` gain a structural coverage-gap list of its own?** `_SURFACE_GAPS` is fixed
text in `recon.py`, deliberately not derived from the kinds, because recon is a peer of the surface
source and does not import it (P11). The same reasoning says structural gaps are fixed text too —
but there will then be two such blocks, and a reader should be told which source each belongs to.

**Q5 — Carried from M3.5, none of them resolved there.**

- The **single-read architecture**. Three consumers re-read every file after `inventory` already
  read it; the decisions are carried forward, the read is not, so a file replaced between them is a
  TOCTOU window. `structure.py` makes it four. Closing it means the bytes travel on the entry,
  which holds a tree in memory — an architecture decision, not a hardening patch.
- Whether `src/secrev` is **held** to importing no process module — a `STACK.md` §2.1 amendment.
- The **HARNESS-CI approval gate**, an open M2 task.
- A deliberate pass over **`.claude/skills/`**: five of nine were never read, and three of the four
  that were carried false claims — two of them M1-era errors about the candidate id, in files loaded
  into every session as instruction.
- Whether `.claude/skills/` belongs inside **F1's scope** or a box of its own. Every sweep in M3.5,
  F1's included, stopped at the repository's own documents.
- **Enforcing the stale-mechanism rule in a gate.** Three candidate shapes are in
  `.claude/TASKS_M3.5.md`; all three need the same missing piece — a machine-readable way to say
  *"this sentence is a record, not an instruction"*.
