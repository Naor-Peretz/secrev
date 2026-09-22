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
  **Still not covered, and stated:** a test that writes and restores within the run, a process it
  detaches, a pytest plugin registered through a planted `*.dist-info` entry point, and a forged
  background log in `.claude/hooks/state/` — advisory text, never the gate's result. For those,
  `commit-review.sh` shows protected paths in the index at commit, whatever put them there. Two
  layers, neither adding an approval.
