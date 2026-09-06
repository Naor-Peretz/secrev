# Fixture tree

A small target for the determinism check and, from M1, for the golden tests.
It is committed, and its content is the expected input — changing a file here
changes every hash derived from it, so treat an edit as a change to the
expected output rather than as tidying.

Deliberate shapes, each covering one rule in `STACK.md` §5:

| Path | Covers |
|---|---|
| `naïve-café.py` | Non-ASCII filename — NFC normalisation (§9 requires at least one) |
| `crlf_module.py` | CRLF line endings — normalised to LF before hashing |
| `pkg/deep/nested.py` | Nesting, so traversal order is not trivially sorted |
| `assets/blob.bin` | A NUL byte in the first 8 KiB — binary by content, not extension |
| `node_modules/` | An excluded directory that is present, so the exclusion is recorded |

`node_modules/` rather than `.venv/`: the root `.gitignore` ignores `.venv/` at
any depth, so a fixture there would be written, pass locally, and never survive
a clone — a fixture that exists only on the machine that made it.

## `rules/` — the per-pattern fixture pairs

One directory per catalog rule id, each holding `positive.*` and `negative.*`.
`tests/test_patterns.py` asserts the pairing in both directions: a pattern with
no fixture directory fails, and a fixture directory naming no pattern fails
too, because that is what an id rename leaves behind.

The negative half is the one that earns its place. §9's reason is that a
pattern without one "will drift into over-matching and nobody will notice", and
it happened immediately: `net.bind_all` was written as a bare `0\.0\.0\.0`,
which matches inside `10.0.0.0/8` — a private range, not a bind to every
interface. The negative fixture caught it before the rule had run against
anything real.

Named `rules/` rather than `patterns/` deliberately. The harness `Bash` guard
matches the protected catalog directory with an unanchored glob (`STACK.md` §8
H-5), so a fixture tree called `patterns` reads to it as the catalog. It fails
closed, which is the right direction, but a refusal naming the wrong directory
costs a reader time.

Fixture content is data, not code: `pyproject.toml` exempts `tests/fixtures/**`
from linting entirely, which is what lets a fixture contain the constructs the
catalog looks for. Without that exemption the seed patterns could not be tested
at all, because the linter would reject the only inputs that exercise them.

There is no symlink here on purpose: git stores one as a path, and a checkout
on a filesystem without symlink support silently materialises a regular file
containing the target path. The symlink rules are tested against trees built
at runtime in `tests/test_determinism.py`, where the shape is guaranteed.
