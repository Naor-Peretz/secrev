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

**And, by owner decision (2026-09-22), one class of harness hardening**: code that test code
plants and that later runs inside a guard. This does not belong to a source milestone — §6 Q5 says
so in as many words — and it is here because four external review rounds found live vectors in
machinery *this milestone added*, and the owner chose to fix them before merge rather than let
them reach `main` while a hardening milestone waits to be opened. The alternative considered and
declined was M3.5's precedent: close M4 on the structural source and open M4.5 for this.

**Scope freeze, part of the same decision.** What enters this milestone is that one class, plus
the F2 corrections its findings make necessary. **Every further finding from 2026-09-22 onward is
recorded and not fixed here**, however small, because "fix it before `main`" is what turned one
review round into five. `.claude/TASKS_M2.md`'s HARNESS-CI and HARNESS-FS remain the owners of
what is left.

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
| Re-windowing the **pattern** source from `lines-20` to `block-20` | It moves every id already in `hits.jsonl` and expires every verification recorded against one (FR-4.6). Doing that in the milestone that also adds a source means a moved id has two possible causes and no way to tell them apart | Its own milestone |

**That last row is a correction, and it is mine.** Four places said the pattern window moves to
`block-20` *in M4* — `STACK.md` §5, `BRIEF_M1.md` §4, `src/secrev/sweep.py` and
`tests/test_sweep.py`, the last two carrying it since M1 with a test guarding it. This brief was
written without noticing any of them, so the milestone shipped a scope omission in the same commit
that scoped it. The owner's decision is that the migration is **not M4's**; all four sites are
corrected in this branch, and M4 gives `block-20` to structural records only, which re-identifies
nothing because those records are new.

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

**The `Parser` returns a vocabulary, not a syntax tree** — taken during
implementation, recorded here because it is the decision that determines whether §7's interface is
real. `parse()` could have returned an `ast.Module` for the rules to walk; they would then be
written against CPython node types, and the honest answer to Q3's own premise — *adding a second
language must not touch rule logic* — would be "it would mean rewriting all of it". So the seam
carries `Unit` → `Function` → `Call` / `Assignment` / `MembershipTest` / `Return`, in terms every
language has.

This is **not** the AST description language §3 refuses below, and the two are close enough to be
worth separating. That refusal is about putting *rule logic in data* — a language in which a new
rule shape is describable without code, which would be designed around the four rules we already
have. This is a fixed vocabulary in code, scoped to exactly what those four ask, with no ambition
to describe a fifth. Two consequences are enforced rather than asserted: `ast` is imported by
`parser.py` alone (`tests/test_parser.py`), and no `ast` node is reachable from a parsed unit —
without both, the interface is a comment and `ALLOWED_IMPORTS` admitting `ast` package-wide would
be a widening with nothing holding the other end.

Two further positions the implementation had to take, both refusing a silent gap rather than
following the requirement literally. **Top-level code is a `Function` named `<module>`**: FR-3.7
scopes the rules to a function body, and read strictly that exempts every top-level script, which
is most of what an agentic artifact is. **A nested definition is its own body**, so a sink inside a
helper is never reported against the enclosing function — a record pointing at a body that does not
contain the call is worse than no record.

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

- [x] **A1 — Each of the four FR-3.6 rules detects its shape**, with a positive fixture that matches
      and a negative fixture that does not. Evidence: the fixture pair per rule, and the negative
      failing first against a deliberately over-broad draft.
- [x] **A2 — The negative fixture separates the shape from its neighbours.** Order-of-operations
      must not fire on a fused create-with-mode call; decision shape must not fire on an allowlist
      that happens to branch over a literal; unvalidated reach must not fire where the validator is
      called; sink adjacency must not fire on a literal string.
- [x] **A3 — A rule is a question.** No record concludes anything, and the `question` field reads as
      one (FR-3.2). A rule whose question can be answered from the record alone is misfiled.
- [x] **B1 — Adding a fifth rule of an existing shape is a data edit only.** Evidence: add one, show
      the diff touches no `.py`. This is NFR-6's actual test, and it is the one AC-4 uses for
      archetypes.
- [x] **B2 — The loader refuses a malformed rule file with exit 2, naming the offending rule id**,
      as `catalog.py` and `kinds.py` do. A silently ignored typo is a check that disappeared.
- [x] **B3 — The `structure.` namespace is closed from both sides**, as `surface.` is: the loader
      requires it, and `catalog.py` refuses it. A `rule_id` in `hits.jsonl` names one question.
- [x] **C1 — Two runs are byte-identical**, and adding an unrelated file moves no existing candidate
      id. Automated in `scripts/determinism_check.py`, which the gate runs.
- [x] **C2 — `structure.py` is in `is_nfr3_path` before it exists**, so the determinism guard is not
      silent on the file it most needs to watch.
- [x] **C3 — The cross-platform digest comparison covers the structure block**, as it covers the
      pattern and surface blocks.
- [x] **D1 — Records carry `source: structure`** and join the one ledger as a third block, replacing
      only their own (M2's Q1 answer).
- [x] **D2 — `structure.py` imports no other source.** Evidence: the import list.
- [x] **D3 — Records carry `window_spec: block-20`**, and the window is the enclosing function or
      block rather than ±20 lines. The name is not new — `STACK.md` §5 has held it since M1 for
      exactly this span (§6 Q2). Using `lines-20` here would make two differently-shaped windows
      comparable, which is the defect C-2 exists to prevent; inventing a third name would
      contradict §5.
- [x] **E1 — Every language present with no structural coverage is a `coverage_gaps` line**
      (FR-3.8). Python-only is a stated position, and silence about the rest is the false assurance
      this project exists to prevent.
- [x] **E2 — FR-3.7's limit is stated in the artifact, not only here.** Cross-function dataflow is
      invisible; a reader of `recon.json` must see that without reading this brief.
- [x] **F1 — The tool runs on itself** and the result is read, not assumed: `secrev structure .`,
      with every candidate resolved or recorded.
- [x] **F2 — Every document claim this milestone makes is true or gone**, searched with
      `git grep -n "<old name>"` from the root, no pathspec — the rule `CLAUDE.md` carries, applied
      to this milestone's own mechanism names.
- [x] **F3 — `.claude/skills/` is read, and every checkable claim in it is true or gone.** Its own
      box rather than part of F2, because the anchor is different: **P8** makes prose reaching an
      agent's context behaviour-defining, so a false sentence in a skill is a defect in the reviewer
      rather than a documentation lapse. Nine files; **five have never been read at all**, and three
      of the four that were carried false claims — two of them the same M1-era error about the
      candidate id, word for word, in files loaded into every session as instruction. Scope is
      **checkable** claims — paths, commands, field names, the id tuple — not prose quality. Read
      as `.claude/skills/`, corrected mid-pass to **everything under `.claude/` that reaches an
      agent's context**: skills, agents, commands, and the strings a hook prints. See the scope
      note below for why the narrow reading was itself the defect. Every
      sweep in M3.5, F1's included, stopped at the repository's own documents, which is why this is
      still open after six review rounds.

      **Done. Nine files read, seven defects in six of them**, and one of the seven was a defect in
      the codebase that a skill had been right about all along:

      1. **`testing-contract` and `pattern-author` both cited `STACK.md` §8** for a testing rule.
         §8 is Harness discipline; §9 is Testing. The same wrong number in two files is a class.
      2. **`testing-contract`'s example called `run_sweep(FIXTURES, workspace=tmp_path)`** and then
         compared a file the call was supposed to have written. `cli.run_sweep` exists, takes
         `(target, workspace, catalog, …)`, and is not what a golden test calls: the sources return
         serialised text and `cli.py` writes. Replaced with the form the real goldens use. *(This
         entry read "no such function" until F2's own sweep; the function exists and the signature
         does not, and overstating a finding is the same defect as understating one.)*
      3. **The suite did not follow `testing-contract`'s own `read_bytes` rule.** Five golden
         comparisons used `read_text`, three of them in tests named `..._byte_for_byte`.
         `read_text` opens in universal-newline mode, so with no `.gitattributes` a clone with
         `core.autocrlf` on compares against a golden it has just silently repaired. All five are
         now byte comparisons, and
         `test_the_old_text_comparison_would_have_passed_on_a_crlf_golden` is the control that
         measures the defect rather than asserting it. **The skill was right and the code was
         wrong** — the first hit in this sweep that went that direction.
      4. **`eval-harness` attributed a false-positive-rate metric to PRD §12.2**, which has none.
         The absence is deliberate: `precision: low` is first-class and `BRIEF_M1.md` §4 forbids
         tuning toward precision, so the skill named an eval target that pushes the trade this
         project refuses. Replaced with §12.2's actual metrics.
      5. **`secrev-invariants` named `SKILL.md` as one of the three files that defeated
         code-detection.** The ledger records `AGENT.md`, `prompt.txt` and an extensionless
         `setup`; `SKILL.md` was a test parameter. It also conflated three *attempts* with three
         *files*.
      6. **`debugging` said the gate has five stages.** It has nine.
      7. **`strategic-compact` ships `suggest-compact.sh` with `#!/bin/bash`** against §1 and §8 —
         the only non-POSIX shebang in fourteen shell scripts, and the only one this project did
         not write. Nothing checked shebangs anywhere, so §1's rule had no control behind it;
         `test_every_shell_script_is_posix_sh` is that control (123 -> 124 assertions), measured
         red on a planted probe and then green, and narrowed after its first draft fired on
         `paths.sh`, which correctly has no shebang because it is sourced.

      **`compile` and `marshal` were enforced by `scripts/self_check.py` citing "STACK.md §2.1"
      while §2.1 listed neither** — found because `secrev-invariants` repeated them as if it were
      quoting. Corrected in §2.1 through spec-guard: the rules were never in dispute, but two
      places attributing them to a paragraph that did not say them is how a rule becomes
      unfalsifiable.

      **F3 was scoped wrongly, and widening it found the worst defect of the pass.** The box said
      `.claude/skills/` because that is where the previous round's defects were — which is
      detection deciding scope, **P11 applied to our own process**, in the milestone whose whole
      subject is P11. `.claude/agents/`, `.claude/commands/` and the hooks' printed strings were
      never in it. Widening to everything under `.claude/` that reaches an agent's context found
      the M1-era **wrong candidate id** `(relative_path, line, rule_id, ordinal)` alive in four
      more places after six review rounds and a dedicated pass: `determinism-guard.sh` printed it
      **to the user** beside the NFR-3 checklist, `python-reviewer.md` prescribed it four bullets
      below its own rule forbidding a line number in a hash input, `gate-resolver.md` gave it as
      the thing to "fix" `ids.py` *to*, and `commit.md` used it as the model of a good commit
      message. Found by grepping the tuple itself rather than the files — the M3.5 repair had been
      applied to the two files someone happened to open. Three sites remain and are correct: two
      historical records and record *sort* order, where `line` genuinely belongs.

      **One defect is recorded and deliberately not repaired.** `suggest-compact.sh`'s counter
      cannot work: `$$` is the script's own pid, a hook is a fresh process every time, so the
      counter file is renamed on every invocation and neither threshold is ever reached. Its
      `SKILL.md` described that behaviour in three numbered points. The behaviour claim is
      corrected and the logic is left alone — it is vendored third-party content, it is not wired
      into `.claude/settings.json`, and rewriting it is not this milestone's business.
- [x] **G1 — `scope-guard.sh` has M4 rules**, and the `ast` objection does not fire on the milestone
      that owns the AST. A guard that objects to the work it exists to permit teaches people to
      click through it, which is the reasoning M2 already recorded for `surfaces`. Evidence:
      `fd2d00f`, and three assertions in `attack.py` exercising the new case (120 -> 123).
- [x] **G2 — The marker moves to `M4` only after G1**, never before (H-6). Evidence: the ordering
      within `fd2d00f` — brief, then rules, then assertions, then `.claude/MILESTONE` last.
- [x] **G3 — `structure/` is protected and scoped in the change that creates it**, as `surfaces/`
      was in M2 and `threat-models/` in M3 — H-4 in `STACK.md` §8, `PROTECTED` in `bash_guard.py`,
      and `is_scoped_path`. It needs an entry of its own only because Q1 put the rule file in a
      directory of its own; under the PRD's original tree `patterns/` would have covered it, which
      is a consequence of that decision worth naming rather than discovering. **The M4 scope case
      now answers `structure/` by name**: it ended in a catch-all permit, so
      `test_m4_permits_the_source_it_builds` had been green for a directory `is_scoped_path` had
      never heard of. A permit assertion cannot tell "allowed by name" from "allowed by silence";
      `test_scope_guard_covers_structure` is the refusal that can. 125 -> 129 assertions.
- [x] Both gates green; self-application clean; every golden regenerated deliberately and every
      changed line explained.

**Evidence, so a tick is a claim someone can check.** 565 tests (was 501), 129 guard assertions,
mypy across 19 source files, determinism byte-identical with ids stable over all three blocks.

- **A1/A2** — `tests/fixtures/structural/<rule id>/{positive,negative}.py`, eight files, asserted
  in both directions and per rule. Each negative is the rule's *nearest neighbour* rather than an
  unrelated file: the fused `mkdir(mode=…)`, the reversed membership, the validator inside the
  argument, the literal command. **A2 changed a rule while it was being written** — the decision
  shape fired on allowlists and denylists alike, because both branch over a literal and return
  booleans. The direction of the membership is the distinction, `MembershipTest.negated` already
  carried it, and it was a field nothing read until the negative fixture demanded it.
- **A3** — every `question` ends in a question mark, asserted; no record carries a status other
  than `unresolved`.
- **B1** — `test_a_fifth_rule_of_an_existing_shape_needs_no_python` loads a fifth rule through the
  real loader. The `shape` field is what makes it true: parameters are declared per *shape*, not
  per rule id, so a fifth rule of a known shape is data and nothing else.
- **B2** — eight refusals, each naming the rule, plus a control that the valid file still loads.
  The one that matters is the **misspelled parameter**: a missing one raises in the analysis and
  someone notices, an unknown one leaves the analysis reading a parameter that is not there.
- **B3** — the catalog refuses the namespace, and **it did not until this test asked.** `surface`
  was named inline in `catalog.py` from M2, so `structure` was open and a pattern could have taken
  a structural rule id. The reservation now reads from `ledger.RESERVED_NAMESPACES`.
- **C1/C2/C3** — `scripts/determinism_check.py` derives the blocks it requires from `cli.SOURCES`
  rather than listing them, which is why the third was covered by construction; `ci.yml` produces
  the structural block for the cross-platform digest under the same guard as the other two.
- **D1/D2/D3** — `source: structure`, `window_spec: block-20`, and an import list holding no other
  source (`ids`, `inventory`, `ledger`, `parser`, `structure_rules` — the shared record module and
  the parser, never `sweep`, `surfaces`, `catalog` or `kinds`).
- **E1/E2** — `_STRUCTURE_GAPS`, four lines with a `structure: ` prefix, and FR-3.7's limit stated
  first among them. The old line said "structural analysis not implemented (M4)" and would have
  been false the moment this shipped.
- **F1 — the tool ran on itself and found a real defect in `cli.py`.** 32 candidates over this
  repository, nothing unparsed. `_prepare` created the workspace with
  `mkdir(parents=True, exist_ok=True)` and then walked it setting `0o700`, leaving every level at
  the umask between the two calls — 0o775 on the machine M3.5 measured — while that directory
  holds the `match_excerpt` values G-3 exists to make safe. M3.5's E4 fixed the mode they end up
  with and left the window they pass through. Fixed with the fused form the rule's own negative
  fixture demonstrates, and `test_the_tool_does_not_contain_the_shape_it_asks_about` keeps it
  fixed. The remaining candidates in `src/` and `scripts/` resolve as correct by construction:
  every path reaching a sink is built by `workspace_for` and never derived from target content.

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

## 6. Decided before implementation, and what is still open

Q1–Q4 were raised here unresolved (`BRIEF_M1.md` §8) and the owner has since settled all four. The
answers are recorded with their reasons, because a decision whose reason is lost is one that gets
reverted by the next person who finds it inconvenient.

**Q1 — Where does `_structure.yaml` live? → `structure/`, and the PRD tree is corrected.** Not
`patterns/`. M2's precedent holds: a different question with different semantics gets its own
directory under the same loader discipline, which is why surface kinds went to `surfaces/`
(`TASKS_M2.md` C-1). Putting a third unrelated schema under a directory `catalog.py` owns would
make `patterns/` mean "rule files" rather than "the pattern catalog", and `catalog.py` refuses
unknown ids for a living. Because the PRD's §7 tree said `patterns/_structure.yaml`, this is a
**document correction** and was made as one, through spec-guard: §7 now shows `surfaces/` and
`structure/` beside `patterns/`. The §7 tree had never caught up with M2 either — `surfaces/` was
missing from it — so the correction closes both.

**Q2 — What window does a structural candidate carry? → `block-20`.** Not a new name: `STACK.md` §5
has named this spec since M1 — *"`lines-20` for the untightened form, `block-20` once a parser
tightens it to the enclosing function or block"*. The question was asked as though a third name had
to be invented, which it did not; the answer was already binding text, and proposing `body` would
have contradicted it. **No §5 amendment is needed for the name.** What §5 did need is the
correction below.

One consequence, recorded now rather than discovered later: when the pattern source is eventually
re-windowed, pattern and structural records will *share* the name `block-20`. That is correct, not a
C-2 violation. C-2 keeps differently-shaped spans from being compared; two spans of the same shape
sharing a name is what the name is for. Ids stay distinct regardless, because `rule_id` is in the
tuple and the `structure.` namespace is closed against the others.

**Q3 — Where does the `Parser` interface live? → `src/secrev/parser.py`, its own module.** The
objection to a module holding one class and one implementation is real and is outweighed by Q3's own
premise: adding tree-sitter must not touch rule logic. An interface living inside its only consumer
is an interface that can be reached around without anyone noticing, and the reaching-around is
exactly the failure the interface exists to prevent. A one-class module makes the seam visible in
the tree.

**Q4 — Does `recon.json` gain a structural coverage-gap list of its own? → Yes, `_STRUCTURE_GAPS`,
with each line prefixed `structure: `.** Fixed text in `recon.py`, not derived from the rules, for
the same P11 reason `_SURFACE_GAPS` is: recon is a peer of the source and does not import it. With
two blocks now, a reader must be able to tell which source a gap belongs to, and the prefix does
that in the artifact rather than in a convention someone has to know.

**A parser that cannot parse is a gap line and exit 2**, never a skipped file and exit 0. A Python
file that fails to parse is not "no candidates here" — it is a file this source did not review, and
H-1 says the two states must not collapse. This is the same polarity M3.5 spent four rounds
arriving at for unread files: the artifact records what went unexamined, and the exit code keys on
it.

**Q5 — Carried from M3.5. Two have answers; three are still open and are not blocking.**

Answered:

- **`.claude/skills/` gets a pass, and it is F3 above** — its own box, anchored in P8, not folded
  into F1. The reason is in the box.
- **The stale-mechanism rule stays prose for now, with a fourth enforcement shape proposed.** Three
  shapes are in `.claude/TASKS_M3.5.md`; the owner has added a fourth — a lint requiring a
  deprecated name, once it is on a derived list, to appear only on a line carrying a record marker,
  so "historical" becomes machine-readable and everything else becomes a failure. Its stated limit
  is the one that matters and is recorded with it: **it cannot catch a claim that is true for the
  old reason and phrased without the old name** — the `big.js` comment, which no name-based search
  reaches. That class stays a reading problem. Not scheduled into M4; it is harness work and this
  milestone is a source.

  **That last sentence stated the rule this milestone then broke, twice, and §1 now records the
  exception rather than leaving the two to sit side by side.** The rule still holds for the lint
  above: it is harness work nobody's review found running. What §1 admits is narrower — harness
  work where an external review demonstrated live code execution in machinery M4 itself added.
  The distinction is "a reviewer ran it", not "it seemed important", and the scope freeze in §1
  is what stops that distinction from widening again.

Still open, and each is named here so it is not mistaken for settled:

- The **single-read architecture**. Three consumers re-read every file after `inventory` already
  read it; the decisions are carried forward, the read is not, so a file replaced between them is a
  TOCTOU window. `structure.py` makes it four. Closing it means the bytes travel on the entry,
  which holds a tree in memory — an architecture decision, not a hardening patch. **It is not in
  M4's deliverables**: it touches `inventory.py`, `sweep.py`, `surfaces.py` and `recon.py`, four
  files this brief's §2 does not list, so admitting it is a brief edit rather than an
  implementation detail. M4 adds the fourth consumer and records that it did.
- Whether `src/secrev` is **held** to importing no process module — a `STACK.md` §2.1 amendment.
  §2.1 forbids a shell *string*, not the module, and `self_check.py` needs `subprocess` in
  `ALLOWED_IMPORTS` to pass its own control test. The stricter reading is defensible and is the
  owner's to take.
- The **HARNESS-CI approval gate**, an open M2 task.
- **Test code is a write path around every guard** — the residual of M3.5's E3, demonstrated in
  M4's review. `Bash(pytest:*)` was removed from the allowlist, but `sh scripts/check.sh` stays
  auto-approved and runs pytest, and `tests/` is not protected, so a test file could write into
  `threat-models/` or `src/` with no guard in the path. **Decided (owner, 2026-09-22): detect,
  from inside the gate, rather than prevent.** The two preventions on offer — protecting
  `tests/`, or taking the gate off the allowlist — would each have put an approval into daily
  work. Instead `check.sh` snapshots every protected path (content and executable bit) before
  pytest and fails if the suite changed one; legitimate tests write to `tmp_path`, so in
  ordinary use it never fires, and the review's own demonstration now fails the gate before it
  can reach a commit. **A second review broke the first version**: the baseline was a `mktemp`
  file, so a test could re-take it and the stage printed "no protected path changed" over a
  change still in the tree — a false green in the control meant to close E3. The baseline now
  lives only in the checker's memory, with pytest run as its child, so there is no file to find;
  that class is closed, not narrowed. **A third review broke the second**: the listing honoured
  ignore rules, so a test planted `.claude/hooks/shutil.py`, hid it in `.git/info/exclude`
  (unprotected, and absent from `git status`), and the stage stayed green while every later
  commit ran the plant inside the commit checkpoint — Python puts a script's own directory first
  on `sys.path`. Now the listing ignores no ignore rule; the suite runs with its bytecode cache
  outside the tree; every interpreter a hook starts runs `-I`, and `-S` where it is stdlib-only;
  the one import of our own code in a hook loads from source, never from `__pycache__`; and
  Python's startup files in the venv and user site are watched. Following the class found two
  more instances than the review named: `async-check.sh` ran the same suite after *every* edit
  with no snapshot at all, and the checker could be reached through a `.pth` in the venv.
  **A fourth review found that this residue list was not a list of what remains — it was a list
  of what we had thought to look for.** Three more vectors, each confirmed running end to end: a
  clean filter in `.git/config` with `.git/info/attributes`, firing on the auto-approved
  `git add`; `core.fsmonitor`, firing on `git status`; and a global `~/.gitconfig`, reaching
  every other repository on the machine. All three were invisible to the checker *structurally* —
  `git ls-files` lists worktree files, so nothing under `.git/` was reachable by it. Worse, the
  commit checkpoint **executed** two of them, because it shells out to `git diff`: round 3's
  finding one layer out, in the control that replaced hand-staging.

  Now: the checker walks in Python and runs no git at all — the listing was the one child process
  a planted `.git/config` could steer; `.git/` is resolved (it is a file, not a directory, in a
  linked worktree) and then watched whole minus git's own churn; the checkpoint's git calls are
  disarmed — every hook that shells to git, through one shared definition, not only the one where
  a finding was demonstrated — `core.fsmonitor` by name and filters by blanking every configured
  driver through the environment, since a driver's name is arbitrary, a fixed list of options never
  reaches it, and the name may contain the `=` that `-c` splits on; and the suite runs with `HOME` and the global git config redirected, which *prevents* the
  global vector rather than watching it.

  **An internal review of that fix, before it was pushed, found three defects in it** — the same
  shape as every round above, this time in our own work and caught by `python-reviewer` rather
  than by the owner. They are written here rather than only in the ledger because the paragraph
  above would otherwise read as a closure it had not reached. (1) The snapshot recorded a symlink
  by hashing what it *pointed at*, so the one entry a link can be — repointed at another file —
  read as unchanged, and a link to a FIFO hung the gate instead of failing it; it now records the
  target path. (2) `-c filter.<driver>.clean=` splits its argument at the first `=`, so a driver
  named `a=b` set an unrelated key and the planted filter ran straight through the disarming; the
  keys go through `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`, which passes key and value separately.
  (3) In a linked worktree `.git` is a *file*, and a walk of a non-directory returns nothing — the
  whole `.git` half watched zero files while the stage printed its success line; the gitdir and
  its common directory are resolved, and a `.git` file naming nothing refuses (H-1). Worst of the
  three, and the reason they are listed: the regression test for (2) asserted **after** its
  temporary tree was deleted, so it could not fail however the hook behaved — deleting the
  disarming outright left it green. A guard that only exists is the failure this milestone is
  about, and the test for it had the same defect.

  **A second internal review, of those three fixes, found the pattern again — twice in the code
  and twice in the tests.** (4) The FIFO hang was closed for the entries `_walk` collects, and
  `_walk` is not how the global git configs or the venv's `*.pth` files are collected: a named
  pipe at either hung the gate with no exit code at all, measured end to end. The branch moved
  into `_digest`, which all three collectors go through. (5) `core.fsmonitor` was disarmed in
  `commit_review.py`, which runs `git diff` — while the trigger this brief *names* for it is
  `git status`, which `session-start.sh` and `session-end.sh` run, on SessionStart and at the end
  of every turn. The fix had gone to the file where the finding was demonstrated rather than to
  the hooks that make the call. They now share `lib/git_safe.sh`, pinned equal to the Python list,
  with a static assertion that no shell hook calls git without it — which immediately found a
  third hook. (6) `GIT_CHURN` skipped `modules`, the one name in a set documented as "executes
  nothing" that is a submodule's real gitdir, holding its own `config` and `hooks/`. (7) A
  `commondir` naming a non-directory was dropped silently while the branch four lines above it
  refused — the same false green, one branch over. And in the tests: the linked-worktree assertion
  passed with the fix removed on any machine that has a `~/.gitconfig`, because it asserted on a
  list that also contains the global configs; and the new scope-guard "control" used a path the
  guard exits before ever reaching the case it claimed to control. Both are the vacuous-test
  failure recorded above, reproduced inside the round that was correcting it.

  **The owner then found the one that beats all of them: the checker ran under an interpreter a
  test can replace.** `check.sh` and `async-check.sh` invoked `protected_snapshot.py` with
  `.venv/bin/python`. `.venv/` is not a protected root, and what was watched inside it was three
  name shapes in site-packages — not the interpreter. One test overwriting that file, or
  `pyvenv.cfg`, which names the base interpreter, replaced *the program that reports*: the run in
  which it landed finished green, and from the next run on the plant **was** the checker, printing
  the line that says nothing changed. `-I -S` are no answer, being flags to the interpreter that
  was replaced. Every other vector in these rounds put planted code inside a hook; this one put it
  in place of the control, and it arrived through `async-check.sh` too, which runs the suite after
  every edit with no approval at all.

  Both halves are fixed, and neither would have sufficed. The gate runs the checker with the
  system interpreter — it is stdlib-only, every hook already did this, and pytest stays a child
  under the venv — which makes the comparison honest. And `bin/` and `pyvenv.cfg` of both virtual
  environments are now watched, which makes the plant a finding *in the run that lands it* rather
  than a resident the honest checker merely declines to be. The watch is not another name on a
  list: it answers a question the file had not asked, which is "what does the gate execute",
  beside "what runs when Python starts".

  **And the owner's follow-up: `command -v python3` is the same vector one step out.** PATH is
  searched in order, and a developer PATH begins with directories the user owns — three sat ahead
  of `/usr/bin` where this was measured. None held a `python3`, so the lookup landed root-owned;
  a test creating one owns every later run, and redirecting HOME does nothing, because PATH carries
  absolute paths. `check.sh` now tries fixed absolute candidates before PATH's answer, requires the
  one it picks to be *unreplaceable* by the user whose tests are about to run — and prints the
  fact when no such interpreter exists rather than implying the property.

  **The first version of that test asked the wrong question, and the owner caught it.** It was
  `[ -w "$candidate" ]`, which is weaker in two ways: replacing a file needs write permission on its
  *directory*, not on the file — delete the entry and create another — and `-w` follows a symlink,
  so on a link it reports about the target. A `python3` symlink in a user-owned directory pointing
  at a root-owned interpreter therefore passed as safe, was taken by the first pass, and the gate
  printed **no note** — claiming the property about a path that `ln -sf` repoints. Confirmed by
  replacing one. It is not a corner case on macOS: Apple's 3.9 cannot meet the gate's floor, so the
  chosen candidate always comes from PATH, where `/usr/local/bin` is user-owned under Homebrew and
  `~/.local/bin` is by construction. `syspy_replaceable` now tests the file, every ancestor
  directory, and the same for each hop of a symlink chain, with `readlink` and no `-f` so it works
  on macOS, and with parameter expansion instead of `dirname` so a plain file costs no fork at all.

  **The owner then found that the corrected test was still one step short, twice.** (a) Permission is
  not the capability: a directory its owner has closed to itself at mode 0555 answers "no" to `-w`,
  and that owner reaches it with one `chmod u+w` — measured, the file was replaced after exactly
  that. `-O` now sits beside `-w` on the file and on every ancestor; it is a builtin in `dash` and in
  BSD `test`, so the no-process property survives. (b) **Not fixed, and written beside the other
  limits so the gap is not read as coverage:** the hop loop resolves a symlink that is the *final*
  component, not one that is an *ancestor*. Walking `/opt/tool/bin/python3` where `/opt/tool` links
  to `/srv/a/b` tests the link and never `/srv/a`, which the user might own — the same "`-w` answers
  about the target" mechanism, one level out. Two reasons for leaving it: the configuration cannot be
  *created* by the reviewed code, since planting it needs a symlink inside a directory that code
  cannot write, so it must pre-exist; and a component-by-component canonicaliser in `sh` is code
  whose bugs are silent in the dangerous direction, inside the one function every guard's integrity
  rests on, and it could not be tested here — isolating the case needs a symlink in a root-owned
  directory, which an unprivileged test cannot create. On the systems where it would apply the
  targets are root-owned anyway: merged-`/usr` on Linux, `/private` on macOS.

  The regression test takes the owner's suggested shape and improves on it. A mode-555 *wrapper* in a
  directory the user owns distinguishes the old question from the new one — `-w` on the file says
  safe, the directory makes it replaceable — and unlike the end-to-end case it runs on both CI legs
  rather than only where PATH wins, so there is no skip to fall quiet. The root case is *encoded*
  rather than skipped: as root everything is replaceable, which the assertion states instead of
  passing over. What the behavioural test cannot reach is the resolver *taking* such a candidate,
  because the fixed candidates win before PATH is consulted on any machine where one of them
  qualifies; that call site is pinned statically and the pin was defeat-verified. Each candidate must also
  parse the checker, with a version floor, since a fixed path can be an older Python. Verified on
  both CI platforms: the stage ran and printed its count on ubuntu and on macOS with no fallback
  notice, so the interpreter chosen there was unreplaceable too.

  **Recorded as the owner's call, and then made by them: the hooks are converted too.** Every hook
  resolved its own interpreter the same way, so a plant earlier on PATH would have owned
  `bash-guard.sh`, `scope-guard.sh` and the commit checkpoint — every decision this harness makes
  about a write — and `skill-activation.sh` was worse, *preferring* `.venv/bin/python` on every
  prompt. `.claude/check.sh` ran the guard assertions themselves under it, so a planted interpreter
  would have been the thing printing "all N guard assertions hold"; the comment four lines above
  that call claimed they ran on the system interpreter, which had not been true since it was
  written. One resolution now, `lib/syspy.sh`, pinned against the gate's copy, with a static
  assertion that no hook resolves its own.

  **A hole found while writing it, and the reason the resolver can afford to be cheap.**
  `bash-guard.sh` ended with the decider's status as its own. `bash_guard.py` returns 0 to permit
  and 2 to refuse; everything else — a crash, an `ImportError`, an interpreter too old to parse it —
  is 1, which `PreToolUse` treats as a non-blocking error, so the write proceeded unexamined. *Any*
  way of breaking that guard was a way of turning it into a permit. Undefined statuses now map to a
  refusal, which covers more than the interpreter case and costs nothing, where verifying each
  interpreter would have cost an extra process start on every tool call.

  **Two limits of the detection half, stated rather than implied:** a PATH directory that cannot be
  listed is skipped, and a plant already in place before the first snapshot is the baseline rather
  than a change. And one practical note from doing it: converting `self-application-guard.sh` left
  it referring to a variable it no longer set, so it refused every `Write` and `Edit` — including
  its own repair. Fail-closed worked exactly as designed, and the repair took the owner's hand,
  which is OQ4's bootstrap case arriving in practice rather than in principle.

  **Still not covered, and stated as a class rather than a list:** a test that writes and restores
  within the run, a process it detaches, a pytest plugin registered through a planted
  `*.dist-info` entry point, a forged background log in `.claude/hooks/state/` (advisory text,
  never the gate's result), and — the honest general case — any further configuration git or
  another tool grows that runs a command. Four rounds have each widened what is watched, and each
  time the next review found the next file. `commit-review.sh` still shows protected paths in the
  index at commit whatever put them there, which is a second layer and not a closure. **The class
  closes when the test run is confined**, which is HARNESS-FS in `.claude/TASKS_M2.md`, accepted
  and unbuilt. Nothing here claims otherwise.

  **Five further findings were recorded here and deliberately not fixed** under the owner's scope
  freeze for that branch, which admitted one class — code planted by test code reaching the guards —
  plus F2. **All five are closed now, in `m4/close`, which is where the freeze stopped applying.**
  They are kept in full rather than struck through, because what each one was is the reason the fix
  is shaped the way it is.

  (i) *Denial of the gate*: a test that makes a watched file unreadable (`chmod 000`) turned the
  snapshot into `CannotCheck`, exit 2 — the correct direction, since refusing beats passing, and
  still a way for any test to **stop the gate**, leaving the operator looking at a broken harness
  rather than at a hostile test. **Closed:** the mode is observable when the content is not, so this
  was never a check that could not run. `unreadable` is a value like `absent`; a file that becomes
  unreadable during the run is reported as `locked` — named apart from `changed`, because the remedy
  is a file mode and not an edit — and a file already unreadable when the baseline was taken reads
  the same in both snapshots and says nothing, which is what keeps the honest case quiet.

  (ii) *pytest's exit codes 3 and 4 collapse into 1*: the wrapper reported "the command failed", so
  "tests failed" and "pytest could not run" arrived as one signal. **Closed:** the child's status
  passes through untouched — a wrapper running an arbitrary command has no business reinterpreting
  another program's exit codes, which is precisely why it must not overwrite them — and `check.sh`
  maps anything outside {0, 1, 2} to exit 2, where pytest is known to be the command.

  (iii) *System git configuration was off for the child* (`GIT_CONFIG_NOSYSTEM`), which also drops a
  system-level `safe.directory` — in a container whose checkout is owned by another uid, every test
  that shells out to git would fail there. **Closed by removing the variable**, which was not earning
  its cost: the vector is a test writing the *global* config, which `GIT_CONFIG_GLOBAL` already
  redirects, and `/etc/gitconfig` is not writable by the user whose tests these are. If it were, that
  test could do anything regardless.

  (iv) *Nothing normalised a path*, so `…/.claude/../src/secrev/x.py` matched the harness case and was
  asked about rather than dispatched to the milestone that would refuse it — and because the harness
  case answers *ahead* of the dispatch, the precedence inverted rather than merely over-matching.
  **Closed** with a lexical `normalise_path` in `paths.sh`, applied by the three guards that read a
  path. Lexical and not `realpath`: resolving symlinks costs a process per tool call and a utility
  whose flags differ between GNU and BSD. The two are not equivalent and the difference is stated —
  with a symlinked component the lexical answer can differ, and only in the direction that
  over-matches, since these globs fire on a segment appearing anywhere. `spec-guard.sh` needs none:
  its patterns are suffix-anchored, which `..` cannot defeat. **And the fix cost two assertions
  immediately:** written as `normalise_path "$(read_field …)"`, the reader's `exit 2` ended only the
  subshell, the outer command succeeded, `set -e` saw nothing, and a malformed payload returned 0
  from two guards. Third time this repository has paid for that shape.

  (v) *A failed `hook_ask.py` exited 1*, which `PreToolUse` treats as a non-blocking error, so a
  write proceeded with nobody asked — on the two guards whose entire purpose is that somebody looks.
  **Closed:** every ask goes through `syspy_ask`, which exits 2 when the question cannot be put.
