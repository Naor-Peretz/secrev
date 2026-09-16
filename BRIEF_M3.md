# Brief — M3: The Threat-Model Layer

**Milestone:** M3 of 12
**Prerequisites:** `REQUIREMENTS_security-review-skill.md` (§8 in full, FR-1.5, FR-2.1–2.3, AC-4,
P7–P11), `STACK.md` (binding; §7 for honest reach), `BRIEF_M2.md` (the surfaces this layer asks
questions about)
**Goal:** the questions stop living in one person's head.

**Provenance.** Written at the moment M2 closed, from the PRD and from M2's own output against this
repository. §1 and §4 bind. Unlike `BRIEF_M2.md` §2, the deliverables below are not derived from the
PRD alone: M2 ran the tool on real trees and produced 484 pattern candidates and 27 surface
candidates, and what that felt like is evidence this brief is allowed to use (§5).

---

## 1. Scope

**Build:** `threat-models/`, at the repository root beside `patterns/` and `surfaces/` — the core,
two overlays, and the classifier that picks them:

- `_agentic-core.md`, loaded for every agentic target;
- `skill.md` and `mcp-server.md`, overlays on the core;
- `_classifier.md`, how a target is sorted into archetypes.

The PRD's §5 tree shows these under `skills/security-review/threat-models/`, which is the packaged
skill layout. This repository flattens that, as it already did for `scripts/`, `patterns/` and
`surfaces/`. Same resolution, stated here so nobody re-derives it.

**Why this milestone is not code.** M1 and M2 built the machinery that decides *what gets read*.
This one decides *what is asked of what was read*. A candidate is a question (FR-3.2), and until now
the questions have been one sentence per pattern and per kind, written by whoever added the rule.
The threat model is where those sentences come from, and AC-4 is the test that the structure holds:
a new archetype must be addable as one overlay file, with no script change and no edit to the core.

**Do not build.** Each is a later milestone and building it early will get it wrong:

| Not now | Why | When |
|---|---|---|
| `structure.py`, `_structure.yaml` | The overlays will name sinks that want AST reasoning. Writing the analysis while writing the questions produces rules shaped by what is easy to detect — P11 in the small | M4 |
| `closure.py`, `_instruction.yaml`, `_manifest.yaml` | Overlays name pattern packs to enable; the packs themselves are a catalog change, and the closure is a larger question than an entry point | M5 |
| `SKILL.md`, phase ordering, the Phase 2 gate | FR-2.2 makes the threat model a hard gate before content is read. Writing the enforcement before the thing enforced is a procedure written against a guess | M6 |
| `subagent.md`, `hook.md`, `agent-config.md` | AC-4 says adding an archetype is cheap. Proving that with three more overlays in the same milestone proves nothing about the seam | M8 |
| `cli-tool.md`, `web-api.md`, `library.md` | Conventional archetypes, core not loaded. They inherit nothing and slot in when a real target demands one | — |

**No new patterns and no new surface kinds.** M3 writes prose. If an overlay wants a pattern that
does not exist, that is a finding about the catalog, recorded in the ledger, not a pack added here.

---

## 2. Deliverables

```
threat-models/
├── README.md           # orientation, and the id convention (added 2026-09-16, see below)
├── _classifier.md      # how to pick archetypes (FR-1.5)
├── _agentic-core.md    # always loaded for an agentic target (PRD §8.1)
├── skill.md            # overlay (PRD §8.2)
└── mcp-server.md       # overlay (PRD §8.2)
```

`README.md` was not in this list when the brief was written, and it existed from the protection
commit onward — both overlays cite it, which made an undeclared file into a rule source. Added here
rather than escalated: this is a brief that had stopped describing its own directory, which is the
correction `BRIEF_M2.md` C-4 and C-5 made for the same reason, not a conflict between binding
documents. Its normative half now points at `STACK.md` §8 H-4 instead of restating it (H-7), so the
duplication that made the question worth asking is gone.

`_agentic-core.md` carries the eight mandatory sections of PRD §8.1 and nothing archetype-specific.
Each overlay carries the six sections of §8.2, **in that order**: applies-when signals, additional
trust boundaries, archetype-specific sinks, mandatory questions, pattern packs to enable, and
known-good implementations.

Two of those six deserve naming here because they are the ones most easily written as filler:

- **Known-good implementations.** A `verified-ok` resolution needs a reference point or it is a gut
  feeling with a checkbox (P4, P6). An overlay without this section makes every resolution weaker.
- **Pattern packs to enable.** This is where the layer touches M1's work. Naming a pack that does
  not exist is allowed and is a coverage gap; naming one that does and getting the id wrong is a
  silent miss.

---

## 3. The shape of the layer

**Composition, not choice** (PRD §8.3). A plugin bundle is skill *and* hook *and* MCP server. The
core loads once, every matching overlay loads, mandatory questions accumulate and are **not**
deduplicated by similarity. Two overlays asking nearly the same question about different boundaries
are two questions.

**The classifier decides loading, not severity.** `_classifier.md` sorts a target into archetypes
from signals — file layout, manifest keys, entry-point shapes, the things `recon.json` and the
surface ledger already report. It concludes nothing about risk, exactly as a pattern concludes
nothing about a match.

**Prose is reviewed as behaviour (P8), and this layer is prose.** These files reach a reviewing
agent's context. Content isolation (NFR-7) applies to the *target*, but an overlay that tells the
agent what to conclude rather than what to ask is the same failure the catalog avoids by shipping
questions rather than verdicts.

---

## 4. Definition of done

- [x] `threat-models/_agentic-core.md` exists and carries all eight §8.1 sections, each with content
      specific enough that two reviewers reading it would look at the same places.
- [x] `skill.md` and `mcp-server.md` each carry the six §8.2 sections in order, including
      known-good implementations.
- [x] `mcp-server.md` names **tool return values** as a dangerous sink, and `skill.md` names the
      **activation description's breadth** (PRD §8.2 item 3 requires both by name).
- [x] `_classifier.md` sorts, by hand, the three artifacts this repository already knows about: a
      skill with a `SKILL.md`, an MCP server declared in `.mcp.json`, and one that is both. Multiple
      archetypes are the norm (FR-1.5).
- [ ] **AC-4 demonstrated, not asserted:** adding one overlay file requires no script change and no
      edit to `_agentic-core.md`. Proven by writing the second overlay after the first and showing
      the core untouched in the diff.
      *Open deliberately.* Everything the tree can show is in place — `mcp-server.md` written
      without touching the core, and the question-id pin moved out of Python into
      `tests/golden/question_ids.json` so that adding an archetype edits no script (owner decision
      on C-1). What is missing is the diff itself, and this box asks for a property of a commit.
      Ticking it from a working tree is the substitution "proven by doing it once" exists to forbid.
- [x] Every mandatory question in an overlay is answerable from artifacts this tool already
      produces (`recon.json`, `hits.jsonl`), or is explicitly marked as needing a phase that does
      not exist yet. A question with no path to an answer is a wish.
      *Verified against the sources, not just in form:* every cited `rule_id` and every cited
      `recon.json` field was checked to exist. Where none does, the question says which phase is
      missing — FR-1.2's closure (M5), FR-1.4's capability manifest (no milestone owns it, raised),
      the instruction pack (M5), the structural source (M4).
- [x] The codebase still passes `STACK.md` §2.1 self-application, and both gates stay green.

---

## 5. Notes for the implementer

- **Write against M2's output, not against the PRD alone.** The surface run over this repository
  produced 27 candidates: five hook bindings, ten skill activations, the tool's own CLI entry point,
  its empty public surface, ten fixtures, and one false positive — a `description:` line inside a
  documentation template. That false positive is the best available evidence of what
  `skill.md`'s applies-when section has to disambiguate.
- **The core is the expensive file.** Eight sections that are true of every agentic artifact, without
  drifting into any particular form, is the part that makes overlays cheap. Written badly, every
  overlay restates it and they drift (PRD §8's own reason for the two layers).
- **Resist the checklist voice.** A mandatory question that can be answered "yes" without reading
  anything is not a question. Compare the seed patterns' `question` fields: they say what to trace
  and where to look.
- Where this brief and the PRD conflict, raise it rather than choosing (`BRIEF_M1.md` §8).

---

## 6. Raised before implementation, for the owner

- **Does `threat-models/` join the protected set (H-4)?** The argument that protected `patterns/`
  and `surfaces/` was: they are tool input, and an unreviewed edit narrows the review with nothing
  reporting it. It transfers, but not exactly. Those two are machine-read data that decide what
  enters the ledger; these are prose that decides what a reviewing agent asks. The failure mode is
  the same shape and the mechanism is different, so this is the owner's call, and it is a `STACK.md`
  §8 amendment either way. Deciding it *before* the directory exists is what M2 learned (C-1):
  protecting an input after it exists leaves a window in which it is not.
- **Does the classifier belong to M3 at all?** The PRD's build order puts `_classifier.md` in M3,
  and FR-1.5 puts classification in Phase 1, beside recon — which is M1's phase. The risk of writing
  it now is that it classifies against signals no script yet extracts (FR-1.4's capability manifest
  is not built). The alternative is an M3 that ships the core and two overlays and defers sorting.
- **Is `recon.json` supposed to carry the archetype?** FR-1.5 sits in Phase 1 but nothing in
  `recon.json`'s contract (BRIEF_M1.md §3) has a field for it. If the classifier's output is meant
  to be machine-readable rather than a judgment the agent makes, that is a data-contract change and
  belongs to M7's freeze, not to this milestone.
