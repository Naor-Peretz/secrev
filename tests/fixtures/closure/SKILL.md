---
name: closure-fixture
description: Demonstrates every member kind FR-1.2 names, from a declared entry point
---

# closure-fixture

The declared entry point of the closure fixture. It exists so the whole-tree
golden reaches this subtree the way a client would — by loading a skill —
rather than only through an explicit `--entry`.

Everything it demonstrates is in entry.md, which this file names so that the
traversal has somewhere to go. The two files together are also the shape the
closure is actually for: a skill whose behaviour lives in prose, pointing at
more prose, pointing at a script and a binary.
