# Disabled agents

Not scanned by Claude Code — this directory is outside `agents/`. Files here are
kept rather than deleted so the decision can be reversed by moving one back.

## Why these two

`architect.md` and `planner.md` were imported from
`github.com/affaan-m/everything-claude-code` and adapted. Two problems:

1. **Four entities for one job.** The built-in `Plan` agent, `architect`,
   `planner`, and `plan-reviewer` all sat in the planning slot. The first three
   overlapped almost entirely. What survives is the built-in `Plan` agent for
   generating a plan, `/milestone` for planning against the current brief, and
   `plan-reviewer` — the only one with a job nothing else does, because it
   reviews a plan against the specification rather than for internal coherence.

2. **A second copy of the stack.** Each carried its own "Technology Stack"
   section duplicating `STACK.md`. `STACK.md` is binding on mechanism for every
   milestone; a copy of it in an agent prompt does not get updated when it
   changes, and then it contradicts the document it was quoting — silently, in a
   place no one reads until an agent acts on it.

   Both copies are gone (M0, TASK-012B). This file used to say a disabled agent
   keeps its copy until someone restores it, which was the H-7 failure wearing a
   procedure: it deferred the correction to a future day when the copy would be
   older still and the drift harder to see, and it relied on whoever did the
   restoring to remember. By the time they were removed both copies listed
   `mypy` as a dependency `STACK.md` did not record, and neither had heard of
   §8 — the section that binds the harness they are part of.

To restore one, move it back to `.claude/agents/`. Nothing else is required, and
that is the point: a file that is correct while disabled is correct when enabled.
