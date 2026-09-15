# Security policy

`secrev` is a security tool, so two different things get called "a security
issue" here and they are not handled the same way. This file draws that line
before someone has to guess it in the middle of a report.

## Status

Pre-release. There is no published version and no supported-version table,
because there is nothing yet to support: the version in `pyproject.toml` is
`0.0.0` and the first milestone that produces a working command is still in
progress. Reports are welcome anyway — the harness and the CI configuration are
real and are in scope today.

## Reporting

**Use GitHub's private vulnerability reporting**: the repository's *Security*
tab → *Report a vulnerability*. That route stays private until an advisory is
published, which is what a report of this kind needs.

If that option is not visible, open a normal issue containing only the words
"security report, details held back" and nothing else, and wait to be contacted.
Do not put the details in a public issue, a pull request, or a commit message.

Include what you would want to receive: what you ran, what happened, and what
you expected instead. A reproduction against a fixture tree is worth more than a
description of one.

This is a single-maintainer project with no service-level commitment. You will
get an acknowledgement and an honest answer about whether it is being worked on;
you will not get a guaranteed turnaround, and promising one here would be a
number nobody is held to.

## In scope

The threat model is *reviewing an artifact that wants to be reviewed
favourably*. Anything in these classes is a vulnerability:

- **Execution or escape while reviewing a target.** `secrev` reads hostile input
  by definition. Anything in a reviewed target that causes code to run, or
  causes a write outside the workspace, is the most serious class here — the
  workspace containment rule is `STACK.md` §6 and guardrail G-4, and it exists
  precisely so that reviewing a repository cannot modify it.
- **Content in a target that reaches the reviewing agent as instruction.**
  Guardrail G-6 makes this a High-severity *finding* when the tool detects it;
  it is a *vulnerability* when the tool is the one carrying it into a model's
  context unlabelled.
- **A credential from the target surviving into output.** G-3 requires anything
  resembling a credential to be redacted before it reaches the ledger or a
  `match_excerpt`. A leak past that is a vulnerability, not a formatting bug.
- **A harness guard that can be bypassed.** The hooks refuse writes to the
  protected paths; a way past one is a real finding under `STACK.md` §8 H-8,
  which says outright that a guard nobody has tried to defeat is an assumption
  rather than a control. Attempts to defeat the guards are invited, not merely
  tolerated.
- **A gate stage that reports success without having checked.** H-1. A green
  result that verified nothing is the failure this project was built around, and
  it counts as a security issue rather than a bug because the green is taken as
  evidence.
- **A credential committed to this repository**, or a dependency or pinned
  action that turns out to be hostile.

## Not in scope — open a normal issue

- **A pattern that misses something, or matches too much.** That is coverage,
  and it is expected to be imperfect: `precision: low` is a first-class value in
  the catalog, and every candidate is resolved by a human or a model anyway
  (principle P4). A miss is a gap to close in the open, not something to embargo.
- **A finding produced by running `secrev` against someone else's code.** Report
  that to whoever owns that code, not here.
- **A known advisory in a dependency.** The audit stage already asks that
  question on every push, and Dependabot files the pull request.

## Disclosure

Fixes go out with an advisory naming the reporter, unless the reporter asks not
to be named. If a report is one this project decides not to act on, that answer
comes with the reasoning, so the finding can be published by whoever found it
rather than sitting indefinitely in a private thread.
