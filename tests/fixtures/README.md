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

There is no symlink here on purpose: git stores one as a path, and a checkout
on a filesystem without symlink support silently materialises a regular file
containing the target path. The symlink rules are tested against trees built
at runtime in `tests/test_determinism.py`, where the shape is guaranteed.
