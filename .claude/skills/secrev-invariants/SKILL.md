---
name: secrev-invariants
description: The rules that constrain every change to secrev — determinism (NFR-3), self-application (STACK.md §2.1), workspace containment (G-4), and dependency discipline. Read before writing or editing anything under src/secrev/, and whenever a change touches file traversal, hashing, path handling, subprocess use, or dependencies.
---

# secrev invariants

Four rules. Everything else in the codebase is revisable; these are not, because
code written on top of a broken one has to be thrown away rather than fixed.

## 1. Determinism (NFR-3, STACK.md §5)

Byte-identical output across runs **and machines**. Not "stable in practice".

| Rule | Why it is not optional |
|---|---|
| Collect paths, then `sorted()` on the POSIX string | `os.walk` order is filesystem order; it differs between two copies of the same tree |
| NFC-normalise every path before use, comparison, or hashing | Decomposed names exist and travel — authored on HFS+, or by a tool that emits NFD — and survive onto any filesystem. Without this the same content is two candidates and verifications expire for no reason (D-4). Not "APFS stores NFD": APFS preserves normalisation and is only insensitive on lookup (`STACK.md` §5) |
| Decode UTF-8 with `errors="replace"`; record the mode | A locale must never decide how a target is read |
| CRLF→LF **before** hashing; line numbers against the original | Otherwise a checkout setting changes every hash |
| `window_sha256` covers window text only | No filename, no line number, no timestamp. The hash answers "did this content change", and must not fire when content merely moved |
| `id` from `(relative_path, rule_id, window_sha256, ordinal)` | Never a traversal counter, and **never `line`** — `derive()` rejects a `line` argument rather than ignoring it, because FR-4.5 says a verification anchored to a line number is lost the moment content moves, and one added import shifts every line below it |
| No timestamps, no absolute paths in deterministic output | `run.json` is the single exemption |

Exclusions are exact directory names — `.git/`, `node_modules`, `.venv`,
`.venv-audit`, `venv`, `__pycache__`, `dist`, `build`, and the tool caches
(`.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.tox`, `.nox`, `.eggs`).
`--exclude NAMES` **replaces** that set; `--exclude ""` skips nothing. They are
**recorded in `recon.json` as what was actually applied, never silently**, and
the applied set is also stated in `coverage_gaps`.

A binary file is one with **more than 5% non-text bytes in the first 8 KiB**
(`STACK.md` §5) — inventoried, not swept, and named in `coverage_gaps`. It was
"a NUL byte in the first 8 KiB" until M3.5, where one byte in a comment was
shown to remove a whole file from review.

**Extension decides the exemption, not the classification.** A file that went
unread for any reason counts as `unread_code`, and the run exits 2, *unless* its
extension is a known binary asset. That polarity is the fourth review's
correction. "Does this look like code" was asked three ways — a code extension,
then a shebang, then a set of known artifact names — and each was defeated by a
file that looked like something else; the last round was walked past by
`AGENT.md`, `prompt.txt` and `setup` with no extension at all
(`.claude/TASKS_M3.5.md`). Naming what may be **skipped** puts the burden of
enumeration on us, which is P3 applied to our own tooling.

Symlinks are never followed; one that escapes the root is itself a candidate
(P9).

Verify, don't assume: `python3 scripts/determinism_check.py`.

## 2. Self-application (STACK.md §2.1, AC-10)

The codebase may not contain what the catalog flags:

`eval` · `exec` · `compile` · `pickle` · `marshal` · `shell=True` · `subprocess`
with a shell string · `yaml.load` or any `Loader=` · runtime network calls ·
writes outside the workspace.

`yaml.safe_load` only. A scanner that flags `yaml.load` and then calls it is not
credible, and that is the whole argument. Enforced three ways — ruff's bandit
rules, `scripts/self_check.py`, and the `self-application-guard` hook — because
this one is a claim the project makes publicly.

**"Writes outside the workspace" is in the list above as a rule, not as an
enforced one.** M3.5's E2 removed exactly that claim from the README: `cli.py`
writes by design, so a name-based AST test would flag it, and deciding whether a
write lands *inside* the workspace is a dataflow question a name test cannot
answer. The structural property is what holds it — `cli.py` is the only module
that writes — and a check nobody looks for because the documentation says it
exists is the expensive kind of wrong.

## 3. Workspace containment (STACK.md §6, G-4)

Output goes to `~/.security-review/<target-slug>/<version>/`, overridable with
`--workspace`, defaulting to **something other than the cwd**. Never write inside
the reviewed target. The target is third-party code that, per G-6, may be trying
to influence the review — a successful injection must have nowhere to land
(NFR-7).

## 4. Dependencies and shell (STACK.md §1, §2)

`PyYAML` at runtime, `pytest`/`ruff`/`mypy` for development, everything else
stdlib. A new runtime dependency requires a recorded reason in STACK.md — every
dependency is a supply-chain surface, and this is the tool whose purpose is to
notice those.

Shell is POSIX `sh`, never `bash`, and only for what is genuinely shell:
invoking `git`, glob expansion. Inventory, counting, and entry-point detection
go in Python. This is not style: it removes the BSD/GNU divergence class
(`sed -i`, `find`, `stat`, `grep -P`) rather than discovering it on a user's mac.

## Interface contract

Exit codes: `0` success · `1` gate failure (the tool worked, the answer is no) ·
`2` usage or config error, including any catalog schema violation · `3` internal
error. The 0/1 split is what lets a hook tell "broke" from "said no".

Machine output to **stdout**, progress and diagnostics to **stderr**.
`secrev sweep target > hits.jsonl` must produce a valid file.

## Related

`pattern-author` · `testing-contract` · `spec-precedence`
