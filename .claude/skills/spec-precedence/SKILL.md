---
name: spec-precedence
description: How the three binding documents relate and what to do when they conflict — PRD over STACK.md over the milestone brief, and why a conflict must be raised rather than resolved. Use when a requirement is ambiguous, when two documents disagree, or before editing REQUIREMENTS, STACK.md, or any BRIEF.
---

# Which document wins

| File | Role |
|---|---|
| `REQUIREMENTS_security-review-skill.md` | PRD — **why**. Principles P1–P11, FRs by phase, data contracts §7, guardrails G-1…G-6, NFRs, build order M1–M12, decisions D-2…D-12 |
| `STACK.md` | Binding stack and environment decisions — **mechanism**. Applies to every milestone |
| `BRIEF_M<n>.md` | Current milestone scope — **what now** |

**A brief loses to STACK.md; STACK.md loses to the PRD on intent and wins on
mechanism.**

## The rule that matters

Where a brief and the PRD conflict, **raise it rather than silently resolving
it** (BRIEF_M1.md §8). A conflict usually means the PRD needs a correction, and
resolving it in code destroys that signal — the documents stay wrong and the
next milestone inherits the error.

This is the one place where "just pick the sensible reading and move on" is the
wrong instinct. Stop and say which two lines disagree.

## Principles override requirements

PRD §4: "If a requirement below ever conflicts with one of these, the principle
wins and the requirement is wrong." The principles most likely to be violated by
a reasonable-looking change:

- **P1** — deterministic work is never a prompt. Inventory, candidate
  generation, extraction, and completeness checking are scripts. The model is
  never asked to "go look around."
- **P4** — every candidate is resolved: a finding, or an explicitly reasoned
  "verified correct". Silence is not an outcome.
- **P6** — negative findings are deliverables.
- **P7** — a file write in an agent-controlled context is code execution, not I/O.
- **P8** — prose reaching an agent's context is behaviour-defining and reviewed
  as such. Reviewing only `scripts/` has reviewed the wrong thing.
- **P9** — the unit of review is the closure, not the entry file.
- **P11** — detection must not decide scope. Every reachable entry point enters
  the ledger on its own account, independent of any match.

## What counts as a document edit, not a code decision

- Adding a runtime dependency → STACK.md §2, with the reason recorded
- Changing an exit code → STACK.md §3
- Weakening or reinterpreting a determinism rule → STACK.md §5
- Building something a brief lists under "do not build" → the brief, and the
  reason it gives for the deferral

Each of these will at some point look like the shortest path to making a test
pass. It is not; the code is wrong, not the document.

## Related

`secrev-invariants`
