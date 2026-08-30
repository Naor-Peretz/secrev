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
| NFC-normalise every path before use, comparison, or hashing | APFS stores NFD, Linux stores NFC. Without this the same target hashes differently on macOS and Linux and invalidates verifications for no reason (D-4) |
| Decode UTF-8 with `errors="replace"`; record the mode | A locale must never decide how a target is read |
| CRLF→LF **before** hashing; line numbers against the original | Otherwise a checkout setting changes every hash |
| `window_sha256` covers window text only | No filename, no line number, no timestamp. The hash answers "did this content change", and must not fire when content merely moved |
| `id` from `(relative_path, line, rule_id, ordinal)` | Never a traversal counter. Adding an unrelated file must renumber nothing |
| No timestamps, no absolute paths in deterministic output | `run.json` is the single exemption |

Exclusions are `.git/`, `node_modules`, `.venv`, `venv`, `__pycache__`, `dist`,
`build` — and they are **recorded in `recon.json`, never applied silently**. A
binary file is one with a NUL byte in the first 8 KiB: inventoried, not swept,
never judged by extension. Symlinks are never followed; one that escapes the
root is itself a candidate (P9).

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
