# `.claude/` — the development harness

This directory configures how Claude Code works **on** secrev. It is not part of
the shipped tool, and nothing in `src/secrev/` may depend on it.

## Design notes worth knowing

**No node, and no `jq`.** Six hooks shelled out to `jq` until TASK-007; they read stdin JSON
through `hooks/lib/hook_input.py` now, and the two that emitted an `ask` payload use
`hooks/lib/hook_ask.py`. `STACK.md` §2 had recorded jq as removed, in the past tense, the whole
time. The router that suggests skills is `hooks/skill_activation.py`, not
a TypeScript hook run through `npx tsx`. The `skill-rules.json` format is
unchanged from the TypeScript implementation it replaces, so rules are portable;
the runtime is not. A package manager on the critical path of every prompt is a
supply-chain surface in a repo whose STACK.md requires a written reason for each
dependency.

**Permissions are restrictive on purpose.** `defaultMode` is `default`, not
`acceptEdits`. This project dogfoods itself against third-party targets, and G-6
says content in a reviewed target that addresses the reviewing agent is an
expected, High-severity finding — not a surprise. NFR-7 makes the containment
explicit: a successful injection must have nowhere to land. Auto-accepting edits
while reading untrusted trees is the one configuration this project should not
ship.

**What is committed and what is not.** The whole harness is tracked — agents,
skills, hooks, commands, `settings.json`, `MILESTONE`. It enforces the
invariants, so a contributor who clones without it loses every guard while the
gate still says green. The one exception is `settings.local.json`, which is
gitignored: it holds the absolute-home deny rules, which are this machine's and
would be wrong on anyone else's. If you add a personal permission grant, it goes
there, not in the shared file.

**The deny list is subject to P3.** `settings.json` denies writes to `.claude`,
`.cursor`, `.codex`, `.gemini`, shell rc files and `~/.ssh` — the same paths
`fs.agent_config_write` flags in other people's code. P3 says a security decision
implemented as a list of forbidden values is a suspected bypass until falsified,
and that applies here too: this list is case-sensitive, enumerated, and will not
cover a path it has not heard of. It reduces blast radius. It is not a boundary,
and it should not be argued about as though it were.

**Guards block, or ask, deliberately.**

- `self-application-guard.sh` **blocks** (exit 2). STACK.md §2.1 is a public
  claim about the codebase; there is no judgment call to delegate.
- `scope-guard.sh` and `spec-guard.sh` **ask** (`permissionDecision: "ask"`).
  Both cover decisions the specification says must be raised, not resolved
  (BRIEF §8) — so they put the call in front of a human rather than guessing.

## Layout

```
.claude/
├── MILESTONE            # current milestone; drives scope-guard and /milestone
├── settings.json        # permissions + hook wiring (committed)
├── settings.local.json  # machine-specific deny rules (gitignored)
├── agents/              # 5 subagents
├── disabled/            # agents kept but not scanned; see its README
├── commands/            # /check, /milestone, /commit, /pr
├── hooks/               # 11 sh hooks + the Python skill router
│   └── lib/             # hook_input, hook_ask, paths — shared, policy-free
└── skills/              # 9 skills + skill-rules.json
```

### The session-boundary hooks

Three hooks exist for a failure that is not a bug — work that is never verified,
and state the session never learns.

- `session-start.sh` (SessionStart) states the milestone, the branch, and whether
  `src/secrev/` and `.venv` exist. `MILESTONE` previously reached the agent only
  at write time, through a scope-guard prompt: it discovered which milestone it
  was in by being interrupted while leaving it.
- `session-end.sh` (Stop) is silent unless a file under `src/`, `tests/`,
  `patterns/` or `scripts/` changed after the last green gate. It reads the
  success marker `scripts/check.sh` writes to `hooks/state/gate-passed` — the
  one place the gate touches the harness. Advisory only: it is guarded, it never
  affects the gate's exit status, and nothing reads it in CI.
- `async-check-report.sh` (UserPromptSubmit) prints the background gate log once,
  when it is new. `async-check.sh` had been running ruff, pytest and the
  self-application check and writing the result to a log that nothing read.

All three keep their state in `hooks/state/`, gitignored by `.claude/.gitignore`
and created on demand. It was `$TMPDIR` first, which is wrong for a reason worth
keeping written down: `secrev-gate-passed` is a global name, so two clones of
this repo on one machine share it. The gate goes green in one checkout and the
Stop hook in the other reads that marker and stays quiet — a false all-clear,
which is the failure mode this project exists to notice.

## Committing and pushing

`/commit` runs the gate, then writes a message whose body is the *why* — usually
a spec reference. `/pr` checks four preconditions before it will do anything.

`settings.json` allows `git add`, branch creation and read-only `git`/`gh`
inspection. It deliberately does **not** allow `git commit` or `git push`:

- **push** is outward-facing. It goes in front of the user every time, and
  approval in one session is not approval in the next.
- **commit** is cheap to approve because it is rare, and it is the moment the
  user most wants to see. Auto-approving it buys one click and gives up the last
  checkpoint before work becomes history.

## Changing the harness

Editing `skill-rules.json` changes what Claude is *reminded* of. Editing the
PreToolUse guards changes what it is *allowed* to do. Keep the distinction: a
reminder that silently became an enforcement point is how a harness stops being
trusted.

`skills/skill-developer/` documents the skill and hook mechanisms in detail.
