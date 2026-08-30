---
description: Run the full quality gate — the same script CI runs
---

Run the gate:

```sh
sh scripts/check.sh
```

It covers, in order: `ruff format --check`, `ruff check`, `mypy --strict`,
`pytest`, the self-application check (STACK.md §2.1), and the determinism check
(NFR-3). Gates with nothing to check yet are skipped and say so.

Then:

- **All pass** — say so and stop. Do not volunteer changes.
- **Mechanical failures** (format, lint, types, an obvious test break) — use the
  Task tool with `subagent_type="gate-resolver"`.
- **Determinism failed** — this one is never fixed by regenerating the golden
  file. Find what non-deterministic value reached the output first. Read
  `secrev-invariants` before touching anything.
- **Self-application failed** — remove the construct. There is no other fix; the
  claim in STACK.md §2.1 is public and either true or not.

A background run of the fast half (ruff, pytest, self-application) fires after
edits and is surfaced once by `async-check-report.sh`. It is not the gate — it
skips mypy and the determinism check — so a green background log is not a reason
to skip this command.

For any failure, the `debugging` skill has the method: read the failure fully,
reproduce at the narrowest scope that still fails, change one thing. It also has
the four failure classes specific to this project.

Report what failed and what you concluded, not just the exit code.
