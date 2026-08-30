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

To restore one, move it back to `.claude/agents/` **and** delete its stack
section, replacing it with a pointer to `STACK.md`.
