---
name: testing-contract
description: How secrev is tested — golden-file byte comparison, the mandatory positive/negative fixture pair per pattern, the non-ASCII filename requirement, and why coverage percentage is the wrong metric here. Use when writing tests, adding fixtures, or changing anything under tests/.
---

# The testing contract

This project's test standard differs **in kind** from a coverage target, not in
degree. Do not import an "80% coverage, unit + integration + E2E" habit here; it
would pass while the thing that actually matters goes unchecked.

## 1. Golden-file tests, byte-compared

Every generation script gets one: a small fixture tree, a committed expected
output, a byte comparison. That is how NFR-3 stops being aspirational
(STACK.md §8).

```python
def test_sweep_golden(tmp_path):
    run_sweep(FIXTURES, workspace=tmp_path)
    assert (tmp_path / "hits.jsonl").read_bytes() == GOLDEN.read_bytes()
```

`read_bytes`, not `read_text`, and not a parsed comparison. The requirement is
byte-identity; a test that parses both sides and compares objects passes while
key order, trailing newlines, and separator choices drift.

## 2. At least one non-ASCII filename

Mandatory, and it is not decoration. Without it the NFC rule is untested, and
the failure it guards against appears in front of a user, on a target that then
hashes differently for no reason (D-4).

Two things this fixture must actually do, both learned the hard way. It has to
*match something*, or it never reaches a golden file and the requirement is
satisfied on paper by a file the generator emits no record for. And the two
normalisation forms have to be built with `unicodedata`, never typed as
literals — a source file holds one normalisation, so a literal-versus-literal
comparison compares a string to itself and passes regardless.

Do not describe this as "the macOS bug". APFS preserves the normalisation it
was given and is only insensitive on lookup; it was HFS+ that stored a
decomposed form (`STACK.md` §5). The NFC defect this repository actually
shipped failed on **Linux** and would have worked on APFS.

## 3. Two fixtures per pattern

Positive and negative, for every entry in the catalog. A pattern without a
negative fixture over-matches silently. See `pattern-author` for what makes a
negative fixture worth writing.

## 4. Stability tests, not just correctness tests

Two properties from BRIEF_M1.md §7 that no ordinary test suite checks:

- Two consecutive runs produce byte-identical `recon.json` and `hits.jsonl`.
- Adding an unrelated file to the tree changes **no existing candidate id**.

Both are automated in `scripts/determinism_check.py`, which the gate runs. Keep
them there rather than reimplementing them per test module.

## 5. Negative results are deliverables

P6: what was checked and found sound is part of the output, because it is the
only evidence of coverage. That applies to the test suite too — a test asserting
that a pattern does *not* fire is as much a deliverable as one asserting it does.

## Running

```sh
sh scripts/check.sh                        # the whole gate, same as CI
pytest                                     # tests only
pytest tests/test_sweep.py::test_name      # one test
python3 scripts/determinism_check.py       # NFR-3 only
python3 scripts/self_check.py              # STACK.md §2.1 only
```

## Related

`secrev-invariants` · `pattern-author`
