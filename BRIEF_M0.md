# Brief — M0: Harness Repair

**Milestone:** M0 — precedes M1
**Prerequisites:** `STACK.md` §8 (binding)
**Goal:** make the development harness actually enforce what it claims to enforce.

---

## Why this comes before M1

The harness currently reports success in situations where it has verified nothing. Three separate
mechanisms do this — an uncovered write path, a swallowed tool failure, and a silent scope exit —
and all three look identical from outside: green.

Writing code under a harness in that state is worse than writing code under no harness, because
the green result is taken as evidence. Fix the harness first.

The order below is by *what fails silently*, not by effort. Items 1 and 2 must land before any
other work; until they do, the remaining fixes improve a mechanism that is not running.

---

## 0. The rule that governs the rest

Add to the harness conventions before making any individual fix:

> **A check that could not run exits 2. It never exits 0.**

Items 1, 4 and 6 below are three instances of violating this. Fixing them individually without
stating the rule guarantees a fourth instance next time. Recorded as H-1 in `STACK.md` §8.

---

## 1. Close the Bash bypass  — *highest severity*

**Problem.** Guards hook `Write|Edit|MultiEdit` only. Writes performed through `Bash` — heredoc,
`tee`, `sed -i`, `>` — bypass all three. This is not theoretical: the active configuration
instructs the agent to prefer Bash for edits, so in that configuration the harness is fully
transparent while still reporting green.

**Fix.** A `PreToolUse` hook on `Bash`.

**Approach — allowlist, not denylist (H-2).** If the command references any path under
`src/secrev/`, `patterns/`, or `scripts/`, permit it only when the invoked command is in a
known-read-only set (`cat`, `grep`, `head`, `tail`, `wc`, `ls`, `find`, `git diff`, `git log`,
`rg`). Refuse otherwise.

Do **not** attempt to detect write operations. That list — `tee`, heredocs, `sed -i`, `>`, `>>`,
`cp`, `mv`, `install`, `python -c`, `dd` — does not close. If you find yourself adding another
verb to a block list, the polarity is wrong. This is P3 applied to our own tooling: the project's
founding finding was a denylist bypass, and reproducing that pattern in the harness that guards
the project would be difficult to defend.

**Verify.** Attempt to modify `src/secrev/cli.py` via heredoc. It must be refused.

---

## 2. Create the virtualenv and fail loudly  — *second highest*

**Problem.** No `.venv` exists, so hooks fall back to system `python3`. `async-check.sh` runs
without `ruff` or `pytest` available and swallows the failure with `|| true`. It currently checks
nothing and says so to no one.

**Fix.**
1. `uv venv` and install `ruff` and `pytest`.
2. Hooks resolve the interpreter from `.venv` explicitly, not from `PATH`.
3. Remove every `|| true` from quality checks. If a tool is missing, exit 2 with a message naming
   the tool.

**Verify.** Temporarily rename the `ruff` binary and run the check. It must fail loudly rather
than pass.

---

## 3. Extend guard coverage to `scripts/` and `patterns/`

**Problem.** Self-application guards cover `src/secrev/*.py` only. `scripts/self_check.py` could
acquire an `eval` with no hook objecting — the gate catches it later, after the fact.

**Fix.** Add both directories to every relevant guard.

`patterns/` matters at least as much as the code: it is the tool's input, and a rule added or
altered without review is a check that silently disappears from every subsequent run.

---

## 4. Make the scope guard refuse when it has no rules

**Problem.** `[ "$MILESTONE" = "M1" ] || exit 0` — the moment `MILESTONE` advances, scope
enforcement vanishes with no signal.

**Fix.** `exit 2` with a message stating that no scope rules exist for the current milestone. A
guard that does not know what is permitted has not concluded that everything is (H-6).

---

## 5. Remove the `jq` dependency

**Problem.** Six hooks depend on `jq`. It is undeclared, in a repository whose stack file requires
a written reason for every dependency, and it is a non-Python external tool — precisely what the
prefer-Python rule exists to avoid.

**Fix.** Replace with `python3 -c` JSON parsing. Prefer removal to documentation here; the
dependency buys nothing that stdlib `json` does not.

---

## 6. Drop the leading anchor from path globs

**Problem.** `*/src/secrev/*.py` does not match a relative `src/secrev/foo.py`. It works today
only because the client sends absolute paths — an undocumented reliance on client behaviour.

**Fix.** `*src/secrev/*.py` (H-5). One character; do not skip it.

---

## 7. De-duplicate the stack section from agent definitions

**Problem.** `planner.md` and `documentation-architect.md` each carry a copy of the technology
section. When `STACK.md` changes, both copies become quietly wrong.

**Fix.** Replace each copy with a reference to `STACK.md`. It is declared binding; a stale copy
contradicts that (H-7).

---

## Definition of done

- [ ] A heredoc write to `src/secrev/cli.py` is refused by the Bash guard.
- [ ] The Bash guard is an allowlist of read-only commands, with no list of blocked write verbs.
- [ ] `.venv` exists with `ruff` and `pytest`; hooks resolve the interpreter from it.
- [ ] No `|| true` remains on any quality check; a missing tool exits 2 with its name.
- [ ] Guards cover `src/secrev/`, `scripts/`, and `patterns/`.
- [ ] The scope guard exits 2 with a message when `MILESTONE` has no rules.
- [ ] No hook invokes `jq`.
- [ ] Path globs have no leading anchor.
- [ ] No agent definition restates `STACK.md` content.
- [ ] **Each guard has been deliberately attacked and observed to refuse** (H-8). A guard nobody
      has tried to defeat is an assumption, not a control.

---

## Note

These eight items were found by reading the harness as an assembled set of agentic components —
which is what `environment` mode (PRD §6, Phase 0.5) is specified to do automatically. Item 1 in
particular is a textbook composition risk: one component can reach around the path another
component guards, and neither is defective on its own. Worth revisiting this brief when Phase 0.5
is built, as a ground-truth case the tool should have produced by itself.
