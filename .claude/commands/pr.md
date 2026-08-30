---
description: Open a pull request for the current branch, after the gate passes
argument-hint: "optional: a title or a note about what the PR is for"
---

Open a PR for the current branch. Note: $ARGUMENTS

## Preconditions — check all four before doing anything

1. **Not on `main`.** If you are, stop: the work needs a branch first (`/commit`
   creates one).
2. **The gate passes.** `sh scripts/check.sh`. CI runs the same script on Linux
   and macOS across 3.11/3.12 plus the cross-platform digest comparison, so a
   local pass is necessary and not sufficient — but a local failure is certain.
3. **A remote exists.** `git remote -v`. If it is empty, there is nowhere to open
   a PR; say so and stop rather than inventing one.
4. **`gh` is authenticated.** `gh auth status`.

## Then, in order

```sh
git log main..HEAD --oneline      # what this PR actually contains
git diff main...HEAD --stat       # and how wide it reaches
```

Read both before writing the description. A PR body written from the plan rather
than from the diff is how scope creep gets merged.

## The body

- **What and why**, with the spec reference — the principle, invariant, or
  decision id the change serves. In this repo that reference is the review.
- **Milestone**, from `.claude/MILESTONE`, and a line confirming nothing here
  belongs to a later one. `BRIEF_M<n>.md` §1 lists what must not be built yet.
- **What was deliberately not done**, if the brief defers something adjacent.
- **How it was verified** — which gates ran, and anything the gate cannot see.

## Ask before both outward-facing steps

`git push -u origin HEAD` and `gh pr create` each publish work under the user's
name. Ask before the push, and ask again before creating the PR. Approval for one
is not approval for the other, and approval in this session is not approval in
the next.
