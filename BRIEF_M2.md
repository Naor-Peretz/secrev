# Brief — M2: The Surface Source

**Milestone:** M2 of 12
**Prerequisites:** `STACK.md` (binding), `REQUIREMENTS_security-review-skill.md` (P11, FR-1.3,
FR-3.9–3.11, D-11), `BRIEF_M1.md` (the ledger and id rules this source writes into)
**Goal:** review scope stops being decided by the pattern catalog.

**Provenance, stated because it affects how much weight this carries.** Written at the moment M1
closed, to give `scope-guard.sh` rules for the milestone the marker now names and to hold the
obligation M1 carried forward. §1 and §4 are the parts that bind — this said "§7", a section this
brief does not have, carried over from `BRIEF_M1.md`'s layout where the Definition of done is §7
(TASKS_M2.md C-4); the deliverables in §2 are
derived from the PRD rather than from any implementation experience, and should be reviewed before
anyone builds against them.

---

## 1. Scope

**Build:** `surfaces.py` and `secrev surfaces`, emitting `source: surface` candidates into the same
`hits.jsonl` the pattern source writes.

The point is not more detection. It is that **detection must not decide scope** (P11). Where
patterns and structure alone determine what gets read, logic with no syntactic signature is never
examined, and the catalog silently sets the boundary of the review (FR-3.10). A surface candidate
says *this entry point is externally reachable — trace it to its sinks*, and it says that whether
or not anything matched there.

M1 demonstrated the need rather than merely asserting it. Its own last DoD item passed because a
pattern looking for agent-configuration path strings happened to fire in the region the item names.
The catalog arrived at the right place through a coincidence of vocabulary. A source that enters
candidates on reachability alone does not depend on that coincidence.

**Do not build.** Each is a later milestone and building it early will get it wrong:

| Not now | Why | When |
|---|---|---|
| Structural / AST analysis | Needs the ledger format settled across more than one source | M4 |
| `closure.py` | Surfaces are entry points; the closure is what they can pull in, and it is a larger question | M5 |
| Instruction & manifest catalog packs | Same engine, later packs | M5 |
| Ledger gate (`verify`) | Nothing to gate until three sources exist | M7 |
| Report rendering | Output shape follows from findings | M9 |
| Threat models, `SKILL.md` | Procedure written before first output is a guess | M3 / M6 |

**No new catalog packs.** M2 adds a *source*, not rules. `patterns/` is out of remit, and
`scope-guard.sh` refuses writes to it under M2 for that reason.

---

## 2. Deliverables

```
src/secrev/
└── surfaces.py          # → hits.jsonl, source: surface
src/secrev/cli.py        # gains the `surfaces` subcommand
tests/
├── fixtures/            # a target with a reachable entry point no pattern matches
└── test_surfaces.py
```

Surfaces to enumerate, from FR-1.3, bounded by `STACK.md` §7's honest reach — Python, plus
manifest-declared surfaces:

- MCP tool definitions
- Skill activation conditions, and the breadth of their descriptions
- Hook event bindings
- CLI commands (declared entry points; **not** the parser beneath them — §1 defers AST analysis to
  M4, and this line asked for it in the same document, which the owner resolved in favour of §1:
  no `ast` in M2, and the parser is a recorded coverage gap. TASKS_M2.md Q3)
- Exported functions of a package's public surface

HTTP routes and IPC handlers are named in FR-1.3 and are **not** required here: both need
framework-specific knowledge, and §7 says a half-built multi-language layer is worse than an
honest Python-only position. Record them as a coverage gap rather than approximating them.

---

## 3. Candidate shape

The M1 record (`BRIEF_M1.md` §5) with `source: "surface"`. Two differences, and they are the
milestone's substance:

- **`rule_id` is a surface id, not a pattern id.** It names the kind of entry point.
- **There is no `match_excerpt` in the pattern sense** — nothing matched. The excerpt is the
  declaration that makes the surface reachable.

`id` derivation is unchanged (`STACK.md` §5), and `window_spec` still travels on the record.
A surface candidate resolves only on a traced account of what the entry point reaches; "nothing
matched here" is not a resolution (FR-3.11).

---

## 4. Definition of done

- [x] `secrev surfaces <path>` emits `hits.jsonl` records with `source: surface`.
- [x] A reachable entry point that **no pattern matches** produces a candidate anyway — the
      assertion that P11 actually holds, and the shape AC-9a describes.
- [x] Two consecutive runs produce byte-identical output; golden test with byte comparison.
- [x] Candidate ids are stable when an unrelated file is added.
- [x] `recon.json`'s `coverage_gaps` stops saying surface enumeration is unimplemented, and says
      what is still unreachable instead (HTTP routes, IPC handlers).
- [x] The codebase still passes `STACK.md` §2.1 self-application.
- [x] **Carried from M1 — TASK-M1-010: the cross-platform determinism job passes on a real macOS
      runner, having compared a non-empty digest.** *Met 2026-09-16 at `d8b72a4`, run
      35079766314:* the macOS runner produced 35 pattern candidates and 10 surface candidates into
      one workspace, hashed that `hits.jsonl` and `recon.json`, and `linux vs macos` printed
      "Linux and macOS agree." having taken the comparison branch — no `NOTHING-COMPARED`
      placeholder. Both ledger blocks were in what was compared, which is the condition the owner
      set in Q6 and the first run for which it was true. Everything testable without macOS was done in
      M1: the generate step replayed locally, the comparison step defeat-tested in all three
      states including a divergence failing, NFD/NFC equivalence asserted at artifact level, and
      symlink-escape and case-folding containment. What remains is two claims about a filesystem —
      whether APFS returns NFD for a name written NFC, and whether its case folding collapses two
      inventory entries into one. **It is a box here because a carried obligation that lives
      only in a commit message stops being an obligation.**

      **The "blocked on there being no git remote" clause is gone (TASKS_M2.md C-5).** The remote
      exists, CI has run, and on 2026-09-15 the job passed on a real macOS runner having compared
      a non-empty digest — the condition as written. The owner's decision (Q6, 2026-09-16) is to
      leave the box open anyway, on a stricter reading: that digest covered the pattern block
      only, because the surface block joined the comparison in TASK-M2-009 and has not been
      pushed. The box closes when CI compares **both** blocks across platforms.

      **Narrowed since, by reading the platform documentation instead of only planning to observe
      it.** APFS *preserves* filename normalisation and is merely insensitive on lookup; HFS+ was
      the filesystem that stored a decomposed form. `STACK.md` §5 asserted both stored NFD and has
      been corrected. So the first question is largely answered on paper — an APFS checkout of this
      repository's NFC-stored fixture should yield the same bytes as an ext4 one — and what the
      runner is really confirming is that nothing between git and the filesystem alters them. The
      second question is the one that stays open and is the sharper of the two: APFS refuses to
      hold two normalisation variants of one name in a directory, so a target containing both has
      a *different inventory* on macOS, which no amount of NFC handling reconciles.

---

## 5. Notes for the implementer

- **Surfaces are the cheapest source and the most valuable per item** (FR-3.10). Expect the
  smallest count of the three. A large surface count usually means entry points are being confused
  with call sites.
- **Nothing here concludes anything**, exactly as in M1. A surface candidate is a question about
  reachability, and Phase 5 answers it.
- Where this brief and the PRD conflict, raise it rather than choosing (`BRIEF_M1.md` §8). That
  happened twice in M1 and both times a binding document was wrong.
