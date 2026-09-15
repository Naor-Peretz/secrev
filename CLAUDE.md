# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

`src/secrev/` holds the whole M1 pipeline — `inventory`, `ids`, `catalog`, `sweep`, `recon`,
`cli` — and `secrev recon` and `secrev sweep` run. `patterns/` ships nine patterns in two packs
(`_base.yaml`, `python.yaml`). Both gates are green and every stage has something to check,
including the artifact half of the determinism stage, which compares real `recon.json` and
`hits.jsonl` output.

**Nothing of M2 exists yet** — no `surfaces.py`, no `.claude/TASKS_M2.md`. `BRIEF_M2.md` §2 was
derived from the PRD rather than from building anything, and says it should be reviewed before
anyone builds against it. The next step is `/milestone`, not code.

M0 and M1 reached `main` as PR #1, merged from `m0/harness-repair` — a name that stopped describing
the branch when M0 closed, so M2 starts on a fresh one. The remote is `github.com/Naor-Peretz/secrev`,
**private**. CI first ran on 2026-09-15 and found four things no local run could: `harness.yml`
never installed the project, so the determinism guard could not import it; a test assumed a
case-sensitive filesystem and failed on APFS; and CodeQL could neither upload (code scanning on a
private repository is paid) nor pass `security-and-quality` over fixtures that are bad code on
purpose. All four are fixed, and every workflow was green on the head that was merged.

TASK-M1-010, the macOS box in M2's Definition of done, now has evidence and is **still not
ticked**. Linux and macOS produced byte-identical `recon.json` and `hits.jsonl` — but the fixture
tree's only non-ASCII name is committed in NFC, so a decomposed name arriving from outside has never
been exercised on either platform. The dependable evidence is a test that creates the NFD spelling
at runtime and asserts it derives the same candidate id as the NFC one.

`.venv` is stdlib `venv` — `STACK.md` §3 no longer makes `uv` the default, because `uv`'s
advertised install pipes a fetched script into a shell, which is `net.fetch_exec`, one of the nine
patterns this tool ships.

### The current milestone is M2

`.claude/MILESTONE` reads `M2`, and **M0 and M1 are closed** — every box in the Definition of done
of `BRIEF_M0.md` and `BRIEF_M1.md` is ticked, with per-task receipts in `.claude/receipts.md` and
the ledgers in `.claude/TASKS_M0.md` and `.claude/TASKS_M1.md`. One obligation was carried rather
than done, by owner decision: TASK-M1-010's macOS run, which now lives as a box in `BRIEF_M2.md` §4
because a carried obligation that lives only in a commit message stops being one.

That marker is the harness's only notion of where the project is, and it has been wrong in both
directions: it read `M1` through the whole of M0, so `scope-guard.sh` policed a boundary the project
had not reached; leaving it at `M0` after M0 closed would have refused every write to `src/` and
`patterns/`, which is exactly what M1 is. **Move it when a milestone closes.** It holds a single
token — `scope-guard.sh` compares it by exact string and `commands/commit.md` pipes it through `tr`
to build a branch name — so a checklist does not go in it.

Moving it forward write-locks the scoped tree until the next brief exists. `scope-guard.sh` ends in
`*) refuse_no_rules`, so between M1 closing and `BRIEF_M2.md` being written every write to `src/`
was refused (H-6). **The remedy is to write the next brief and give the guard its rules — never to
move the marker back to buy write access.** Under M2 the guard permits `src/` and refuses
`patterns/`: M2 adds a candidate source, not rules. An assertion in `attack.py` refuses any unticked
Definition-of-done box in a brief below the marker, so the marker cannot pass an unfinished
milestone.

M0 delivered, beyond its own list: `.claude/` entered the protected set, `STACK.md` §8 gained
**H-9**, and three of the brief's own premises turned out to be wrong — the gate never caught an
`eval` in `scripts/`, `|| true` was not the only way a status was lost (`cmd | head` discards it
just as completely, twice), and the read/write allowlist needed a third category for *executing* a
script. `BRIEF_M0.md`'s closing note records all three.

### How M1 was built, and what carries into M2

`BRIEF_M1.md` §2 lists the deliverable tree alphabetically. That is not a sequence, and following it
puts `cli.py` first. The order is in `.claude/TASKS_M1.md`, and the reason is worth carrying:

**`inventory.py` first, and its determinism test before it.** It is the only file that
concentrates the decisions that cannot be changed afterwards — traversal order, NFC normalisation,
exclusions, binary detection, symlinks. `recon.py` and `sweep.py` are both consumers of the walk:
right, and they inherit it free; wrong, and both are rewrites. `ids.py` comes before `sweep.py` for
the same reason — an identity derived from a traversal counter looks correct until something is
inserted ahead of it. `cli.py` is last.

A determinism check written after the generators exist is a retrofit onto code composed without
it, and NFR-3 is the one requirement that does not survive being retrofitted: getting it wrong
invalidates every verification recorded above it (D-4).

**The same holds for M2.** `surfaces.py` is a third consumer of the walk and a third generator of
ids in `hits.jsonl`, so its golden test comes before it. It also has to be added to `is_nfr3_path`
in `.claude/hooks/lib/paths.sh`, which names `ids.py`, `inventory.py`, `sweep.py` and `recon.py`
exactly — until then `determinism-guard.sh` stays silent on edits to it.

The gate enforces the order mechanically. The determinism stage keys on `src/secrev/inventory.py`,
not on the `src/secrev/` directory — a directory appears with the *first* file, so the
directory-shaped condition would have kept printing "nothing to compare" for exactly as long as the
NFR-3 rules were being written.

**One assertion in `tests/test_determinism.py` is a test of a test.** `sorted()` was removed
deliberately and most of that file stayed green: two walks of one tree agree whether or not the
output is sorted, because `os.walk` is stable within a machine. Only the explicit
`paths == sorted(paths)` caught it — and that assertion is worth nothing if the fixture tree's raw
traversal order ever coincides with sorted order, so a separate assertion holds that apart. A
50-file tree written in opposite orders was tried and **does not** catch it on ext4, whose
directory index orders by a hash of the name; it is kept as a cross-filesystem canary and is
labelled as not being the control.

**The Bash bypass is closed.** `bash-guard.sh` is wired as a `PreToolUse` matcher on `Bash`, and a
write to `src/`, `patterns/`, `scripts/` or `.claude/` through a shell is refused.

What it permits beside a protected path: the read-only set (`cat`, `grep`, `head`, `tail`, `wc`,
`ls`, `rg`, `git diff`, `git log`), and running an existing script — `sh <x.sh>`, `python3 <x.py>`
with no flag after the interpreter. What it refuses: everything else, **and every shell operator**.
No `;`, `&&`, `||`, `|`, newline, redirect, subshell or substitution, because each of those carries
a write past the command that was actually checked. That costs read-only pipelines: `cat src/x.py |
grep foo` is refused, and reading a protected file takes one command or the `Read` tool.

`find` is deliberately absent from the read-only set — it carries `-delete` and `-exec`, and
admitting it "minus those flags" would be a denylist over flags (P3).

`.claude/` is protected against `Bash` only. A `Write` or `Edit` to a guard is untouched by this
hook and passes in front of the ones that watch writes, so repairing the harness stays possible and
stays visible while the silent-disable path closes.

M0 exists because a harness that reports green while verifying nothing is worse than no harness:
the green is taken as evidence.


## Development environment

```
sh scripts/check.sh                    # the gate — exactly what CI runs, no second list
sh scripts/check.sh --fast             # what pre-commit runs: no pytest, determinism or audit
sh scripts/check.sh --sast             # the gate plus CodeQL (minutes; CI runs it every push)
python3 scripts/self_check.py          # STACK.md §2.1 alone (AST-based, not grep)
python3 scripts/determinism_check.py   # NFR-3 alone: two runs byte-identical + stable ids
python3 scripts/license_check.py       # licence allowlist alone (STACK.md §2.2)
python3 scripts/deps_audit.py          # known-vulnerability audit alone (needs the network)

python3 -m venv .venv                  # env (STACK.md §3); needs the python3-venv package
.venv/bin/pip install -e '.[dev]'      # uv is permitted, but is not the default
pytest                                 # all tests
pytest tests/test_sweep.py::test_name  # a single test

python3 -m venv .venv-audit            # the supply-chain tooling, kept out of .venv (§2.2)
.venv-audit/bin/pip install -r .github/requirements/audit.txt
```

`--sast` needs the CodeQL CLI, which nothing here installs either. Pinned and hash-verified against
the checksum GitHub publishes beside the bundle, the same discipline as `gitleaks`:

```
V=2.26.4; B=codeql-bundle-linux64.tar.zst
curl -fsSL -O "https://github.com/github/codeql-action/releases/download/codeql-bundle-v$V/$B"
curl -fsSL -O "https://github.com/github/codeql-action/releases/download/codeql-bundle-v$V/$B.checksum.txt"
sha256sum -c "$B.checksum.txt" && tar --zstd -xf "$B" -C ~/.local/share/
```

`check.sh` looks for `~/.local/share/codeql/codeql` — the bundle's top-level `codeql/` directory
holds the CLI directly, so that is where the `tar` above puts it — or `$CODEQL_BIN`. Point it at the real
binary inside the extracted bundle, never at a symlink to it: the CLI resolves its query packs
relative to its own location, so a lone symlinked executable reports `codeql/python-queries cannot
be found` — which is "could not run", and the stage correctly exits 2 rather than calling it clean.

`gitleaks` is an external binary and nothing here installs it. Pinned, hash-verified, the
same way CI does it — `brew install gitleaks` is equivalent on macOS:

```
V=8.30.1; SHA=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  # linux_x64
curl -fsSL -o gl.tgz "https://github.com/gitleaks/gitleaks/releases/download/v$V/gitleaks_${V}_linux_x64.tar.gz"
printf '%s  gl.tgz\n' "$SHA" | sha256sum -c - && tar -xzf gl.tgz gitleaks && mv gitleaks ~/.local/bin/
```

The dev set is `pytest`, `ruff` and `mypy`, all recorded in `STACK.md` §2 with reasons —
`mypy` only since TASK-014, having been configured and run for some time while appearing
nowhere in the binding document. `pip-audit`, `pip-licenses` and `gitleaks` are §2.2, and
the first two live in `.venv-audit` rather than `.venv`: they carry 29 transitive packages
including a network client stack, and the environment that vouches for the code should hold
only packages someone chose.

`uv` is permitted but is no longer the default (§3). Its advertised install pipes a fetched
script into a shell, which is `net.fetch_exec` — one of the nine patterns this tool
ships. The objection is to the method, not the tool.

The gate runs, in order: `ruff format --check`, `ruff check`, `mypy --strict`, `pytest`, the
self-application check, the secrets scan (`gitleaks dir`), the licence allowlist, the
determinism check, and the dependency audit.

### Two gates, and neither calls the other

| | `scripts/check.sh` | `.claude/check.sh` |
|---|---|---|
| Question | Is the software correct? | Does the tooling still refuse what it claims to? |
| Covers | `src/`, `tests/`, `scripts/`, `patterns/` | `.claude/`, `tests/harness/` |
| Config | `pyproject.toml` | `.claude/ruff.toml` |
| CI | `ci.yml` — every push | `harness.yml` — pushes touching those paths |
| Run by | `.githooks/pre-commit`, `pre-push` | `/check`, CI |

The guard assertions used to be stage 4 of the product gate, and the product gate used to write
its success marker into `.claude/hooks/state/`. Both are gone. `.claude/` is the layer that
*writes* this project; `src/` is the project. A stage asserting that a `PreToolUse` hook still
refuses a heredoc is not an answer to "is the software correct", and a contributor without Claude
Code should not have their build fail on a layer they never run.

The marker is now `.gate-passed`, in the product's own space. **Reading across the boundary is
fine — the harness reads it. Writing across it is not.** An assertion in `attack.py` fails if
`scripts/check.sh` mentions `.claude` outside a comment, because nobody deletes a boundary
deliberately; someone adds one convenient line.

Two stages are absent from the harness gate and say so rather than being omitted: no dependency
audit, no licence check, because the harness is stdlib throughout. A third-party import there
would put a package on the critical path of every prompt in every session.
`--sast` appends CodeQL. Every stage now has something to check.

The last four are STACK.md §2.2 and came from comparing this gate against a mature
JavaScript project's CI (format → lint → build → test → outdated → audit → licences →
gitleaks → CodeQL). Two things did not come across. Its pre-push hook prints
`⚠️ not installed - skipping` for gitleaks and CodeQL and still reaches `✅ All CI checks
passed`, which is the H-1 collapse this harness exists to prevent — here a missing tool
exits 2. And its blocking outdated-dependency check is deliberately absent: it turns a build
red for a release nobody in this repository made, which is the drift
`.github/requirements/dev.txt` was pinned to avoid. Dependabot answers that question as a PR.

`self_check.py` is AST-based on purpose. `shell=True` is a structure question, and a grep here
would be the exact mistake the catalog is designed not to make. The crude grep-shaped check inside
`check.sh` is a separate backstop; both must pass and neither replaces the other.

### The gate runs in three places

| Where | What runs | Why there |
|---|---|---|
| `.githooks/pre-commit` | `check.sh --fast` | Format, lint, types, guards, self-application, secrets, licences. Cheap enough that nobody learns to type `--no-verify` |
| `.githooks/pre-push` | `check.sh` (full) | The last point before code leaves the machine. Adds pytest, determinism, and the dependency audit |
| `.github/workflows/ci.yml` | `check.sh` (full) | On **every push to every branch** except `dependabot/**` (built through its PR instead, not twice), every PR, and `workflow_dispatch` |

`--fast` is a prefix of the same list, not a second list: nothing reaches a remote on its
strength, because pre-push and CI both run the whole thing. `--fast` also does not write the
`gate-passed` marker — a partial run must not read as a verified one.

The secrets scan is in the fast half on purpose: `gitleaks dir` reads the working tree, so it
catches a credential at the commit that would have introduced it rather than after it is
history, where removal is a rewrite and the credential is burned anyway. The dependency audit
is out of it for the opposite reason — it queries OSV, a push has a network by definition and
a commit does not, and a stage that fails offline teaches people to bypass the hook.

`git config core.hooksPath .githooks` is set. Both hooks honour `--no-verify`, which is not a
bypass so much as a deferral: CI runs the identical gate and says so.

### What CI covers beyond the gate

| Job | Asserts |
|---|---|
| `gate` | The full gate on ubuntu + macos × 3.11 + 3.12 |
| `install-paths` | Both documented pip routes work: `pip install -e .` and `pip install -e '.[dev]'` (STACK.md §3) |
| `catalog` | A malformed catalog exits **2** *and* names the offending pattern id (BRIEF §4, §7) |
| `cross-platform-determinism` → `compare-platforms` | The artifact hashes from Linux and macOS are identical |
| `codeql.yml` | Dataflow analysis over the Python source, on every push and weekly. Default suite, `tests/fixtures` excluded — both in `.github/codeql/codeql-config.yml`, which `--sast` reads too. Nothing is uploaded (code scanning on a private repository is paid), so the job judges its own SARIF with `scripts/codeql_check.py --sarif`. No `continue-on-error` |

NFR-3 says byte-identical "across runs and machines". A single-platform check cannot see the
NFC/NFD divergence, so the cross-platform comparison is the one that actually tests it.

**Every action is pinned to a commit SHA**, never a tag. `@v4` resolves to whatever the maintainer
last pointed it at — a remote code reference that can change with no diff here. Five actions are
used at all (four in `ci.yml`, `codeql-action` twice in `codeql.yml`), and that is deliberate: each
one is third-party code with access to the checkout. `gitleaks` is installed from a pinned,
hash-verified release tarball rather than through `gitleaks/gitleaks-action`, for the same reason.
Dependabot (`.github/dependabot.yml`) moves the pins forward as PRs someone reads.

**The dev toolchain is pinned** in `.github/requirements/dev.txt`, and the supply-chain tooling
in `.github/requirements/audit.txt`. Unpinned, every CI run resolved
whatever ruff and mypy were newest, so the rules the gate enforces could change with no commit to
explain it. Not hash-locked yet — `--require-hashes` is the next step, and the file says so rather
than overstating what it provides.

`uv` is deliberately absent from CI. §3 permits it but does not depend on it, so installing it to
prove a path the document declined to require would add a supply-chain surface for nothing.

### What the `.claude/` harness enforces

`bash-guard.sh` covers `Bash`; every other `PreToolUse` row covers `Write|Edit|MultiEdit`. Between
them, no tool that can write to a protected path is unwatched (H-3).

| Hook | Event | Effect |
|---|---|---|
| `bash-guard.sh` | PreToolUse Bash | **Refuses** a Bash command touching `src/`, `patterns/`, `scripts/` or `.claude/` unless it reads (allowlisted command) or runs an existing script (`sh <x.sh>`, `python3 <x.py>`, no flags). Every shell operator refuses — chaining carries a write past the command that was checked |
| `self-application-guard.sh` | PreToolUse Write/Edit | **Blocks** a write that would put `eval`, `exec`, `pickle`, `shell=True`, `yaml.load`, `Loader=`, or a network client into Python under `src/` or `scripts/` |
| `scope-guard.sh` | PreToolUse Write/Edit | **Asks** when a write reaches past the milestone in `.claude/MILESTONE`; **refuses** when that milestone has no rules (H-6) |
| `spec-guard.sh` | PreToolUse Write/Edit | **Asks** before any edit to the PRD, `STACK.md`, or a brief, restating precedence |
| `determinism-guard.sh` | PostToolUse | Re-runs the determinism check when `ids.py`, `inventory.py`, `sweep.py` or `recon.py` is touched |
| `async-check.sh` | PostToolUse | Runs ruff + pytest + self-check in the background, debounced |
| `plan-review.sh` | PostToolUse ExitPlanMode | Routes every plan through the `plan-reviewer` agent before code |
| `skill-activation.sh` | UserPromptSubmit | Surfaces the project skills that apply to the prompt |
| `async-check-report.sh` | UserPromptSubmit | Prints the background gate log once, when it is new |
| `session-start.sh` | SessionStart | States milestone, branch and uncommitted count, points at the milestone's brief (or says it is absent), and warns when `src/secrev/` or `.venv` is missing |
| `session-end.sh` | Stop | Silent unless a source file changed after the last green gate |

Agents: `plan-reviewer`, `python-reviewer`, `gate-resolver`, `documentation-architect`,
`web-research-specialist`. Planning is the built-in `Plan` agent plus `/milestone`;
`architect` and `planner` are in `.claude/disabled/` with the reason.
Skills: `secrev-invariants`, `pattern-author`, `testing-contract`, `spec-precedence`,
`debugging`, plus `skill-developer`, `iterative-retrieval`, `eval-harness`,
`strategic-compact`.
Commands: `/check`, `/milestone`, `/commit`, `/pr`.

`.claude/MILESTONE` drives `scope-guard.sh` and `/milestone`. It is the harness's only notion of
where the project is; setting it forward past an unfinished milestone disables the guard for
everything that milestone was supposed to police.

### Harness state and what is committed

Hook state — the background gate log, its seen-marker, and the `gate-passed` marker — lives in
`.claude/hooks/state/`, created on demand. It was `$TMPDIR` first, which is wrong for a reason
worth keeping: `secrev-gate-passed` is a global name, so two clones on one machine share it, one
checkout's green run silences the other's Stop hook, and the result is a false all-clear.

`scripts/check.sh` writes that marker on its exit-0 path. It is the one place the project gate
touches the harness — guarded by `[ -d .claude/hooks ]`, advisory, never affecting exit status.

Two `.gitignore` files, deliberately: the root one covers the **project** (venv, build output,
tool caches, `.security-review/`, credentials); `.claude/.gitignore` covers the **harness that
writes the project** (`settings.local.json`, `hooks/state/`). A rule about how code gets written
should never have to be read as a rule about the code. The rest of `.claude/` is committed — a
contributor who clones without it loses every guard while the gate still says green.

`settings.json` allows `git add`, branch creation, and read-only `git`/`gh`. It deliberately does
not allow `git commit` or `git push`: push is outward-facing and is asked every time, and commit is
the last checkpoint before work becomes history.

## The binding documents and their precedence

| File | Role |
|---|---|
| `REQUIREMENTS_security-review-skill.md` | PRD — *why*. Principles P1–P11, FRs by phase, data contracts (§7), guardrails G-1…G-6, NFRs, build order M1–M12, decisions D-2…D-12. |
| `STACK.md` | Binding stack/environment decisions — *mechanism*. Applies to every milestone. §8 binds the harness itself (H-1…H-9). |
| `BRIEF_M0.md` | Harness repair. Closed. |
| `BRIEF_M1.md` | The pattern sweep — the first milestone that produced `src/secrev/`. Closed. |
| `BRIEF_M2.md` | The surface source. **Current.** §1 and §4 bind; §2 is PRD-derived and unreviewed. |

Resolution order: **a brief loses to `STACK.md`; `STACK.md` loses to the PRD on intent and wins on
mechanism.** Where a brief and the PRD conflict, raise it rather than silently resolving — a
conflict usually means the PRD needs a correction, and resolving it loses that signal
(`BRIEF_M1.md` §8).

## What is being built

`secrev`, a Python CLI backing a Claude Code skill that reviews *agentic artifacts* (skills, MCP
servers, subagents, hooks, agent configs, plugins, CLI tools) for security issues. The thesis is
method, not detection: every candidate is resolved rather than dropped, review scope is set
independently of what the pattern catalog matched, and verifications are scoped and expire.

Pipeline — three peer candidate sources (D-11) feed one ledger, `hits.jsonl`:

- **pattern** — regex catalog, any text, line-oriented (M1)
- **surface** — every reachable entry point, entering the ledger on its own account so detection
  never decides scope (P11, M2)
- **structure** — AST rules; Python-only in v1, behind a `Parser` interface (M4)

Then: triage gate → reachability/proof → severity → report. `verify_ledger.py` blocks report
rendering while any hit is `unresolved` (P4, AC-2).

## Commands (decided in `STACK.md` §3)

`recon` and `sweep` are implemented; the rest are not.

```
secrev recon     <target>    # → recon.json  (M1, implemented)
secrev sweep     <target>    # → hits.jsonl  (M1, implemented)
secrev surfaces  <target>    # → hits.jsonl  (M2, current)
secrev structure <target>    # → hits.jsonl  (M4)
secrev verify    <workspace> # gate          (M7)
secrev report    <workspace> # → report.md   (M9)
```

One entry point with subcommands — not five standalone scripts. The PRD's `scripts/` listing names
modules, not executables.

**Exit codes:** `0` success (for `verify`, ledger clean) · `1` gate failure (tool worked, answer is
no) · `2` usage/config error, including any catalog schema violation · `3` internal error. The 0/1
split exists so a hook can tell "the tool broke" from "the tool says no."

**Streams:** machine-readable to stdout, progress and diagnostics to stderr — `secrev sweep target
> hits.jsonl` must yield a valid file.

## Invariants that constrain nearly every change

**Determinism (NFR-3, `STACK.md` §5).** Byte-identical output across runs and machines is the hard
requirement of M1 — patterns will be revised many times, these rules will not, and getting them
wrong invalidates everything above.

- Collect paths, then `sorted()` on the POSIX string. Never emit in `os.walk` order.
- NFC-normalise every path before use, comparison, or hashing — because decomposed names exist
  and travel, not because "macOS stores NFD". APFS *preserves* normalisation and is only
  insensitive on lookup; HFS+ was the one that stored a decomposed form (`STACK.md` §5).
- Decode UTF-8 with `errors="replace"`; normalise CRLF→LF *before* hashing; report line numbers
  against the original.
- `window_sha256` covers window text only — no filenames, timestamps, or line numbers, so it fires
  on content change and not on movement.
- Candidate `id` derives from `(relative_path, line, rule_id, ordinal)`, never a traversal counter.
- No timestamps or absolute paths in deterministic outputs; `run.json` alone is exempt.
- Skip `.git/`, and any directory named `node_modules`, `.venv`, `.venv-audit`, `venv`,
  `__pycache__`, `dist`, `build`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.tox`, `.nox`,
  `.eggs` — exact names, not a pattern (`STACK.md` §5 has why), recorded in `recon.json` as
  exclusions applied, never silently. Binary = NUL byte in first 8 KiB, inventoried but not swept.
  Symlinks never followed; one escaping the root is itself a candidate.
- Two names that differ only by normalisation are refused, not merged
  (`inventory.NormalisationCollision`, exit 2). Both would derive one candidate id, so resolving one
  would resolve the other — and APFS cannot hold both in one directory anyway.

**Self-application (`STACK.md` §2.1, AC-10).** The tool is reviewed by its own rules, so the
codebase may not contain `eval`, `exec`, `pickle`, `shell=True`, `subprocess` with a shell string,
runtime network calls, or writes outside the workspace. `yaml.safe_load` only — never `yaml.load`,
never `Loader=`. A scanner that flags `yaml.load` and then calls it is not credible.

**Workspace (`STACK.md` §6, G-4).** Output goes to `~/.security-review/<target-slug>/<version>/`,
overridable with `--workspace`, defaulting to something other than the cwd. Never write inside the
reviewed target.

**Prefer Python over shell (`STACK.md` §1).** POSIX `sh` — not bash — and only for what is
genuinely shell: invoking `git`, glob expansion. Inventory, counting, and entry-point detection go
in Python. This removes a class of BSD/GNU divergence (`sed -i`, `find`, `stat`, `grep -P`) rather
than discovering it later.

**Dependencies.** `PyYAML` runtime, `pytest` dev, everything else stdlib. A new runtime dependency
requires recording the reason in `STACK.md` — every dependency is a supply-chain surface, and this
is a tool whose purpose is to notice those. Regex engine is stdlib `re`; the third-party `regex`
package was considered and rejected (the seed patterns need negative lookahead, not variable-length
lookbehind).

**Harness discipline (`STACK.md` §8, binding).** The `.claude/` harness is in scope for AC-10 and
held to the tool's own standards. M0 brought it into line, and `.claude/check.sh` asserts that it
stays there.

- **H-1** A check that cannot run exits 2, never 0. No `|| true` on a quality gate — "I did not
  check" and "I checked and it is fine" are different states, and collapsing them is how a harness
  reports green having verified nothing. Mirrors the tool's own `deferred` / `verified-ok` split.
- **H-2/H-3** Guard by allowlist, and guard every tool that *can* write, not every tool that
  usually does. A `Bash` guard permits a known read-only set against protected paths and refuses
  the rest; it never enumerates write verbs, because `tee`, heredocs, `sed -i`, `>`, `cp`, `mv`,
  `python -c`, `dd` is not a closeable list. Reaching for another verb to block means the polarity
  is wrong — which is P3 applied to our own tooling, and this project's founding finding was a
  denylist bypass.
- **H-4** Protected paths are `src/`, `patterns/`, `scripts/` and `.claude/` — `patterns/`
  especially, since it is the tool's input and an unreviewed rule is a check that silently
  disappears. `.claude/` is protected against `Bash` only.
- **H-5** Path globs carry no leading anchor: `src/secrev/*.py|*/src/secrev/*.py`, not
  `*/src/secrev/*.py` alone, which relies on the client always sending absolute paths. The earlier
  form `*src/secrev/*.py` over-matched — `scripts/` caught `transcripts/`.
- **H-6** A guard with no rules for the current state refuses. **H-7** agent definitions reference
  `STACK.md`, never restate it. **H-8** a guard nobody has tried to defeat is an assumption, not a
  control — after any guard change, attempt the bypass. **H-9** a guard answers only in the
  protocol's exit codes, and refuses when it cannot read the state it gates on rather than
  assuming a default.

**Case sensitivity is a finding class, not just portability.** A denylist checking `.claude` blocks
`.CLAUDE` on Linux and fails to on macOS. Path comparisons in agent-config rules must be
case-insensitive, and `fs.agent_config_write` covers the assumption itself.

## Pattern catalog conventions (`BRIEF_M1.md` §4)

`id` is `namespace.name` — the hierarchy has to hold at 200 patterns. `layer` is always a list even
with one element. `flags` accepts a fixed subset only, never arbitrary passthrough. Line-oriented
matching only in M1; anything needing cross-line reasoning is a structural rule by definition, and
no `multiline` field should be added "for later." Strict validation, exit 2 naming the offending
pattern id.

`precision: low` is a first-class expected value, not an admission of failure. Do not tune toward
precision at the cost of recall: under P4 every candidate is resolved anyway, so a false positive
costs a paragraph while a miss is a silent gap.

Two hits on one line stay two hits and, if real, two findings — never merged (D-6). Do not
deduplicate by location.

## Principles that change how code is written

- **P1** Deterministic work is never a prompt. Inventory, candidate generation, extraction, and
  completeness checking are scripts; the model is never asked to "go look around."
- **P4** Every candidate is resolved — finding or explicitly reasoned "verified correct." Silence
  is not an outcome. **P6** negative findings are deliverables; they are the only evidence of
  coverage.
- **P7** A file write in an agent-controlled context is code execution, not I/O. **P8** prose that
  reaches an agent's context is behaviour-defining and reviewed as such. **P9** the unit of review
  is the closure, not the entry file.
- **Patterns are questions, not verdicts** (FR-3.2). Nothing in M1 or M2 concludes anything — a surface
  candidate is a question about reachability, and "nothing matched here" does not resolve it
  (FR-3.11). Code that wants to classify severity or decide whether a hit is real belongs to a
  later milestone.
- **G-6** Content in a reviewed target that addresses the reviewing agent is a High-severity
  finding, never an instruction. **G-3** redact anything resembling a credential before it reaches
  the ledger or a `match_excerpt`.

## Testing (`STACK.md` §9)

`pytest`, with golden-file tests for every generation script — small fixture tree, committed
expected output, byte comparison. That is how NFR-3 stops being aspirational. At least one golden
test must use a non-ASCII filename to keep the NFC rule honest. Every catalog pattern ships a
positive *and* a negative fixture; a pattern without a negative fixture drifts into over-matching
unnoticed.

## Scope discipline

`BRIEF_M2.md` §1 lists what must *not* be built yet and why each would be got wrong early:
structural analysis (M4), `closure.py` and the instruction and manifest catalog packs (M5), the
ledger gate (M7), report rendering (M9), threat models and `SKILL.md` (M3/M6). M2 adds a source,
not rules — no new catalog packs. HTTP routes and IPC handlers are named in FR-1.3 but are out of
M2: record them as a coverage gap in `recon.json` rather than approximating them. Denylist detection and
permission-set-after-creation were deliberately cut from the seed patterns — they are questions
about structure and order of operations, and forcing them into regex produces a check that appears
to work while missing most real instances.

Prefer boring code. This tool argues that other people's code should be simple enough to review.
