# closure entry

The entry file of the closure fixture. Every member kind FR-1.2 names appears
below exactly once, so a test can assert on each by name instead of on a count
— a count is the assertion that keeps passing while the thing it counted
changed.

Nothing in this tree cites a document by filename, deliberately. A citation is
a reference, and a fixture whose unresolved members include the briefs it
quotes would be asserting its own prose rather than its own design. The
whole-tree golden is where incidental references get demonstrated.

Read [the direct helper](helpers/direct.md) first. A plain reference: this file
names it, so it is in the closure because of this line.

When a request needs more than the summary, read helpers/progressive.md as
well. That is the progressively loaded case — the file is a closure member
whether or not the condition ever holds, and "we could not tell whether this
loads" is a finding candidate rather than a shrug (P9).

The bundled script is helpers/run.sh, and the bundled binary it unpacks is
helpers/payload.bin.

The rule set this fixture was written against lives at
https://example.invalid/closure/rules.json and is not shipped here. Nothing
fetches it, because the stack document forbids runtime network calls — so
FR-1.2's answer stands: an unresolvable member is itself a finding candidate.

Older revisions kept their notes in ../../../outside/notes.md, which is above
this tree and is never read.

helpers/absent.md is named here and is not in the tree at all.

The cycle is helpers/cyclé.md, which names this file back.

Three shapes the extractor must *not* read as references, each with its own file
so the negative case is demonstrated rather than described. helpers/calls.py
holds attributes spelled like extensions; helpers/imports.ts holds package
specifiers beside one relative specifier that must still resolve; and uv.lock is
a member of this closure whose dependency table is not read for references at
all.

