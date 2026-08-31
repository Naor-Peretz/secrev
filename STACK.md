# Stack & Environment Decisions — `security-review`

**Status:** v1.0 — binding
**Applies to:** every milestone. Read this before writing code for any brief.
**Companion documents:** `REQUIREMENTS_security-review-skill.md` (the PRD — *why*),
`BRIEF_M1.md` and successors (per-milestone scope — *what now*).

This file exists so implementation does not re-decide these per milestone. Where a brief and this
file disagree, this file wins. Where the PRD and this file disagree, the PRD wins on intent and
this file wins on mechanism.

---

## 1. Language and runtime

- **Python 3.11+** for all analysis logic. No 3.12-only syntax.
- **POSIX `sh`** — not `bash` — for the thin shell layer only.
- **Rule: prefer Python over shell.** Shell is used only for what is genuinely shell: invoking
  `git`, and glob expansion. File inventory, counting, and entry-point detection go in Python.
  This is not style preference — it removes an entire class of BSD/GNU divergence (§4).

## 2. Dependencies

| Package | Use | Status |
|---|---|---|
| `PyYAML` | catalog loading | required |
| `pytest` | tests | dev only |
| `ruff` | lint | dev only |
| `mypy` | types (`--strict`) | dev only |
| `pip-audit` | known-vulnerability audit (§2.2) | gate only, separate env |
| `pip-licenses` | licence allowlist (§2.2) | gate only, separate env |
| `gitleaks` | secret scanning (§2.2) | gate only, external binary |

`mypy` was configured in `pyproject.toml` and run as a gate stage while appearing nowhere in this
table, and `CLAUDE.md` asserted it was "recorded in `STACK.md` §2 with reasons". It was not. Recorded
now, with the reason: `--strict` on a tool whose output feeds a ledger other checks gate on, where a
silently-`Any` field is a wrong answer rather than a crash.

**No `jq`.** The harness originally shelled out to `jq` in six hooks. It is removed rather than
documented: it is a non-Python external dependency, which is exactly what §1's prefer-Python rule
exists to avoid, and an undeclared one in a repository that requires a written reason for every
dependency. Hooks parse JSON with `python3 -c` instead.

**Everything else is stdlib.** `re`, `ast`, `hashlib`, `pathlib`, `json`, `unicodedata`.

- **Regex engine: stdlib `re`.** An earlier draft called for the third-party `regex` package on
  the grounds that a seed pattern needed variable-length lookbehind. On re-inspection it needs
  only negative *lookahead*, which `re` supports. `regex` is therefore not adopted. If a future
  pattern genuinely requires variable-length lookbehind, adopting it is a one-line change and a
  note in this file — do not pre-empt it.
- **No new runtime dependency may be added without recording the reason here.** Every dependency
  is a supply-chain surface, and this is a tool whose entire purpose is to notice those.

### 2.1 Self-application (binding)

Per AC-10 the tool is reviewed by its own rules. Non-negotiable consequences:

- **`yaml.safe_load` only.** Never `yaml.load`, never `Loader=`. A scanner that flags `yaml.load`
  and then calls it is not credible.
- No `eval`, `exec`, `pickle`, or `shell=True` anywhere in the codebase.
- No `subprocess` with a shell string; argument lists only.
- No network calls at runtime (NFR-4). Tests included.
- No writes outside the workspace directory (§6).

### 2.2 Supply-chain gates (binding)

The gate checked whether the code was correct and said nothing about what it
depended on. Three questions were missing, and each is one this tool asks of the
targets it reviews — which under AC-10 is reason enough on its own:

| Question | Stage | Where it runs |
|---|---|---|
| Is a credential in the repository? | `gitleaks dir` | every commit, push, and CI run |
| Are the licences ones we accept? | `scripts/license_check.py` | every commit, push, and CI run |
| Do the declared dependencies carry advisories? | `scripts/deps_audit.py` | push and CI |
| Does untrusted input reach a dangerous sink? | `scripts/codeql_check.py` | CI; locally with `--sast` |

Binding consequences:

- **The audit tooling installs into `.venv-audit`, never `.venv`.** `pip-audit`
  and `pip-licenses` bring 29 transitive packages, among them `requests`,
  `urllib3` and `certifi` — a network client stack, in a project whose NFR-4
  keeps one out of the runtime and whose §2 requires a written reason per
  dependency. Both tools inspect another environment from outside it
  (`pip-licenses --python`, `pip-audit --path` / `-r`), so the environment that
  type-checks and tests the code stays the ten packages someone chose. Pinned in
  `.github/requirements/audit.txt`.
- **`gitleaks` is installed from a pinned, hash-verified release tarball.** Not
  `curl … | sh`, and not `gitleaks/gitleaks-action`: the first is
  `net.fetch_exec`, one of the eight seed patterns this project ships, and the
  second is a third-party action with access to the checkout when a checksum
  achieves the same thing. It is an external binary rather than a Python
  dependency, so it is not in `pyproject.toml` and absent it the gate exits 2.
- **Allowlist, not denylist, for licences (P3).** A licence nobody has
  considered fails and names itself. `scripts/license_check.py` holds the set,
  with the reason beside each entry that is not plainly permissive.
- **A blocking "are the pins current" check is deliberately absent.** The
  project this gate was compared against has one and it blocks CI. Here it would
  contradict `.github/requirements/dev.txt`'s own reason for existing: a build
  that turns red because someone else published a release, with no diff in this
  repository to explain it. Dependabot answers the same question as a pull
  request a person reads (`.github/dependabot.yml`).
- **CodeQL is unconditional in CI and opt-in locally**, and carries no
  `continue-on-error`. A SAST job that stays green when it analysed nothing
  reports exactly like one that analysed everything and found nothing — H-1, in
  the stage most likely to be trusted without being read.
- **Each stage distinguishes "found nothing" from "could not check" (H-1).** A
  scanner that produced no report, an OSV query that could not reach the
  network, a missing binary: all exit 2. `scripts/deps_audit.py` reads the
  report file rather than the exit code for exactly this reason — `pip-audit`
  exits non-zero both when it finds a vulnerability and when the network is
  gone, and only the first writes a report.

## 3. Packaging and interface

- **Stdlib `venv` + `pip`**, with a `pyproject.toml`. `python3 -m venv .venv`, then
  `.venv/bin/pip install -e .`. `uv` is permitted but is not the default and nothing may depend on
  `uv`-specific features.

  This reverses an earlier decision in this file, and the reason is the tool's own subject matter.
  `uv`'s advertised install is `curl … | sh` — a fetched script piped straight into a shell, which
  is `net.fetch_exec`, one of the eight seed patterns this project ships. A scanner that flags that
  construct and then installs itself with it cannot defend the finding. The objection is to the
  *method*, not the tool: `pipx install uv` or a distribution package carry none of it. But with
  four dev dependencies `uv` buys nothing over stdlib `venv`, so the tie goes to the option with no
  supply-chain surface at all.
- **One CLI entry point, `secrev`, with subcommands.** Not five standalone scripts. The PRD's
  `scripts/` listing describes modules, not executables.

  ```
  secrev recon    <target>            → recon.json
  secrev sweep    <target>            → hits.jsonl   (M1)
  secrev surfaces <target>            → hits.jsonl   (M2)
  secrev structure <target>           → hits.jsonl   (M4)
  secrev verify   <workspace>         → gate         (M7)
  secrev report   <workspace>         → report.md    (M9)
  ```

- **Exit codes** — fixed now so the gate is scriptable and hooks can rely on it:

  | Code | Meaning |
  |---|---|
  | 0 | Success; for `verify`, ledger is clean |
  | 1 | Gate failure — the run worked, the result is not acceptable (unresolved candidates remain) |
  | 2 | Usage or configuration error (bad arguments, malformed catalog, missing target) |
  | 3 | Internal error |

  The 0/1 split matters: a hook must distinguish "the tool broke" from "the tool worked and the
  answer is no."

- **Streams:** machine-readable output to **stdout**, human progress and diagnostics to
  **stderr**. `secrev sweep target > hits.jsonl` must produce a valid file.

## 4. Platforms

**Supported:** Linux and macOS. **Out of scope for v1:** Windows; the answer is WSL. Revisit only
if a real target demands it — Windows path and permission semantics would cost more than they
return at this stage.

Known divergences to design around rather than discover:

- `sed -i`, `find`, `stat`, and `grep -P` differ or are absent between BSD (macOS) and GNU
  (Linux). Mitigated by §1's prefer-Python rule.
- **Filesystem case sensitivity.** macOS defaults to case-insensitive; Linux is case-sensitive.
  This is not only a portability concern — it is a *finding class* in this domain. A denylist
  checking `.claude` blocks `.CLAUDE` on Linux and fails to block it on macOS. Path comparisons
  in agent-config rules must be case-insensitive, and a seed pattern covers the case-sensitivity
  assumption itself (see `BRIEF_M1.md`, `fs.agent_config_write`).

## 5. Determinism (implements NFR-3)

NFR-3 requires byte-identical output from generation scripts across runs and machines. That is
unachievable without fixing the following explicitly:

- **Traversal order** — collect paths, then `sorted()` on the POSIX path string. Never emit in
  `os.walk` order.
- **Filename Unicode** — normalise every path to **NFC** before use, comparison, or hashing.
  APFS/HFS+ store NFD, Linux stores NFC; without this the same target hashes differently on the
  two platforms and invalidates verifications for no reason (D-4).
- **Content decoding** — UTF-8 with `errors="replace"`. Record the decoding mode; never let a
  locale decide it.
- **Line endings** — normalise CRLF → LF *before hashing*. Report line numbers against the
  original file.
- **Hashing** — `window_sha256` is SHA-256 over the NFC-normalised, LF-normalised window text.
  No filenames, timestamps, or line numbers in the hash input: the hash answers "did this content
  change," and must not fire when the content merely moved.
- **Exclusions** — skip `.git/`, and any directory named `node_modules`, `.venv`, `venv`,
  `__pycache__`, `dist`, `build`. Recorded in `recon.json` as exclusions applied, not silently.
- **Binary files** — detected by NUL byte in the first 8 KiB; recorded in the inventory, not
  swept. Never guessed at by extension alone.
- **Symlinks** — never followed. Recorded as symlinks with their target. A symlink pointing
  outside the target tree is itself a candidate (a closure question, per P9).
- **No timestamps or absolute paths in deterministic outputs.** Paths are relative to the target
  root. Run metadata with timestamps belongs in a separate `run.json`, which is explicitly exempt
  from NFR-3.
- **The window** — ±20 lines around the matched line, tightened to the enclosing function or
  block boundary where the language allows it. Fixed here rather than left to `window.sh`, because
  since the correction below `window_sha256` is *inside* the candidate id: the window definition
  now decides identity. Changing it later re-identifies every candidate in every ledger and
  invalidates every verification recorded against them (FR-4.6), so it is a versioned decision and
  a change to it is a migration, not a tuning knob.

- **Stable IDs** — candidate `id` is derived from
  **`(relative_path, rule_id, window_sha256, ordinal)`**, not from a counter over traversal, and
  the `ordinal` ranges over *byte-identical windows only* — never over every match of the rule in
  the file. IDs must survive an unrelated file being added.

  This corrects an earlier version of this rule, which derived the id from
  `(relative_path, line, rule_id, ordinal)`. The reasoning is recorded because the correction is
  the kind someone reverts in six months while tidying:

  - **`line` had to go.** PRD FR-4.5 says a verification "anchored only to a line number is lost
    the moment the content moves". An id containing `line` anchors it to exactly that, so the
    mechanism defeated the requirement it existed to serve — one added import shifts every line
    below it and re-identifies every candidate in the file. Precedence gives the PRD intent; this
    file was wrong.
  - **A rule-wide `ordinal` had to go.** Two matches of one rule at lines 40 and 90: delete the
    first and the second moves from ordinal 1 to 0. Nothing about the surviving match changed.
  - **What each surviving component is for.** `window_sha256` answers "did this content change",
    which is the question FR-4.6 invalidates on, so putting it in the id makes that structural
    rather than a separate check that can be forgotten. The `ordinal` exists only because D-6
    requires two byte-identical matches in one file to stay two candidates, and nothing in their
    content can tell them apart.

  **The residue, stated rather than discovered.** Two byte-identical windows in one file are the
  one case where an id can still move: delete the first and the second's ordinal shifts. That is
  irreducible — the two are indistinguishable by content, so any identity separating them is
  positional, and positional identity shifts. It is bounded (identical windows only, same file)
  where the old scheme's instability was not, and it is the price of D-6.

  `line` remains a field on the candidate record, for a reader locating the hit. It simply takes
  no part in the identity.

## 6. Workspace layout

Never inside the reviewed target (G-4).

```
~/.security-review/
└── <target-slug>/
    └── <version>/
        ├── run.json          # timestamps, tool version, catalog_version (NFR-3 exempt)
        ├── recon.json
        ├── closure.json
        ├── hits.jsonl        # the ledger — all three sources
        ├── findings.json
        ├── poc/
        └── report.md
```

- `<target-slug>` — normalised from the source identity; `<version>` — the resolved tag or SHA.
- The per-version directory is what makes re-review (D-4) and lifecycle tracking (D-8) possible
  later. Build the layout now even though nothing reads across versions until M7.
- Overridable with `--workspace`; the default is never the current directory.

## 7. Analysis coverage by source

The three candidate sources (D-11) have different language reach. State this honestly in the
report rather than implying uniform coverage.

| Source | Reach | v1 |
|---|---|---|
| Pattern | Any text; language packs reduce false positives, they are not a prerequisite | All languages |
| Structural | Requires a parser | **Python only** |
| Surface | Requires entry-point conventions per ecosystem | Python, plus manifest-declared surfaces (MCP tools, skill activation, hook bindings) |

- **`structure.py` must sit behind a `Parser` interface**, with `ast` as the first implementation.
  Adding tree-sitter later must not require touching rule logic. Do not adopt tree-sitter in v1 —
  Python-only is an acceptable v1 position; a half-built multi-language layer is not.
- Where a closure member is in a language with no structural coverage, `recon.json` records it and
  the report states it as a coverage gap (FR-3.8). Silence here would be exactly the false
  assurance this project exists to prevent.

## 8. Harness discipline

The `.claude/` harness — hooks, agents, settings — is subject to the same standards as the tool.
It is in scope for AC-10, and the rules below are binding on it.

- **H-1 — A check that cannot run exits 2, never 0.** No `|| true` on a quality gate. "I did not
  check" and "I checked and it is fine" are different states, and collapsing them produces a green
  report from a harness that verified nothing. This mirrors the `deferred` / `verified-ok`
  distinction the tool itself enforces (FR-4.4).
- **H-2 — Guard by allowlist, not by denylist (P3).** A `PreToolUse` guard on `Bash` must permit a
  known-safe set of read-only commands against protected paths and refuse everything else. Do not
  enumerate write verbs: `tee`, heredocs, `sed -i`, `>`, `>>`, `cp`, `mv`, `install`, `python -c`,
  and `dd` are not a closeable list. Adding another verb to a block list is the signal that the
  polarity is wrong.
- **H-3 — Guards cover every tool that can write, not every tool that usually writes.**
  `Write|Edit|MultiEdit` alone leaves `Bash` as an open path. Under P7 a write is an execution
  primitive regardless of which tool performed it.
- **H-4 — Protected paths are `src/`, `patterns/`, `scripts/`, and `.claude/`.** `patterns/`
  especially: it is the tool's input, and a rule added without review is a check that silently
  disappears. `.claude/` is protected against **`Bash` only** — writes through `Write`/`Edit` stay
  permitted there, so repairing the harness remains possible and remains visible, while the path
  that disables a guard without anything objecting closes. Nothing guarded the harness itself: a
  `sed -i` on `bash-guard.sh` removed the control, and no component was defective on its own. That
  is composition risk in the sense of FR-0.8, found in the reviewer rather than the reviewed.
- **H-5 — Path globs carry no leading anchor.** Use `src/secrev/*.py|*/src/secrev/*.py`, not
  `*/src/secrev/*.py` alone. The latter depends on the client always sending absolute paths — true
  today, undocumented, and not something to rely on.

  This rule previously said `*src/secrev/*.py`. That form does drop the dependency on absolute
  paths and also matches `foosrc/secrev/x.py`; the `scripts/` equivalent matched `transcripts/` and
  `descripts/`. The two-alternative form meets the stated rationale without the over-match. The
  failure was closed rather than open — it refused writes to paths this repository does not contain
  — but a control that fires on the wrong file teaches people to work around it.
- **H-6 — A guard with no rules for the current state refuses.** When `MILESTONE` advances past
  what a scope guard knows, it exits 2 with a message. It does not exit 0.
- **H-7 — Single source of truth.** Agent definitions reference this file; they never restate its
  content. A copied stack section goes stale silently, which is the failure mode this file exists
  to prevent.
- **H-8 — Guards are verified by attempting the bypass.** After any guard change, deliberately try
  the thing it should block. A guard nobody has tried to defeat is an assumption, not a control.
- **H-9 — A guard answers in the protocol's vocabulary, and reads the state it gates on rather
  than assuming it.** Two shapes of the same error, both found in M0.

  A hook that exits with a value the event gives no meaning to has not answered. `jq`'s
  parse-error code reaching the caller through `set -eu` produced `exit 5` from three `PreToolUse`
  guards, where only 0 and 2 carry meaning. It looked like neither a refusal nor a pass.

  A hook that cannot read the state it gates on refuses; it does not substitute a default.
  `MILESTONE=$(cat … || echo M1)` assumed the one milestone the guard had rules for — the most
  permissive reading available of a total failure to read anything.

  H-1 covers a check that cannot run. This covers the two ways a check can appear to have run
  without having done so, which is harder to see and worth naming separately.

  And a guard that runs someone else's check does not report in its own name. Its message must
  separate "I failed" from "what I ran failed", because a reader who cannot tell them apart looks
  at the wrong file. `determinism-guard.sh` invokes `determinism_check.py`; when that fails, the
  assertion said "PostToolUse guard must not block", which named the guard for a defect in the
  thing under it. Attribution is part of the answer, not decoration on it.

## 9. Testing

- **`pytest`**, with golden-file tests for every generation script: a small fixture tree, a
  committed expected output, byte-comparison. This is how NFR-3 stops being aspirational.
- At least one golden test must include a filename with non-ASCII characters, to keep the NFC
  rule honest.
- Every pattern in the catalog ships with a positive and a negative fixture. A pattern with no
  negative fixture will drift into over-matching and nobody will notice.
