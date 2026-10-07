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

- [ ] **The record count over this repository, and its history, superseded by
      the roots entry above.** Three measurements, each after a different fix,
      kept because the sequence is the finding: **3,692** with references
      resolved only relative to the referring file (`STACK.md` alone 415 times,
      because a mention inside `src/secrev/` resolved to
      `src/secrev/STACK.md`); **1,171** once resolution tried all three
      conventions that exist; **1,024** once the roots became the entry points
      the target declares. Each fix was right and none of them made the number
      small, which is what the roots entry above is about.

      The question that remains: FR-4.3 refuses to render a report while any hit
      is unresolved, so what does P4's "every candidate is resolved" permit? The
      bulk of these are documentation naming example files, which is honest low
      precision under P4 — a false positive costs a paragraph and a miss is a
      silent gap — but a thousand paragraphs is not a review.

## Four real targets, two defects fixed, and the contract decision

**The owner ran PR #23's head on three real targets, which is the measurement no
amount of running it on this repository could have produced.** Both defects below
are M5's, and both were invisible here: this repository has no lockfile and
almost no TypeScript.

### The two fixes

1. **A lockfile is a member and is not a referrer** (FR-0.3: dependency CVEs and
   third-party service behaviour are out of scope by default). `uv.lock`,
   `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`,
   `Cargo.lock`, `Gemfile.lock`, `composer.lock`. The owner measured **925
   `remote_resource` records out of one `uv.lock`** — 58% of that target's entire
   output on one file's dependency table. A source spending the majority of its
   output there has stopped being readable, which is H-1 arriving as volume. The
   file stays a member, because a lockfile pins what will be installed, and a gap
   line says it was not read.
2. **Extractor precision, two shapes.** A token followed by `(` is a call:
   `response.json()` matched because `.json` is a real suffix. An import
   specifier that does not start with `.` or `/` is a package: `from
   "@modelcontextprotocol/sdk/types.js"` resolves out of `node_modules`, which
   `STACK.md` §5 excludes from the walk by name — so reporting it was reporting
   dependency resolution as a hole in the artifact. **Both permits are in the
   same fixtures**, because a rule that only refuses passes by refusing
   everything: `open("progressive.md")` still resolves, and `./local.ts` in an
   import still resolves.

Each suppression has its own `coverage_gaps` line and a test asserting the line
exists, because a rule that quietly stops reporting something is the silence
FR-3.8 exists to prevent — and these three were added *because* a measurement
called them noise, which is exactly when a gap line matters most.

### The fixes measured in isolation, same tree before and after

| target | before | after | |
|---|---|---|---|
| `jacob-bd/gemini-notebook-mcp-cli` | 1,597 | **665** | −932, 58% — almost all the lockfile |
| `modelcontextprotocol/servers` | 409 | **348** | −61, 15% |
| `anthropics/skills` | 1,175 | **1,156** | −19, 2% |
| this repository | 1,210 | **1,190** | −20, 2% |

**This repository's figure went from 1,040 to 1,190 across the same change, and
that is not the fix going backwards.** It is the fixture files and test prose this
work added; measured on one identical tree the fixes take 1,210 to 1,190. Worth
stating because the raw before-and-after looks like a regression and is not.

### Per rule and per referrer kind, after the fixes

A referring file is a manifest (structured configuration a client reads as data),
code (something an interpreter or shell runs), or prose. `is_prose` counts JSON,
YAML and TOML as prose, which is right for the instruction layer and wrong here —
a path in a manifest is a path something opens — so manifests are split out by
name first.

| target | records | rule | code | manifest | prose |
|---|---|---|---|---|---|
| gemini-notebook-mcp-cli | 665 | `missing_reference` 297 | 116 | — | 181 |
| | | `remote_resource` 289 | 45 | 3 | 241 |
| | | `ambiguous_reference` 79 | 10 | — | 69 |
| anthropics/skills | 1,156 | `missing_reference` 821 | 111 | — | 710 |
| | | `remote_resource` 289 | 30 | — | 259 |
| | | `ambiguous_reference` 46 | 10 | — | 36 |
| modelcontextprotocol/servers | 348 | `remote_resource` 218 | 10 | 3 | 203 |
| | | `missing_reference` 112 | 50 | — | 62 |
| | | `ambiguous_reference` 18 | 7 | — | 11 |
| this repository | 1,190 | `missing_reference` 1,058 | 546 | 15 | 497 |
| | | `ambiguous_reference` 86 | 48 | — | 38 |
| | | `remote_resource` 37 | 20 | 1 | 14 |
| | | `escaping_reference` 9 | 7 | — | 2 |

**And the `code` column is not what it looks like, which took a second
measurement to see.** The first split tested whether the matched *line* starts
with a comment marker and reported 567 of this repository's 621 code records as
executable — wrong, because only a docstring's opening line carries the marker and
this repository's modules are mostly docstring. Tracking the state across lines:

| target | from code | executable | comment | docstring |
|---|---|---|---|---|
| this repository | 621 | 507 | 41 | 73 |
| gemini-notebook-mcp-cli | 171 | 147 | 4 | 20 |
| anthropics/skills | 151 | 94 | 32 | 25 |
| modelcontextprotocol/servers | 67 | 59 | 8 | 0 |

So a sixth of the code records are prose living in a code file. That matters to
the proposal below, which treats a reference from code as evidence of loading.

### The contract proposal, modelled, for the owner's decision

**The proposal as stated:** per-instance records for evidence of loading —
`remote_resource`, `escaping_reference`, and missing or ambiguous references from
code or manifests — and unresolved citations in prose grouped into one record per
referring file listing the paths. Still in the ledger, so FR-4.3 still forces a
decision, and the file gets FR-3.15's full read anyway.

| target | now | under the proposal | |
|---|---|---|---|
| this repository | 1,190 | **613** | 547 per-instance + 66 grouped |
| gemini-notebook-mcp-cli | 665 | **424** | 397 + 27 |
| anthropics/skills | 1,156 | **423** | 362 + 61 |
| modelcontextprotocol/servers | 348 | **284** | 272 + 12 |

It roughly halves the volume and leaves 284 to 613. **What holds it up is
`remote_resource` from prose**, which the proposal keeps per-instance by design —
241 of them in one target, 259 in another, 203 in a third, and nearly all are
documentation links in a README.

**One clause changes that, and the owner should see the number before deciding:**
group a URL in prose too, on the grounds that a documentation link is a citation
on exactly the same footing as a filename in a sentence.

| target | now | with that clause | |
|---|---|---|---|
| this repository | 1,190 | **597** | 527 + 70 |
| gemini-notebook-mcp-cli | 665 | **183** | 150 + 33 |
| anthropics/skills | 1,156 | **176** | 94 + 82 |
| modelcontextprotocol/servers | 348 | **82** | 62 + 20 |

That is the readable number on every real target, and it costs one thing worth
naming: a URL in a README that *is* fetched at run time would arrive grouped with
the citations rather than on its own. FR-1.2 asks for resources fetched at load or
run time to be recorded as unresolvable members, and grouping records them — but
it records them beside links to documentation, which is a worse reading position
for the one that matters.

This repository stays near 600 under both, because 507 of its records come from
executable code naming paths — test expectations listing fixture files, and the
gate scripts. For a target that is itself a review tool that is expected, and it
is the one case where the number is not evidence about the contract.

### DECIDED and implemented (owner, 2026-10-08)

**The proposal plus the prose-URL clause, with one exception the owner added: a
`remote_resource` in a *root* file stays per-instance.** An agent loads a declared
entry point verbatim, so a URL there is usually an instruction rather than a
citation — the one place where "prose" and "what the agent acts on" come apart.
The contract is in `STACK.md` §3, because FR-4.3 gates on it and M7 inherits it.

One ordering detail decided here and worth keeping: **a manifest is a manifest
before it is a root.** `_referrer_kind` tests the format first, so a `.mcp.json`
entry point keeps every record. Asking "is it a root?" first was the first
version and a test caught it: a `plugin.json`'s ambiguous reference was *grouped*,
because the root exception only covers URLs.

And one edge the literal reading gets wrong, fixed: **a file nobody read has no
citations to group.** The single reference that reaches the grouping from an unread
file is a declared entry point the target does not contain — `--entry nowhere.md` —
and calling that a citation in prose is false twice over: there is no prose, and
the caller named it as the thing the artifact loads. It keeps its own record. None
of the four measured targets uses `--entry`, so this neither explains nor
contradicts their numbers.

### A fourth defect, and it was the worst of them

**A TypeScript ESM specifier names the emitted file, and the source has a
different extension.** `import { x } from "./tool.js"` in a `.ts` file means
`tool.ts`. On `modelcontextprotocol/servers` the owner measured 42
`missing_reference` records that were relative `.js` imports whose `.ts` file is
in the tree — so the records were wrong **and the real source never entered the
closure**. A TypeScript MCP server's own code sat outside the reachable set while
the artifact showed a tidy list of paths the target supposedly lacked.

Over-reporting is this project's chosen direction; that was under-reporting
wearing over-reporting's clothes, which is worse than either. `.js`→`.ts`/`.tsx`,
`.jsx`→`.tsx`, `.mjs`→`.mts`, `.cjs`→`.cts`, tried only after the literal path
fails so a repository that commits its compiled output still resolves to the
`.js` that exists. One positive fixture per shape, and the permit with them.
Verified on the case the owner named: `toggle-subscriber-updates.ts` is a member,
36 `.ts` members in that target, 6 `.js` references left — one build artefact, one
URL, one product name in prose, and three prose mentions written without `./`
whose paths are unresolvable either way. `.mts` and `.cts` joined
`inventory.LANGUAGE_BY_SUFFIX`, so a rewritten member is not reported as "an
extension naming no language".

### The final numbers, all four targets

| target | before this round | after | |
|---|---|---|---|
| `jacob-bd/gemini-notebook-mcp-cli` | 1,597 | **218** | owner's model predicted 224 |
| `anthropics/skills` | 1,175 | **242** | predicted 269 |
| `modelcontextprotocol/servers` | 409 | **50** | predicted 96 — the ESM fix is the difference |
| this repository | 1,210 | **913** | code-heavy; see below |

By rule, after:

| target | records | missing | remote | citations | ambiguous | escaping |
|---|---|---|---|---|---|---|
| gemini-notebook-mcp-cli | 218 | 116 | 68 | 22 | 12 | — |
| anthropics/skills | 242 | 111 | 54 | 67 | 10 | — |
| modelcontextprotocol/servers | 50 | 11 | 17 | 15 | 7 | — |
| this repository | 913 | 783 | 34 | 35 | 52 | 9 |

**Where my numbers and the owner's differ, and I did not tune to close it.**
Modelling the contract on 7ff5a8b before implementing, my reading gave 213/242/89
and a variant keyed on (file, rule) gave 230/283/97 — the owner's 224/269/96 sits
between them, so one clause of their model is one I cannot see. Candidates: which
names count as manifests, whether a citation inside a *comment* in a code file
groups, and whether a file's grouped record is one or one per rule. Matching a
number by trying clauses until it coincides is the move this project refuses, so
the contract is implemented as *stated*, the reading is written out in
`STACK.md` §3 and in `closure._PER_INSTANCE_KINDS`, and the delta is here. One
line from the owner closes it if the difference matters.

**This repository stays high (913) and that is not the contract failing.** 783 of
its records are `missing_reference` from executable code — test expectations
listing fixture paths, the gate scripts, `src/` naming artefacts — which the
contract keeps per-instance by design because a path in code is a path something
opens. For a target that is itself a review tool, that is the honest answer, and
it is the one case among the four where the number says nothing about the rule.

## The answer to that question, given by the owner (2026-10-07)

**P4 forbids unexamined membership, not shared reasoning.** A class resolution is
admissible when the row for each candidate carries one *instance-level* fact
showing the class condition holds for that candidate. A paragraph standing in for
175 reads is not; 175 rows sharing seven paragraphs and each carrying its own
evidence is.

It is implemented rather than only written down, in `tests/f1_resolutions.py` and
`tests/golden/f1_resolutions.md`, which resolve every committed `.claude/`
candidate that way — and `tests/test_f1_resolutions.py` asserts row count equals
candidate count **in both directions**, because the failure a class resolution
actually has is looking complete while covering all but one.

**No count is written in this file either, and that is the demonstration rather
than an omission.** This ledger is under `.claude/`, so its own prose produces
candidates: writing "there are N" here is writing a figure that the act of
writing it invalidates. The count lives in the generated table. Adding the
entries below moved the table by 13 new rows and 10 re-identified ones, every one
of them in this file and `receipts.md`.

Three things came out of building it that M7 will need:

- **Closure membership cannot do the classifying, measured.** The first idea was
  to let the closure resolve these: a candidate in a file no declared entry point
  reaches is a record about the repository rather than content a client loads,
  which would be P9 doing exactly what it is for. When measured, **159 of 175
  sat in files that *are* closure members** — the receipts, the ledgers, the guard sources —
  because of the prose-citation chains above. So the discriminator is a property
  of the *host*: which paths it reads into a context window, which it executes,
  which it never opens. That is written down as a fact about the host, and it
  will be wrong for a client that behaves differently.
- **The gap the table crosses is `is_prose` answering the wrong question.**
  `is_prose` says whether a format holds prose; the resolution turns on whether
  anything *loads* the file. An instruction-layer pattern can only ask the first.
  If the closure's over-breadth is ever settled, applying the instruction pack to
  prose **in the closure** rather than to prose by format is the shape to try,
  and it needs the phase ordering M6 owns — the closure would have to run before
  the sweep.
- **A fact that is computed finds its own negative cases.** The
  `executed-not-loaded` rows carry where in the source the match sits, computed
  rather than asserted, and three came back as not-a-comment: two module
  docstrings and `hook_ask.py`'s `"hookEventName": "PreToolUse"`, which is the
  hook protocol's own field name in the code that emits it. A phrase from a table
  would have labelled all 22 identically and hidden them.

The table is content-keyed and will go stale: a candidate id derives from
`(path, rule_id, window_sha256, ordinal)`, so editing any file under `.claude/`
re-identifies the candidates in it. The test names the ids that gained or lost a
row, which is FR-4.6 arriving by hand — and the two failures are different jobs,
one regenerating a table and one re-reading content whose resolution expired.

## The roots were wrong, and what fixing them did and did not fix

**Owner correction, 2026-10-07, and the measurement is the record.** `_roots`
treated every readable file as its own entry point when `--entry` was absent.
That computes the *tree*, not the closure: FR-1.2 defines the closure as "the
entry file plus every file it references", and with every file a root every
filename mentioned in any document becomes a reference to resolve. The owner
measured 1,171 records over this repository, 1,036 of them
`closure.missing_reference`.

An intermediate version of mine filtered to readable text and was worse in a
different way: an unreferenced oversized file then appeared nowhere in
`closure.json` at all, while the gap line beside it claimed such a member "is in
the closure and is not read". That property is now kept by `Closure.unreachable`
— the complement of the closure inside the inventory, with a gap line naming its
size — which is the honest place for it. A file no entry point reaches is a
*statement*, not a member, and it is the first place to hide something from a
closure-based review.

**What the roots are now:** the entry points the target declares. `SKILL.md`,
`.mcp.json`, `plugin.json`, `hooks.json`, `settings.json`, a `bin` in
`package.json`, a `[project.scripts]` target in `pyproject.toml` resolved
through both packaging layouts — and the agent instruction files `CLAUDE.md`,
`AGENTS.md` and `AGENT.md`, which are the owner's list plus one addition of
mine, recorded here with its reason: those reach the context window on every
request, which is the strongest form of "the host loads this without being told
to" in the list, and leaving them out would make the closure of an
agent-instruction repository empty. A target declaring none is **exit 2 asking
for `--entry`**. Each root carries its reason into `closure.json`, because "the
caller asked about this path" and "the target declares this entry point" are
different reviews.

The fixture tree is what the owner asked for: **4 roots, 10 members, 6
unresolved**, every one of the six actionable — two scripts a hook configuration
names and the tree does not contain, a remote MCP endpoint, a remote rule set, a
path above the root, one missing helper. A `SKILL.md` was added to the designed
closure fixture so the whole-tree golden reaches that subtree the way a client
would, rather than only through an explicit `--entry`.

- [ ] **Over this repository it is 1,024 records, not a small number, and the
      roots were not the whole cause.** This is the part to put in front of the
      owner rather than paper over. With correct roots: 16 roots, 139 members,
      393 unresolved, 1,024 ledger records, 94 unreachable. The roots fix moved
      `missing_reference` from 1,036 to 902 — a seventh, not an order of
      magnitude.

      **The remaining amplifier is transitive expansion through prose
      citation**, and the chain is exact: `TASKS_M1.md` → `TASKS_M2.md` →
      `BRIEF_M5.md` → `tests/test_closure.py`. Four hops, every one a document
      citing another by name, not one of them a load — and the test file's own
      docstrings then contribute 111 records naming example paths. The closure
      swallowed the test suite through the ledgers.

      **One narrowing was implemented and measured and then reverted**, and the
      reason it was reverted matters more than the idea: follow a reference only
      when something about how it is *written* says "read this" — Markdown link
      syntax, an `@include`, or a referring file that is not prose. Measured:
      the repository went 1,024 → 934 records, a 9% reduction, while the
      designed fixture's closure went from 10 members to 5, because a skill
      saying "read `helpers/progressive.md`" is a bare token in prose. So it
      cost A1 half its demonstrated member kinds and bought almost nothing. The
      predicate was also wrong where it mattered most: `is_prose` counts JSON,
      YAML and TOML as prose, so the manifests whose paths genuinely *are* loads
      were the ones it stopped following.

      The honest statement of the problem: distinguishing "read `X`" from "see
      the discussion in `X`" is reading the sentence, which is FR-3.15's
      territory and not a regex's. The options I can see, none of them M5's to
      choose: a depth bound (arbitrary, and this project refuses thresholds
      measured against its own fixtures); an imperative-detection rule in the
      instruction pack feeding the closure (couples two sources, P11); or
      accepting that a repository whose agent-facing prose cites everything has
      a closure that reaches everything, and that FR-3.15's "Phase 4 must
      include a full read of the prose closure" is the PRD already saying so.

      Whichever it is, it changes what `verify_ledger` has to swallow in M7, so
      it is a decision with FR-4.3 consequences rather than a tuning knob.

## F1 — the tool run on itself, and what reading the result changed

`secrev sweep .` with both new packs over this repository: **373 candidates**,
**202** of them in `.claude/`, which is F1's own question. The distribution:
`manifest.hook_rewrite_event` 144, `instruction.write_outside` 71,
`instruction.install_component` 40, `instruction.approval_bypass` 39,
`manifest.wildcard_grant` 28, `instruction.conceal_action` 11,
`manifest.broad_activation` 10, `instruction.authority_claim` 9,
`instruction.override_prior` 6, `instruction.exfiltrate` 6,
`manifest.filesystem_scope` 5, `manifest.network_permission` 4.

**Two of the rules were wrong about themselves, and reading the output is the
only thing that could have shown it.** Both are corrected:

1. `manifest.hook_rewrite_event` claimed `precision: high`, on the argument that
   "these are literal event names, not a shape". It produced **144** candidates
   here and **three** of them are bindings — `.claude/settings.json` lines 60, 74
   and 106. The rest are prose and comments naming the events: every hook file's
   header, `.claude/README.md`, and a vendored skill whose entire subject is how
   hooks work. A literal name is exact and says nothing about whether the line is
   a binding, which is the claim `high` was making. Now `medium`, with the
   measurement in the pack beside it. Not `low`: in a real target's
   configuration the name *is* the binding, and this repository documents hooks
   for a living.
2. `manifest.wildcard_grant` had `deny` in its key list, so
   `.claude/settings.json`'s `"deny": ["Read(**/.env)"]` was reported as an
   unbounded grant. A wildcard inside a *deny* list is the opposite of the
   finding — it is a broad refusal, and flagging it asks a reader to justify a
   control. `deny` is out of the key list. The tool-scoped half still fires on
   that line, because `"Read(**/.env)"` reads identically under `allow` and
   under `deny` and the key is on another line; §4 makes cross-line reasoning a
   structural rule by definition, so the limit is stated in the pack rather than
   guessed at.

   The goldens net to zero on this one, because the fixture that holds the case
   and the regex change landed together — so the negative fixture plus
   `test_negative_fixture_does_not_match` is the assertion, and it was
   defeat-verified by putting `deny` back and watching it go red.

- [ ] **The one real finding about this checkout, for the owner rather than for
      the tool. The owner has said they will narrow it themselves; it is
      recorded here and the file is not edited.** `instruction.write_outside`
      fires 38 times on `.claude/settings.local.json`, which grants this session
      `Write` and `Edit` on `~/.claude/**` — including
      `~/.claude/.credentials.json` — and on `~/.bashrc`, `~/.zshrc`,
      `~/.profile`, `~/.cursor/**`, `~/.codex/**`, `~/.gemini/**` and
      `~/.agents/**`.

      That is exactly FR-3.13 class 5 and `fs.agent_config_write` asking their
      question, and the answer is "yes, deliberately, by the owner" — which is a
      P4 resolution rather than a defect. It is recorded because the file is
      gitignored, so nothing in the repository states it and no reviewer reading
      the committed harness would know: the guards in `.claude/hooks/` are
      written as though agent-configuration directories were out of reach, and
      on this machine they are not. The resolution belongs to the owner, not to
      M5.

**The rest is P8 working as `BRIEF_M5.md` §5 predicted**, and none of it is
tuned away. `instruction.approval_bypass`'s 39 are mostly `TASKS_M3.5.md` and
`receipts.md` *arguing for removing* auto-approved rules; `install_component`'s
40 are mostly a skill whose subject is creating skills. Documents that discuss a
finding produce the finding — including the three this milestone added by writing
the corrections above down, which moved `manifest.wildcard_grant` from 25 to 28.
A pattern that did not fire on them would be one that cannot read prose.

One hit is worth keeping as the example of the pack earning its place:
`instruction.conceal_action` on `.claude/agents/python-reviewer.md:85`, "Do not
report what these already caught". A genuine instruction not to report
something, legitimate in context, and resolvable in one sentence — which is what
a low-precision prose rule is supposed to cost.

## Raised during implementation and not fixed here

- [ ] **Eight lines in two closed milestones' files are now false, and M5 may
      not write either directory.** Found by F2's sweep — `git grep` from the
      root with no pathspec, candidates derived from `git log -p main..HEAD`
      rather than recalled. Sorted into CLAUDE.md's three categories, these are
      all in the first: they state the superseded rule.

      In `threat-models/`, seven lines say the packs do not exist:
      `skill.md:126` and `:186` and `:191`, `mcp-server.md:131` and `:191` and
      `:196`, `_agentic-core.md:85`. Each carries some form of "no pattern
      covers the instruction layer" or "does not exist; M5", with the sentence
      that the ledger's silence there "is coverage that does not exist yet
      rather than coverage that passed". Now false in both directions: the packs
      ship, and the ledger carries 373 records from them against this repository
      alone.

      Two more in the same files, `skill.md:177` and `mcp-server.md:180`, say
      "every pack in a run declares the same `version`", which the Q6 decision
      removed. And one in `patterns/python.yaml:19` says "one run has one
      catalog_version — so the version belongs to the whole catalog", which is
      the superseded rule stated in a *product-code comment*, the second of
      CLAUDE.md's three priorities by who reads it.

      **None of it is fixed, because M5 may write neither directory.**
      `scope-guard.sh` refuses `threat-models/` by name, and its reason is that
      editing the questions to suit the answers is P11 in the small; it refuses
      every file in `patterns/` but the two M5 owns, because M1's catalog is
      closed. Both refusals are right. The owner's scope rule for this run names
      "you'd need to touch a closed milestone's files" as a stop condition, so
      this is recorded rather than done — and the guard would have refused it
      anyway, which is the control working rather than an obstacle.

      What narrows the damage in the meantime: `recon.json` now carries
      `_CATALOG_LAYER_GAPS`, which states the limits the packs actually have, in
      the machine artifact a later phase reads rather than only in prose. So a
      reader who trusts the artifact is not misled; only one who trusts the
      overlays is.

      The exact edits, so whoever makes them does not re-derive them. In each
      overlay's §5 the pack line changes from "does not exist; M5" to naming the
      pack, its version and the classes it covers. Each evidence line that says
      "read" *because no pattern existed* gains the ids that now cover it —
      SKILL-04 and SKILL-05 get `instruction.approval_bypass`,
      `instruction.authority_claim` and `instruction.override_prior`; MCP-05 to
      MCP-07 the same three plus `manifest.broad_activation`; CORE-05
      `instruction.*` as a set; SKILL-08 and CORE-11
      `manifest.wildcard_grant`, `manifest.filesystem_scope` and
      `manifest.network_permission`; CORE-18 `manifest.hook_rewrite_event`.
      The "same `version`" sentences become "each pack declares its own
      `version`, and a record carries its pack's". And `python.yaml`'s comment
      loses its last two clauses.

      **What must not be written into them:** that the packs close those
      questions. Every one of those evidence lines also says the answer comes
      from *reading*, and FR-3.15 keeps it that way permanently — the ids are an
      addition to the evidence, not a replacement for it.

- [ ] **`recon.py` had no `coverage_gaps` line about the catalog's own layers,
      and that asymmetry was the finding.** Every source states its limits
      there — `_SURFACE_GAPS`, `_STRUCTURE_GAPS`, `_CLOSURE_GAPS` — while the
      catalog's missing instruction and manifest layers were recorded only in
      the overlays, in prose, and never in the artifact. Closed in M5 with
      `_CATALOG_LAYER_GAPS` (three lines: the comments-and-docstrings gap Q3
      pre-decided, FR-3.15's permanent cost, and the grant-versus-purpose
      comparison no line-oriented rule can make). Listed here because the
      *class* is worth remembering: a gap recorded only where a human happens to
      look is half a gap.

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
