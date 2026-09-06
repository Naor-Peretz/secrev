# secrev

Security review of *agentic artifacts* — skills, MCP servers, subagents, hooks,
agent configs, plugins, and the CLI tools around them. A Python command-line
tool, backing a Claude Code skill.

> **Status: early, and not usable yet.** The walk and the candidate-identity
> scheme exist; the catalog, the sweep and the `secrev` command itself do not.
> The commands below are the decided interface, not a working one. Nothing here
> is published to PyPI.

## The thesis is method, not detection

Most scanners are a pattern list, and their honest failure mode is silence: a
rule did not match, nothing was said, and nobody can tell that apart from a
clean result. Three commitments push against that, and they shape the code more
than any individual rule does.

- **Every candidate is resolved.** A match becomes either a finding or an
  explicitly reasoned "verified correct". Silence is not an outcome, and a
  negative result is a deliverable — it is the only evidence that anything was
  covered.
- **Scope is set independently of what matched.** Every reachable entry point
  enters the ledger on its own account, so detection never decides what gets
  reviewed. A file nothing matched in is still a file that was looked at.
- **Patterns ask questions; they do not return verdicts.** A regex hit is a
  place to look. Whether it is real is a later stage's problem, and keeping
  those apart is why `precision: low` is an ordinary value in the catalog rather
  than an admission.

Three peer candidate sources feed one ledger: `pattern` (a regex catalog over
any text), `surface` (reachable entry points), and `structure` (AST rules,
Python-first behind a parser interface). Then a triage gate, reachability, a
severity pass, and a report that will not render while any candidate is still
unresolved.

## Interface

```
secrev recon     <target>    # → recon.json
secrev sweep     <target>    # → hits.jsonl
secrev surfaces  <target>    # → hits.jsonl
secrev structure <target>    # → hits.jsonl
secrev verify    <workspace> # gate
secrev report    <workspace> # → report.md
```

Machine-readable output goes to stdout and progress to stderr, so
`secrev sweep target > hits.jsonl` yields a valid file. Exit codes are `0`
success, `1` the tool worked and the answer is no, `2` usage or config error,
`3` internal error — the 0/1 split exists so a hook can tell a broken tool from
a refusal.

Output is written to `~/.security-review/<target-slug>/<version>/`, never inside
the target being reviewed.

## Two properties worth knowing before reading the code

**It is deterministic on purpose.** Byte-identical output across runs *and*
machines is a hard requirement, not a nicety: verifications are anchored to
content, and an anchor that moves when nothing changed expires every previous
verification for no reason. Paths are collected then sorted, never emitted in
traversal order; every path is NFC-normalised because APFS stores NFD; CRLF is
normalised before hashing and line numbers are reported against the original.
No timestamps and no absolute paths appear in deterministic output.

**It is reviewed by its own rules.** The codebase may not contain `eval`,
`exec`, `pickle`, `shell=True`, a subprocess shell string, a runtime network
call, or a write outside the workspace — `yaml.safe_load` only, never
`yaml.load`. A scanner that flags `yaml.load` and then calls it is not credible,
so a gate stage enforces this against the source with an AST walk rather than a
grep. `PyYAML` is the only runtime dependency.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
sh scripts/check.sh            # the gate — exactly what CI runs
```

`scripts/check.sh` runs format, lint, `mypy --strict`, tests, the
self-application check, a secrets scan, the licence allowlist, the determinism
check, and a dependency audit. It is the same list in the git hooks and in CI,
because a second list drifts from the first. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the setup that makes the hooks run, and for how the harness under
`.claude/` differs from the product gate.

## The documents

`REQUIREMENTS_security-review-skill.md` is the PRD and says *why*. `STACK.md`
is binding on *mechanism*. The `BRIEF_*.md` files scope one milestone each.
Precedence runs PRD → `STACK.md` → brief, and a conflict between them is raised
rather than quietly resolved, because a conflict usually means the PRD needs a
correction and resolving it loses that signal.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE) — **source-available, not open source.**
Any noncommercial purpose is permitted, and that expressly includes personal
projects, research, education, charities, and government and public-safety
bodies. Commercial use is not covered and needs a separate licence: open an
issue to start that conversation.

The distinction is deliberate rather than incidental, so it is worth stating
plainly: the noncommercial restriction fails the Open Source Definition's
field-of-use criterion. Calling this "open source" would be wrong, and GitHub
will show it as *Other* rather than a recognised licence.
