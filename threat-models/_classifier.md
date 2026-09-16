# `_classifier.md` — how a target is sorted into archetypes

FR-1.5. This file holds **the procedure and nothing else**. The signals live in each overlay's
"Applies when" section, so there is one list per archetype to keep true rather than two that drift
apart the first time one is edited (`TASKS_M3.md` D-2).

That division is the whole design. A classifier restating each overlay's signals would be correct
on the day it was written and wrong on the day an overlay was edited, with nothing reporting the
divergence — the same failure shape the two-layer split exists to avoid.

**This file decides loading, not risk.** It concludes nothing about a target, exactly as a pattern
concludes nothing about a match (FR-3.2). Sorting wrongly is not a wrong verdict; it is a narrower
review, which is why the procedure below fails toward inclusion.

---

## The procedure

1. **Read the artifacts recon produced.** `recon.json` for the layout, the languages, the declared
   entry points and the workflows; the `source: surface` records in `hits.jsonl` for what is
   reachable. Classification is deterministic work over what scripts found, not an impression of
   the tree (P1).

2. **Take each overlay in `threat-models/` in turn and read its "Applies when" section.** Every
   overlay states its own signals; this file does not know them, and a reader who needs them is in
   the wrong file.

3. **Apply every overlay that plausibly matches — not the best one.** Where two overlays both fit,
   both load. Composition is the norm rather than the exception (FR-1.5, PRD §8.3): a bundle is
   routinely a skill *and* a hook *and* a server, and choosing among them silently removes every
   question the discarded overlays would have asked.

4. **Load `_agentic-core.md` once**, beside whatever matched (FR-2.1). It loads for every agentic
   target regardless of how many overlays did.

5. **Accumulate the mandatory questions. Do not deduplicate by similarity.** Two overlays asking a
   near-identical question about different boundaries are two questions, and answering one does not
   answer the other (PRD §8.3).

6. **If nothing matches, load the core alone and record a coverage gap** naming what the target is
   and why no overlay fitted. An unclassified agentic target is reviewed less thoroughly than a
   classified one, so the gap is the honest record of that — and it is the signal that an overlay
   is missing, which is how the next one gets written.

7. **Review the seams.** An artifact matching several archetypes is also reviewed for what happens
   *between* them (FR-0.8): a hook that can rewrite a call to the server in the same bundle is a
   composition risk that neither overlay owns on its own.

### Why it fails toward inclusion

Misclassification is silent narrowing, which is the failure P11 exists to prevent one level up. An
artifact tagged as one thing and reviewed only as that thing never receives the other's questions,
and nothing in the output says so — the review looks complete. An overlay applied unnecessarily
costs a reviewer some questions that resolve quickly; an overlay not applied costs the whole class
of issue it was written for. The asymmetry decides the direction, as it does for `precision: low`
in the catalog and for over-redaction in the ledger.

### What is not a signal

Anything the artifact says about itself in prose. A README calling something "a simple wrapper", a
description claiming a narrow purpose, a name — these are the artifact's own account and are
reviewed as content (P8), never used to decide what questions get asked of it. The signals in an
overlay's "Applies when" are structural for that reason.

---

## Worked examples

Three shapes this repository already knows, sorted by hand. They are here because a procedure
nobody has executed is a guess about its own clarity.

**A skill with a `SKILL.md`.** `hits.jsonl` carries a `surface.skill_activation` record; the head of
the file is YAML frontmatter with `name:` and `description:`. `skill.md` applies. No
`surface.mcp_server`, `surface.mcp_tool` or `surface.mcp_tool_listing` record, and no MCP SDK
dependency, so `mcp-server.md` does not. **Load:** core + `skill.md`.

Note what step 2 disposes of here: this repository's own M2 run produced a `surface.skill_activation`
record at `.claude/skills/skill-developer/SKILL.md:143`, inside a fenced block showing a template.
`skill.md`'s own "Applies when" resolves it — the discrimination is per record, not per file, and
that file *is* a skill on the strength of its frontmatter. The classifier does not need to know
that rule; it needs to read the section that states it.

**A server declared in `.mcp.json`.** A `surface.mcp_server` record on a `"command"` or `"url"`
line. `mcp-server.md` applies. Whether any `surface.mcp_tool` record exists decides nothing about
loading: a server whose tools are declared outside Python produces none, which is a coverage gap
that overlay names, not a reason to skip it. No `SKILL.md`, so `skill.md` does not apply.
**Load:** core + `mcp-server.md`.

**An artifact that is both.** A bundle with a `SKILL.md` *and* an `.mcp.json` declaring a server.
Both overlays apply, the core loads once, and the questions accumulate: `SKILL-01`…`SKILL-10` and
`MCP-01`…`MCP-10` together, with `SKILL-09` and `MCP-09` both asked even though both concern what
the artifact can reach — different boundaries, so two questions (step 5). Step 7 then asks what
passes between them, which neither overlay covers alone. **Load:** core + `skill.md` +
`mcp-server.md`.

---

## What the phase records

The archetype does not go in `recon.json` — its contract has no field for it, and adding one is a
data-contract change belonging to M7's freeze (`TASKS_M3.md` D-3). But a judgment with no shape is
not a record: free-form prose cannot be read by M7's gate or by M9's report, and an agent that
quietly skips an overlay leaves no trace. So this phase's own output states, in this order:

- **the archetypes chosen, and the evidence for each** — the record, field or layout that matched,
  named specifically enough that a second reader reaches the same list;
- **the overlays applied**, including the core;
- **the question ids carried forward**, which is what makes "every candidate is resolved" checkable
  later and what lets a finding cite the question it came from.

Where nothing matched, the same output carries the gap from step 6 instead of an archetype list.

This shape goes to M7 alongside the FR-1.5 placement question, so the contract freeze has something
concrete to decide rather than a habit to codify.
