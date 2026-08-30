# M0 task ledger — harness repair

Scope: `BRIEF_M0.md` items 0–7 + its Definition of done. Mechanism: `STACK.md` §8 (H-1…H-8).

**This file is the ledger. `.claude/MILESTONE` is not.** That file holds a single token and is
`cat`-ed by `scope-guard.sh:17` (exact string compare), `session-start.sh:14` (brief filename),
`plan-review.sh:13`, and `commit.md:51` (branch name). A checklist there makes the compare fail,
which exits 0, which silently removes scope enforcement — H-6, and the thing M0 is fixing.

Gate for every task: `sh scripts/check.sh`. There is no Makefile.

One task per iteration. Do not start a second.

---

- [x] **TASK-000 — Baseline commit.** No behaviour change. The repo has zero commits, so the
      first M0 change would otherwise be "initial commit + a fix": unreviewable as a diff and
      unrevertable. *Files:* none (snapshot only).
      *Accept:* `git rev-list --count HEAD` = 1; `git status --porcelain` empty; gate green.

- [x] **TASK-001 — `tests/harness/attack.py`, the instrument.** Stdlib-only Python, runnable as
      `python3 tests/harness/attack.py` with no venv, and collectable by pytest later. Feeds
      crafted PreToolUse JSON on stdin to each guard and asserts exit codes. Characterizes the
      harness *as it is* — it must be green before anything it measures changes. `subprocess`
      with argument lists only, never a shell string (`STACK.md` §2.1).
      *Files:* `tests/harness/attack.py`.
      *Accept:* green against the unmodified harness; red if any guard's exit code is edited.

- [x] **TASK-002 — `hook_input.py` + one hook off `jq`.** The shared stdin-JSON reader, proven on
      `self-application-guard.sh`. Owns parsing only; knows no policy.
      *Files:* `.claude/hooks/lib/hook_input.py`, `.claude/hooks/self-application-guard.sh`,
      `tests/harness/attack.py` (the assertion; the original list omitted it, which would have
      left a behaviour change unasserted).
      *Accept:* attack.py green; the hook makes no `jq` call. Not a raw `grep jq` — the comment
      recording the removal contains the word, and a criterion that forbids documenting the
      change is the wrong criterion.

- [ ] **TASK-002B — Wire the instrument into the gate.** `attack.py` is stdlib, so this needs no
      `.venv` and is not blocked behind TASK-005. Until it lands, the guard assertions run only
      when someone remembers to run them — a check whose result no one sees is not a check
      (`async-check-report.sh`'s own header). Runs before the pytest stage; a missing `python3`
      exits 2, never 0 (H-1).
      *Files:* `scripts/check.sh`.
      *Accept:* `sh scripts/check.sh` runs the 16 assertions and reports them; defeating a guard
      turns the gate red, not just the driver.

- [ ] **TASK-003 — `bash_guard.py`, the allowlist.** Item 1, highest severity. Allowlist of
      read-only commands (H-2); no write-verb list anywhere in the file. **Redirection and
      heredoc targets are resolved and treated as writes regardless of which command precedes
      them** — otherwise `cat > src/secrev/cli.py <<'EOF'` passes, since `cat` is allowlisted,
      and that is the brief's own test case. Unparseable command → refuse (H-1).
      *Files:* `.claude/hooks/bash-guard.sh`, `.claude/hooks/bash_guard.py`, `tests/harness/attack.py`.
      *Accept:* attack.py's heredoc case refuses; `cat` of the same path permits.

- [ ] **TASK-004 — Wire the `Bash` matcher.** The guard file is not the control; the wiring is.
      *Files:* `.claude/settings.json`.
      *Accept:* a live in-session heredoc to `src/secrev/cli.py` is refused (H-8).

- [ ] **TASK-005 — `.venv`, and hooks that resolve it.** BLOCKED: `uv` is absent and
      `python3 -m venv` fails here (no `ensurepip`; Ubuntu ships it as `python3-venv`). Needs a
      decision on the machine before it can run.
      *Files:* `.claude/hooks/async-check.sh`, `determinism-guard.sh`, `skill-activation.sh`.
      *Accept:* `.venv/bin/python -m ruff --version` succeeds; no hook falls back to `PATH`.

- [ ] **TASK-006 — The gate stops lying about missing tools.** Today `check.sh` prints
      `skipped: not installed` for ruff, mypy and pytest and still reaches `all gates pass`.
      Missing tool → exit 2 naming it. "Nothing to check yet" stays a legitimate skip; "cannot
      check" does not. Name the pytest branch specifically — `[ -d tests ] && pytest --version`
      collapses both states into one message. **After TASK-005**: `.githooks/pre-commit` runs
      this gate, so making it strict first blocks every commit.
      *Files:* `scripts/check.sh`.
      *Accept:* with `ruff` unavailable the gate exits 2 naming ruff, not 0.

- [ ] **TASK-007 — Remaining five hooks off `jq`.** After items 1 and 2, per the brief's ordering
      rule: converting hooks while the Bash bypass is open is "improving a mechanism that is not
      running."
      *Files:* `scope-guard.sh`, `spec-guard.sh`, `plan-review.sh`, `determinism-guard.sh`, `async-check.sh`.
      *Accept:* `grep -rn jq .claude/hooks/` empty; attack.py green.

- [ ] **TASK-008 — Guard coverage: `+scripts/`, `+patterns/`.** Item 3. Note the brief's stated
      backstop is false: `self_check.py:18` scans `src/secrev` only, so nothing in the gate
      catches an `eval` in `scripts/`. The new coverage is the only control, not a second one.
      *Files:* `self-application-guard.sh`, `scope-guard.sh`, `.claude/hooks/lib/paths.sh`.
      *Accept:* `eval(` into `scripts/self_check.py` is blocked.

- [ ] **TASK-009 — Unanchor the path globs.** Item 6, H-5. `*/src/secrev/*.py` → `*src/secrev/*.py`.
      *Files:* `self-application-guard.sh`, `scope-guard.sh`, `determinism-guard.sh`.
      *Accept:* a relative `src/secrev/x.py` matches.

- [ ] **TASK-010 — Scope guard refuses with no rules.** Item 4, H-6. Path filter must move
      *before* the milestone check, or exit 2 refuses every write in the repo.
      *Files:* `.claude/hooks/scope-guard.sh`.
      *Accept:* `MILESTONE=M9` → write to `src/secrev/` exits 2; write to `README.md` untouched.

- [ ] **TASK-011 — `MILESTONE` M1 → M0.** Separate from TASK-010 on purpose: flipping it before
      the guard refuses is what silently disables scope enforcement.
      *Files:* `.claude/MILESTONE`.
      *Accept:* `session-start.sh` reports M0 and finds `BRIEF_M0.md`.

- [ ] **TASK-012 — Strip the restated stack section.** Item 7, H-7.
      `documentation-architect.md:11` carries a full `## Technology Stack`. **Open:** the brief
      also names `planner.md`, which is in `.claude/disabled/` where the recorded policy says a
      disabled agent keeps its section until restored. Whether DoD 9 reaches `disabled/` is a
      decision to raise, not to settle here.
      *Files:* `.claude/agents/documentation-architect.md`.
      *Accept:* no live agent file restates a `STACK.md` mechanism.

- [ ] **TASK-013 — Documentation catches up.** `CLAUDE.md`'s hook table gains the Bash guard and
      its dependency paragraph loses jq; `.claude/README.md` likewise.
      *Files:* `CLAUDE.md`, `.claude/README.md`.
      *Accept:* no stale jq reference; the M0 status table reflects what actually landed.

---

## Raised, not resolved (BRIEF §8)

1. `STACK.md` §2 describes jq as already removed, past tense, while six hooks use it.
2. PRD §13's build order runs M1–M12 and does not know M0 exists.
3. `find` is in the brief's read-only allowlist and has `-delete` and `-exec`. Permitting it minus
   those flags is a denylist over flags (P3), so "special-case it" is not the neutral option.
   Left out of TASK-003's allowlist pending an answer.
4. Is `.claude/` a protected path? H-4 says `src/`, `patterns/`, `scripts/`. A Bash write to
   `bash-guard.sh` disables the control and nothing objects. Bootstrap problem is real.
5. H-4 says `src/`; H-5 and every existing hook say `src/secrev/`. Which is the guard's set?
6. Does DoD 9 reach `.claude/disabled/`? See TASK-012.
7. `plan-reviewer.md` §4 lists §2.1's constructs while citing it — checklist or restatement?
8. The trigger "command references a protected path" is a denylist over path *spellings*
   (`$HOME/...`, globs, variables, string concatenation). Inherited from H-2, not invented here,
   but it means the guard fails open on any spelling it does not recognise.
