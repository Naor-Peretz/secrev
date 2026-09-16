# `threat-models/` — what is asked, and of which artifacts

The layer M3 builds (`BRIEF_M3.md`). Two levels, per PRD §8: `_agentic-core.md` carries what is
true of every agentic artifact and loads for all of them; each overlay carries what is specific to
one form and loads beside the core. `_classifier.md` holds the procedure for deciding which
overlays load — never the signals themselves, which live in each overlay's applies-when section, so
that there is one source of truth to drift from.

Protected (`STACK.md` §8 H-4), for the reason `patterns/` and `surfaces/` are, in the form that
applies to prose: a mandatory question deleted here is a check that disappears from every later
review of that archetype, and nothing else reports it.

## Question ids

Every mandatory question carries a stable id: `CORE-01…` in the core, and an archetype prefix in an
overlay (`SKILL-01…`, `MCP-01…`). Ids are **append-only**: a question that is superseded says so
and keeps its id, because the id is what a later milestone cites.

They exist because protection is only half the guarantee. It gates an unreviewed edit; an approved
edit that drops a question is just as silent. `tests/` therefore holds the committed set of ids,
and removing one turns a test red until the golden is updated deliberately — the discipline the
artifact goldens already use.

They are also what makes later milestones possible rather than retrofitted: M9's report can state
which questions were asked and answered, and a finding can cite the question it came from.

## What a file here may not do

Conclude. An overlay asks; Phase 5 answers. A question that can be answered "yes" without reading
the artifact is not a question (FR-3.2, and the seed patterns' `question` fields are the model).
