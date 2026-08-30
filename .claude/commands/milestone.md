---
description: Plan the current milestone against its brief
argument-hint: "optional: a specific part of the milestone to plan"
---

Plan work for the milestone named in `.claude/MILESTONE`. Scope: $ARGUMENTS

## Read first, in this order

1. `.claude/MILESTONE` — which milestone is current.
2. The matching `BRIEF_M<n>.md` — §1 scope, §2 deliverables, §7 Definition of Done,
   and especially the "do not build" table with its per-row reason.
3. `STACK.md` — binding mechanism.
4. The relevant PRD sections. §4 (principles) and §14 (decisions) at minimum;
   the brief will name others.

Do not plan from memory of these documents. Read them.

## Produce

- **Deliverable map** — every file in the brief's §2 tree, what it owns, and
  which other file it must not know about.
- **Sequence** — ordered steps, each independently verifiable. The invariants
  (traversal, normalisation, id derivation) come first: they are the ones that
  invalidate everything above them if wrong, and they are the ones that will not
  be revised later.
- **Definition of Done coverage** — map each checklist item in §7 to a step. An
  unmapped item is an incomplete plan.
- **Explicitly out of scope** — restate what the brief defers, with its reason.
- **Open questions** — anything the documents leave genuinely ambiguous, and any
  place two of them appear to disagree. Do **not** resolve a conflict; naming it
  is the deliverable (BRIEF §8).

## Then

Present the plan via ExitPlanMode. The `plan-review` hook will ask you to run the
`plan-reviewer` agent — do that before writing any code, and address its findings
or say why you disagree.
