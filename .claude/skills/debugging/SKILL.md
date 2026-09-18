---
name: debugging
description: How to debug in secrev — read the failure before forming a theory, reproduce it at the smallest scope that still fails, and treat determinism and cross-platform failures as the specific classes they are. Use when something is broken, a test or gate is red, output differs between runs or machines, or a pattern matches the wrong thing.
---

# Debugging

The habit this replaces is guessing. A theory formed before reading the failure
costs more than the reading would have, because the fix that follows it changes
code that was not wrong.

## 1. Read the failure completely

The whole message, the whole traceback, the whole diff. In this project the
useful line is rarely the last one: pytest's assertion diff, ruff's rule code,
mypy's *first* error (the rest are usually its consequences).

State what failed before saying why. If you cannot say what failed in one
sentence, you have not read enough.

## 2. Reproduce at the smallest scope that still fails

```sh
sh scripts/check.sh                          # the whole gate
pytest tests/test_sweep.py::test_name        # one test
python3 scripts/self_check.py                # STACK.md §2.1 alone
python3 scripts/determinism_check.py         # NFR-3 alone
```

Narrow before changing anything. A fix validated only by the full gate has not
been validated — you cannot tell which of the five checks your change moved.

## 3. Change one thing

One hypothesis, one edit, re-run the narrow command. Two simultaneous changes
that turn a failure green leave you not knowing which was needed, and the
unnecessary one stays in the codebase forever.

Never comment out an assertion to see what happens next. The assertion is the
specification; what happens next is not interesting if the specification is off.

---

# The four failure classes here

## Determinism (NFR-3) — never fixed by regenerating the golden file

A determinism failure means a value that is not a property of the input reached
the output. Regenerating the golden file makes the symptom go away and leaves
the tool non-deterministic — worse than before, because the check now certifies
it. Find the value first. In order of likelihood:

- **Traversal order.** `os.walk`, `iterdir`, `rglob`, `glob`, `listdir`, or a
  `set`/`dict` built from one, whose order reaches the output. Collect, then
  `sorted()` on the POSIX string.
- **Unicode form.** A path used, compared, or hashed without
  `unicodedata.normalize("NFC", ...)`. It can fail on either platform, and
  which one is not obvious — do not assume "this is the macOS bug". APFS
  preserves the normalisation it was given and is only insensitive on *lookup*,
  so code that reopens a file by its NFC-normalised name works on APFS and
  raises on ext4 when the name was stored NFD. That defect shipped in this
  repository and failed on Linux. `STACK.md` §5 carries the correction.
- **Line endings.** CRLF must become LF *before* hashing, while line numbers are
  reported against the original.
- **Identity.** A candidate `id` from a traversal counter rather than
  `(relative_path, rule_id, window_sha256, ordinal)` renumbers everything when
  an unrelated file appears. **`line` is not in the derivation**, and `derive()`
  rejects it rather than ignoring it: FR-4.5 says a verification anchored to a
  line number is lost the moment the content moves, and one added import shifts
  every line below it. An id that changed while its content did not is this
  class, and it is the expensive one — every verification hanging on that id is
  thrown away.
- **Ambient values.** A timestamp, an absolute path, a PID, `hash()` on a str
  (PYTHONHASHSEED), or a locale-dependent sort key. `run.json` is the only
  output exempt from the first two.

Diff the two runs and look at *what* differs before looking at the code — the
shape of the difference names the class. A reordered block is traversal; a
changed digest with identical text is normalisation; one changed id with
everything else stable is derivation.

## Cross-platform (Linux vs macOS)

If it passes locally and fails in CI's digest-comparison job, suspect, in order:
NFC/NFD, case-insensitive filesystem (`.claude` vs `.CLAUDE` — a finding class
here, not just portability), and BSD-vs-GNU tool divergence in shell. STACK.md §1
exists to keep the third out: if the answer involves `sed -i`, `find`, `stat` or
`grep -P`, the code belongs in Python.

## Self-application (STACK.md §2.1)

There is one fix: remove the construct. `eval`, `exec`, `pickle`, `marshal`,
`shell=True`, `yaml.load`, `Loader=`, a network client. A `# noqa` on a bandit
rule is not a fix — it converts a public claim about this codebase into a lie
that the gate now certifies. If the construct seems genuinely necessary, that is
a design problem to raise, not a suppression to add.

## A pattern matching the wrong thing

Decide which failure it is before touching the regex:

- **False positive** — costs one paragraph. Under P4 every candidate is resolved
  anyway. Do not tighten the regex to remove it; `precision: low` is a
  first-class value.
- **False negative** — a silent gap, and much worse. This is the one to chase.

Both start the same way: add the fixture that fails, then change the pattern.
Every pattern ships a positive *and* a negative fixture, so a fix without a new
fixture has not been demonstrated.

If the pattern needs to reason across lines to be right, it is not a pattern —
it is a structural rule, and it is M4. Do not reach for `re.MULTILINE`.

---

## When stuck

Say so, and say precisely what you have ruled out. Three failed hypotheses
narrated honestly are more useful than a fourth guess presented as a finding —
and in this repo, a confident wrong answer about determinism is the expensive
kind.
