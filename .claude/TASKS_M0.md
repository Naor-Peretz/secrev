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

- [x] **TASK-002B — Wire the instrument into the gate.** `attack.py` is stdlib, so this needs no
      `.venv` and is not blocked behind TASK-005. Until it lands, the guard assertions run only
      when someone remembers to run them — a check whose result no one sees is not a check
      (`async-check-report.sh`'s own header). Runs before the pytest stage; a missing `python3`
      exits 2, never 0 (H-1).
      *Files:* `scripts/check.sh`, `tests/harness/attack.py` (the wiring assertion).
      *Accept:* `sh scripts/check.sh` runs the assertions and reports them; defeating a guard
      turns the gate red, not just the driver.

- [x] **TASK-003 — `bash_guard.py`, the allowlist.** Item 1, highest severity. Allowlist of
      read-only commands (H-2); no write-verb list anywhere in the file. **Redirection and
      heredoc targets are resolved and treated as writes regardless of which command precedes
      them** — otherwise `cat > src/secrev/cli.py <<'EOF'` passes, since `cat` is allowlisted,
      and that is the brief's own test case. Unparseable command → refuse (H-1).
      *Files:* `.claude/hooks/bash-guard.sh`, `.claude/hooks/bash_guard.py`, `tests/harness/attack.py`.
      *Accept:* attack.py's heredoc case refuses; `cat` of the same path permits.

- [ ] **TASK-014 — `STACK.md` amendments.** The decisions come first: the document is binding,
      and the code follows it rather than the reverse. §2 gains `mypy`. §3 stops making `uv` the
      default — the objection was `curl | sh` (`net.fetch_exec`, a seed pattern), and with four
      dev dependencies `uv` buys nothing over stdlib `venv` anyway. §8 H-4 gains `.claude/`,
      H-5's glob form is corrected, and **H-9** is added.
      *Files:* `STACK.md` (spec-guard will ask on each edit — that is the mechanism working).
      *Accept:* each amendment carries its written reason; `secrev-invariants` skill still agrees
      with the document.

- [ ] **TASK-009B — Correct the glob form.** Follows H-5's correction in TASK-014.
      `*src/secrev/*.py` → `src/secrev/*.py|*/src/secrev/*.py`.
      *Files:* `.claude/hooks/lib/paths.sh`, `determinism-guard.sh`, `tests/harness/attack.py`.
      *Accept:* `transcripts/notes.py`, `descripts/a.py` and `foosrc/secrev/x.py` stop being
      refused; relative and absolute `src/secrev/*.py` still are.

- [ ] **TASK-004 — Execute category, and no operators near a protected path.** Two changes, one
      commit, because either alone is wrong.
      **Execute:** `sh <path.sh>` and `python3 <path.py>` permitted — running an existing script
      is not writing it. No token after the interpreter may start with `-`, so
      `python3 -c "open('scripts/check.sh','w')"` stays refused.
      **Operators:** any of `;` `&&` `||` `|` `` ` `` `$(` newline in a command touching a
      protected path is a refusal. Without this the execute category reopens exactly what the
      Bash guard closes: `sh scripts/check.sh; cat > src/secrev/x.py` has an allowlisted first
      command and the chain carries the write. This replaces the safe-separator design from
      TASK-003, and it costs read-only pipelines — `cat src/x.py | grep foo` is now refused.
      *Files:* `.claude/hooks/bash_guard.py`, `tests/harness/attack.py`.
      *Accept:* the chained-write case refuses; `sh scripts/check.sh` permits;
      `python3 -c` refuses.

- [ ] **TASK-004B — `.claude/` is a protected path.** Open question 4, decided. Bash writes to the
      harness refused; `Write`/`Edit` permitted, so repair stays possible and stays visible while
      the silent-disable path closes. Composition risk in the sense of PRD FR-0.8: one component
      able to disable another's control, neither defective alone.
      Note the set diverges — `.claude/` is protected against **Bash only**, so it belongs in
      `bash_guard.py` and not in `paths.sh`, which governs the Write/Edit hooks.
      *Files:* `.claude/hooks/bash_guard.py`, `tests/harness/attack.py`.
      *Accept:* `sed -i` on `bash-guard.sh` refuses; `cat` of it permits; a `Write` to it is
      untouched by this guard.

- [ ] **TASK-004C — Wire the `Bash` matcher.** The guard is not the control; the wiring is.
      *Files:* `.claude/settings.json`, `tests/harness/attack.py` (the last known-open inverts),
      `CLAUDE.md`.
      *Accept:* a live in-session heredoc to `src/secrev/cli.py` is refused (H-8), and
      `sh scripts/check.sh` still runs.

- [ ] **TASK-005 — `.venv`, and hooks that resolve it.** Decided: `python3-venv` + stdlib `venv`,
      not `uv`. Requires one command with `sudo`, which is the user's to run:
      `sudo apt install python3-venv`, then `python3 -m venv .venv` and
      `.venv/bin/pip install ruff pytest mypy`.
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

- [x] **TASK-007 — Remaining five hooks off `jq`.** After items 1 and 2, per the brief's ordering
      rule: converting hooks while the Bash bypass is open is "improving a mechanism that is not
      running."
      *Files:* the five hooks, plus `.claude/hooks/lib/hook_ask.py` (two of them used `jq -n`
      to *emit* the ask payload, so a reader alone did not finish the job) and
      `tests/harness/attack.py`.
      *Accept:* no hook *invokes* jq — not a raw grep, since six now carry a comment recording
      the removal. attack.py green.

- [x] **TASK-008 — Guard coverage: `+scripts/`, `+patterns/`.** Item 3. Note the brief's stated
      backstop is false: `self_check.py:18` scans `src/secrev` only, so nothing in the gate
      catches an `eval` in `scripts/`. The new coverage is the only control, not a second one.
      *Files:* `self-application-guard.sh`, `scope-guard.sh`, `.claude/hooks/lib/paths.sh`,
      `tests/harness/attack.py`.
      *Accept:* `eval(` into `scripts/self_check.py` is blocked. Note the two predicates are
      different sets on purpose: `patterns/` is in the scope guard's remit and out of the
      self-application guard's, because a catalog rule that detects `yaml.load` contains the
      string `yaml.load` — refusing it would read the tool's own input as if it were code.

- [x] **TASK-009 — Unanchor the path globs.** Item 6, H-5. `*/src/secrev/*.py` → `*src/secrev/*.py`.
      *Files:* `.claude/hooks/lib/paths.sh` (TASK-008 moved both globs there),
      `.claude/hooks/determinism-guard.sh`, `tests/harness/attack.py`.
      *Accept:* a relative `src/secrev/x.py` matches. See open question 9 for the over-match
      the literal form brings with it.

- [x] **TASK-010 — Scope guard refuses with no rules.** Item 4, H-6. Path filter must move
      *before* the milestone check, or exit 2 refuses every write in the repo.
      *Files:* `.claude/hooks/scope-guard.sh`, `tests/harness/attack.py`.
      *Accept:* `MILESTONE=M9` → write to `src/secrev/` exits 2; write to `README.md` untouched.
      A second H-1 breach was in the same two lines: `|| echo M1` meant an unreadable marker
      was treated as the one milestone it had rules for.

- [x] **TASK-011 — `MILESTONE` M1 → M0.** Separate from TASK-010 on purpose: flipping it before
      the guard refuses is what silently disables scope enforcement.
      *Files:* `.claude/MILESTONE`, `.claude/hooks/scope-guard.sh` (M0's rules — flipping the
      marker alone would refuse `scripts/check.sh`, which TASK-006 must edit; H-6's answer to
      "no rules" is to write them, not to leave the guard ruleless), `tests/harness/attack.py`.
      *Accept:* `session-start.sh` reports M0 and finds `BRIEF_M0.md`; M0 permits `scripts/`
      and refuses `src/` and `patterns/`.

- [x] **TASK-012 — Strip the restated stack section.** Item 7, H-7.
      `documentation-architect.md:11` carries a full `## Technology Stack`. **Open:** the brief
      also names `planner.md`, which is in `.claude/disabled/` where the recorded policy says a
      disabled agent keeps its section until restored. Whether DoD 9 reaches `disabled/` is a
      decision to raise, not to settle here.
      *Files:* `.claude/agents/documentation-architect.md`, `tests/harness/attack.py`.
      *Accept:* no live agent file restates a `STACK.md` mechanism. The copy was already
      stale in three ways when removed — see the receipt.

- [x] **TASK-013 — Documentation catches up.** `CLAUDE.md`'s hook table gains the Bash guard and
      its dependency paragraph loses jq; `.claude/README.md` likewise.
      *Files:* `CLAUDE.md`, `.claude/README.md`, `tests/harness/attack.py`.
      *Accept:* no stale jq reference; the M0 status table reflects what actually landed. Two
      further false claims were found while doing it — "the repository has no commits", and
      mypy being "recorded in STACK.md §2" (open question 10).

---

## Decided (2026-08-30)

- **OQ3 — `find`.** Stays out of the allowlist. "Except these flags" is a denylist over flags;
  `ls` and `rg` cover the need.
- **OQ4 — `.claude/` is a protected path.** Bash writes refused, `Write`/`Edit` permitted. The
  bootstrap objection dissolves: repair stays possible and stays visible, and the silent
  disable path closes. This is composition risk — one component able to disable another's
  control (PRD FR-0.8).
- **OQ9 — H-5's glob form was wrong.** `*src/secrev/*.py` catches `transcripts/`. Corrected in
  `STACK.md` to `src/secrev/*.py|*/src/secrev/*.py`, which meets the stated rationale without
  the over-match.
- **OQ10 — `mypy` enters `STACK.md` §2.** A defect in the document.
- **New: H-9.** Two findings of this milestone are one rule — a guard that returns a value the
  protocol gives no meaning to (`exit 5` from jq through `set -e`), and one that assumes the
  state instead of reading it (`|| echo M1`). Added to `STACK.md` §8.
- **`uv` is no longer the default.** The objection was to `curl | sh`, which is `net.fetch_exec`
  — one of the eight seed patterns. A project that scans for it and installs itself that way
  cannot defend itself. `pipx install uv` or apt fix the method; but with four dev dependencies
  `uv` buys nothing over stdlib `venv`, so `STACK.md` §3 is corrected.
- **OQ1 is closed by TASK-007**, not by a decision: the six hooks stopped calling jq, so
  `STACK.md` §2 became true. Left here because a resolved item that stays on an open list is
  the same drift this milestone exists to catch.

## Raised, not resolved (BRIEF §8)

1. PRD §13's build order runs M1–M12 and does not know M0 exists.
2. H-4 says `src/`; H-5 and every existing hook say `src/secrev/`. Which is the guard's set?
3. Does DoD 9 reach `.claude/disabled/`? See TASK-012.
4. `plan-reviewer.md` §4 lists §2.1's constructs while citing it — checklist or restatement?
5. The trigger "command references a protected path" is a denylist over path *spellings*
   (`$HOME/...`, globs, variables, string concatenation). Inherited from H-2, not invented here,
   but it means the guard fails open on any spelling it does not recognise.
6. **Residual risk, recorded so it is not rediscovered.** A script under `scripts/` can write
   anywhere, so there is a chain: write a script, then run it. Not a bypass — the first link is
   guarded, and the execute category permits running an existing script, never creating one —
   but the risk is real and belongs in writing rather than in someone's memory.
