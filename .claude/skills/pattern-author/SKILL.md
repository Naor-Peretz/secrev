---
name: pattern-author
description: How to add or change a pattern in the secrev catalog — schema rules, the questions-not-verdicts principle, precision as a first-class low value, and the mandatory positive/negative fixture pair. Use when editing anything under patterns/, adding a rule id, or changing catalog.py validation.
---

# Authoring a catalog pattern

## A pattern is a question, not a verdict

FR-3.2. The `question` field is the deliverable; the regex is only how the
question finds its subject. A pattern that reads like a conclusion ("unsafe
deserialisation") is wrong even when it matches correctly — write "Is the
serialised data from a trusted origin? Deserialisation of untrusted data is
execution."

Nothing in the pattern layer concludes anything. If a change wants to decide
whether a hit is real, or how severe it is, it belongs to a later milestone.

## Schema (BRIEF_M1.md §4)

```yaml
version: "2026.08.1"          # bump on any add or semantic change
patterns:
  - id: exec.shell_true       # namespace.name — the hierarchy must hold at 200
    layer: [code]             # ALWAYS a list: code | instruction | manifest
    languages: [python]       # omit or [] = all text
    paths_exclude: ["tests/**", "**/test_*.py"]
    regex: 'subprocess\.[a-zA-Z_]+\([^)]*shell\s*=\s*True'
    owasp: ASI-02             # OWASP Agentic Top 10 (2026), where one fits
    flags: [i]                # fixed subset only — never arbitrary passthrough
    precision: high           # high | medium | low
    question: >
      Where does the command string originate, and is any part of it
      interpolated from input the caller does not control?
    default_severity_hint: high   # REQUIRED, and this is the spelling
    references: ["CWE-78"]
```

Hard constraints:

- **Line-oriented only.** No `multiline`, no `re.MULTILINE`, no `re.DOTALL`.
  Anything needing cross-line reasoning is a structural rule (M4) *by
  definition*. Do not add the field "for later" — an unused field invites misuse.
- **`layer` is always a list**, even with one element. Some rules belong to two.
- **`flags` is a closed set.** Arbitrary flags reaching the engine is a bug.
- **`owasp` is optional.** Omit rather than force a bad fit.
- Validation is strict and fails with **exit code 2 naming the offending id**. A
  silently ignored typo in a pattern file is a missing check nobody sees.

## Do not tune for precision

`precision: low` is an expected value, not an admission. Under P4 every candidate
gets resolved anyway, so a false positive costs one paragraph and a miss is a
silent gap. A low-precision pattern that puts a human in front of the right
region is doing its job.

For the same reason: two patterns matching one line stay two hits, and if both
are real, two findings (D-6). Never deduplicate by location. Where two patterns
repeatedly collide, the defect is in the **catalog** — fix it in YAML at
maintenance time, not by run-time judgment.

## Every pattern ships two fixtures

Positive and negative, both, always (STACK.md §9 — §8 is the harness). A pattern with no negative
fixture drifts into over-matching and nobody notices. The negative fixture is
where the interesting design lives:

- `deser.unsafe` must match `yaml.load(f)` and **not** `yaml.load(f, Loader=yaml.SafeLoader)`
  — negative lookahead, which stdlib `re` handles.
- `fs.agent_config_write` is a path list and the single most important pattern in
  this domain. Give it the most coverage, including the case-sensitivity
  assumption itself: `.CLAUDE` and `.claude` are one directory on macOS and two
  on Linux (STACK.md §4).

Fixtures live under `tests/fixtures/` and are excluded from linting — they
deliberately contain the constructs the catalog looks for, so linting them would
mean the seed patterns cannot be tested.

## Before you add a structural-looking rule

Denylist detection and permission-set-after-creation were **deliberately cut**
from the seed patterns. They are questions about structure and order of
operations; forcing them into regex produces a check that appears to work and
quietly misses most real instances. They belong in `_structure.yaml` at M4.
Do not smuggle structural rules into the pattern catalog (D-11).

## Related

`secrev-invariants` · `testing-contract`
