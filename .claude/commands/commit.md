---
description: Run the gate, then commit the staged work with a message that says why
---

Commit the current work. Scope: $ARGUMENTS

## Order — the gate first, always

```sh
sh scripts/check.sh
```

`.githooks/pre-commit` runs the same script, so a red gate will stop the commit
anyway. Running it first means you find out before writing the message, not
after. If it fails, stop and fix it — `--no-verify` is for when you *mean* to
bypass, which is not the same as when it is inconvenient.

## Then

1. `git status` and `git diff` (staged and unstaged). Read what actually changed;
   do not write the message from memory of what you intended to change.
2. `git log --oneline -10` for the message style already in use.
3. Stage deliberately. `git add -A` is fine when the diff is the whole change and
   you have just read it. It is not fine as a reflex.
4. Never commit `.claude/settings.local.json` — it is gitignored and holds this
   machine's absolute paths.

## The message

Subject line says what changed. Body says **why**, because the diff already says
what. In this repo the "why" is usually a spec reference — a principle, an
invariant, a decision id — and that reference is the most useful thing in the
message six months later.

```
sweep: derive candidate ids from (path, rule_id, window_sha256, ordinal)

A traversal counter would renumber every hit when an unrelated file is
added, which breaks the stable-id half of NFR-3. D-4.
```

Do not describe the commit as generated in the subject or body — the trailers
already carry attribution, and repeating it in prose costs a line that could
have said why.

## Branch

If on `main`, branch first:

```sh
git checkout -b $(tr 'A-Z' 'a-z' < .claude/MILESTONE)/<short-topic>
```

## Stop there

Commit only. **Do not push** — pushing is outward-facing and is the user's call
every time, even when a previous push in the same session was approved.
