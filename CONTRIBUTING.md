# Contributing

## Setup, including the step that is easy to miss

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
git config core.hooksPath .githooks     # ← this one
```

That third line is not optional and is not automatic. The hooks live in
`.githooks/` rather than `.git/hooks/`, so a clone without it commits and pushes
with **no gate running locally at all** — everything still looks fine, and CI
catches it later. A silent absence of checking is the exact failure this project
is built around, so it is worth confirming rather than assuming: after setting
it, `git commit` should print gate output.

One external binary is not installed by any of the above. `gitleaks` is fetched
from a pinned, hash-verified release tarball; the command is in `CLAUDE.md`
under *Development environment*, with the version and SHA. It is not repeated
here on purpose — a pinned hash written down twice is a hash that gets bumped in
one place. Without it the gate exits `2` rather than skipping, which is
deliberate.

## The gate

```sh
sh scripts/check.sh            # everything CI runs
sh scripts/check.sh --fast     # what pre-commit runs: no tests, determinism or audit
sh scripts/check.sh --sast     # the above plus CodeQL (minutes)
```

`--fast` is a prefix of the same list, never a second list. Nothing reaches a
remote on its strength: pre-push and CI both run the whole thing.

A failing stage exits `1`. A stage that *could not run* — a missing tool, no
network — exits `2`, and those two are never collapsed. "I did not check" and
"I checked and it is fine" are different states, and a gate that reports them
identically is worse than no gate, because the green gets believed. If you find
yourself adding `|| true` to make a stage pass, that is the bug.

## Two gates, and neither calls the other

| | `scripts/check.sh` | `.claude/check.sh` |
|---|---|---|
| Asks | Is the software correct? | Does the tooling still refuse what it claims to? |
| Covers | `src/`, `tests/`, `scripts/`, `patterns/` | `.claude/`, `tests/harness/` |

The second one is only interesting if you are changing the Claude Code harness.
A contributor who does not use Claude Code never runs it, and their build does
not fail on a layer they do not have. Reading across that boundary is fine;
writing across it is not, and an assertion enforces it.

## Tests

Golden-file tests with byte comparison, not approximate assertions — that is how
the determinism requirement stops being aspirational. Concretely:

- Every generation script gets a golden test against the committed fixture tree.
  Changing a fixture changes every hash derived from it, so treat an edit there
  as a change to expected output rather than as tidying.
- At least one golden test uses a non-ASCII filename, which is what keeps the
  Unicode normalisation rule honest.
- Every catalog pattern ships a positive **and** a negative fixture. A pattern
  without a negative fixture drifts into over-matching and nobody notices.

Coverage percentage is not the metric here and is not measured.

## Commits and pull requests

The subject says what changed; the body says **why**, because the diff already
says what. In this repository the "why" is usually a spec reference — a
principle, an invariant, a decision id — and six months later that reference is
the most useful line in the message.

Both git hooks honour `--no-verify`. That is a deferral rather than a bypass: CI
runs the identical gate on every push to every branch. Use it when you mean to,
not when it is inconvenient.

## Never record a target's specifics in this repository

Running the tool against real third-party code is part of the work — one of
M1's Definition-of-Done items requires it. Writing up that run is where the
trouble is, because the natural way to show a sweep worked is to say what it
found and where.

**Do not.** No file path inside a target, no function or constant name, no
description of the shape of a weakness — not in a brief, not in a commit
message, not in a receipt, not in a golden file. This repository is going
public, so a commit that names someone else's unfixed weakness has disclosed
it: to the maintainer and to everyone else at once, minus the part where the
maintainer was told first. FR-8.4 requires explicit human action before
anything reaches a maintainer, and a commit is not that action. G-1 says the
output exists to help someone fix their exposure, not to publish it ahead of
them.

The question a milestone is entitled to answer is whether *the tool* did its
job — how many candidates, over how many files, whether it reached the region
a check required. All of that is recordable without coordinates.

This happened twice while M1 was being written, which is why it is a rule and
not a reminder. The first time a brief pronounced on a target's soundness — a
Phase 4 verdict from a milestone that owns no triage. The second time it merely
gave the file path, which is worse than it sounds: it is the part an attacker
actually needs. Both had to be removed from the working tree *and* rewritten
out of history, which is only cheap because nothing had been pushed. Assume
that luck is not available next time.

## When the documents disagree

`REQUIREMENTS_security-review-skill.md` (the PRD) beats `STACK.md`, which beats
a milestone brief. If two of them conflict, **say so in the issue or pull
request instead of picking one**. A conflict usually means the PRD needs a
correction, and quietly resolving it in code loses the only signal that it did.
This has already happened more than once and both times the document was wrong,
so raising it is the expected outcome and not an escalation.

## Scope

Each `BRIEF_*.md` opens with what must *not* be built yet, and the reason each
would be got wrong if attempted early. Those lists are load-bearing: most of
them exist because doing the thing early produces something that looks like it
works. A pull request implementing a later milestone's feature will be asked to
wait, however good it is.

## Licensing of contributions

This project is under [PolyForm Noncommercial 1.0.0](LICENSE), which is
source-available and **not** an open-source licence — commercial use is not
covered by it. By opening a pull request you agree that your contribution is
licensed to the project under those same terms. There is no CLA and no
copyright assignment. If that arrangement does not work for you, say so before
writing code rather than after.
