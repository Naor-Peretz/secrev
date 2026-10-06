# Brief — M1: Recon & Pattern Source

**Milestone:** M1 of 12
**Prerequisites:** `STACK.md` (binding), `REQUIREMENTS_security-review-skill.md` (context —
read §2 on prior art before writing patterns; published rule taxonomies are legitimate seed
material, third-party engines are not)
**Goal:** a working pattern source. Point it at a repository, get a structured list of questions.

---

## 1. Scope

**Build:** `secrev recon` and `secrev sweep`, the catalog format, and eight seed patterns.

**Do not build.** Each of these is a later milestone and building it early will get it wrong:

| Not now | Why | When |
|---|---|---|
| Structural / AST analysis | Needs the ledger format settled first | M4 |
| Surface candidates | Separate source with separate semantics | M2 |
| Ledger gate (`verify`) | Nothing to gate until three sources exist | M7 |
| Report rendering | Output shape follows from findings, which don't exist yet | M9 |
| Threat models, `SKILL.md` | Procedure written before first output is a guess | M3 / M6 |
| Instruction & manifest patterns | Same engine, later catalog packs | M5 |

At the end of M1 the tool is driven by hand and produces a ledger file. That is the whole target.

**Two patterns deliberately excluded.** Early drafts listed ten seed patterns. Two of them —
denylist detection and permission-set-after-creation — are questions about *structure* and *order
of operations*, not about the presence of a token. Forcing them into regex would produce a check
that appears to work and quietly misses most real instances. They move to `_structure.yaml` in M4.
This is D-11 in practice: do not smuggle structural rules into the pattern catalog.

---

## 2. Deliverables

```
pyproject.toml
src/secrev/
├── __init__.py
├── cli.py               # argparse; subcommands recon, sweep
├── inventory.py         # deterministic file walk (STACK.md §5)
├── recon.py             # → recon.json
├── catalog.py           # YAML load + validation
├── sweep.py             # → hits.jsonl
└── ids.py               # stable candidate id derivation
patterns/
├── _base.yaml
└── python.yaml
tests/
├── fixtures/            # incl. one non-ASCII filename
└── test_*.py
```

---

## 3. `recon.json`

Deterministic; no timestamps, no absolute paths.

```jsonc
{
  "target": {"root": "<slug>", "version": "v0.9.14", "source": "git", "sha": "f26bf51…"},
  "inventory": {
    "files_total": 412,
    "by_language": {"python": 207, "yaml": 31, "markdown": 24},
    "loc_total": 58231,
    "binary": ["assets/icon.png"],
    "symlinks": [{"path": "docs/link", "target": "../README.md", "escapes_root": false}],
    "excluded": [".git/", "node_modules/", ".venv/"]
  },
  "entrypoints": {
    "declared": ["notebooklm-mcp-cli = app.cli:main"],
    "workflows": [".github/workflows/ci.yml"]
  },
  "security_process": {
    "security_md": false, "dependabot": true, "sast_config": false, "test_files": 94
  },
  "coverage_gaps": ["structural analysis unavailable for: yaml, markdown"]
}
```

`entrypoints` is populated from declared metadata only in M1 — `pyproject.toml` scripts,
`package.json` bin. Deeper enumeration is M2's job; do not attempt it here.

---

## 4. Catalog format

The schema below is derived from the seed patterns rather than designed ahead of them. Validate it
strictly and fail with exit code 2 on any violation — a silently ignored typo in a pattern file is
a missing check that nobody sees.

```yaml
version: "2026.08.1"          # catalog_version; bump on any add or semantic change
patterns:
  - id: exec.shell_true       # namespace.name — hierarchy must hold at 200 patterns
    layer: [code]             # ALWAYS a list: code | instruction | manifest
    languages: [python]       # omit or [] = applies to all text
    paths_exclude: ["tests/**", "**/test_*.py"]
    regex: 'subprocess\.[a-zA-Z_]+\([^)]*shell\s*=\s*True'
    owasp: ASI-02              # OWASP Agentic Top 10 (2026) category, where one applies
    flags: [i]                # i = ignorecase; subset only, no arbitrary flags
    precision: high           # high | medium | low — how the report presents it
    question: >
      Where does the command string originate, and is any part of it interpolated
      from input the caller does not control?
    default_severity_hint: high  # PRD FR-3.3's spelling; this brief said `severity_hint`
                                 # and lost on precedence. A *default* the severity phase may
                                 # override — the shorter name reads like a verdict, which
                                 # under FR-3.2 is exactly what a pattern must not carry.
    references: ["CWE-78"]
```

Binding constraints:

- **Line-oriented matching only.** No multi-line patterns in M1. Anything needing cross-line
  reasoning is a structural rule (M4), by definition. Do not add a `multiline` field "for later" —
  an unused field invites misuse.
- **`layer` is always a list**, even with one element. Some rules legitimately belong to two.

  **In M1 the validator accepts a list and exits 2 if it holds more than one element.** §5's hit
  record and PRD §7 both carry `"layer": "code"` as a scalar, so a two-layer pattern has no
  defined ledger representation — one record with which value, or two records? All eight seed
  patterns are single-layer, so M1 does not have to answer that, and answering it here with
  nothing to test against would be a guess frozen into the data contract. What M1 must not do is
  accept a catalog it cannot emit: the refusal names the pattern id and says the representation is
  undecided rather than silently dropping a layer.
- **`precision: low` is a first-class, expected value**, not an admission of failure. A low-precision
  pattern that surfaces the right region for a human to read is doing its job. Do not tune patterns
  toward high precision at the cost of recall — under P4 every candidate gets resolved anyway, so
  the cost of a false positive is one paragraph, while the cost of a miss is a silent gap.
- **`flags`** accepts only a fixed subset. Never pass arbitrary flags through to the engine.
- **`owasp`** maps the pattern to an OWASP Agentic Top 10 (2026) category where one applies.
  Optional — omit rather than force a bad fit. It exists so findings speak a vocabulary
  maintainers already recognise (PRD §2.4).

---

## 5. `hits.jsonl` — M1 subset

One JSON object per line. Emit only these fields in M1; the rest of the PRD schema is added by
later milestones and must not be stubbed with placeholders.

```jsonc
{
  "id": "H-a3f21c04",
  "file": "src/app/paths.py",
  "line": 137,
  "layer": "code",
  "source": "pattern",
  "rule_id": "exec.shell_true",
  "precision": "high",
  "question": "Where does the command string originate…",
  "match_excerpt": "subprocess.run(cmd, shell=True)",
  "status": "unresolved",
  "catalog_version": "2026.08.1",
  "window_spec": "lines-20"
}
```

- `id` — stable, derived per `STACK.md` §5 from
  `(relative_path, rule_id, window_sha256, ordinal)`, where `ordinal` ranges over byte-identical
  windows only. Adding an unrelated file must not renumber anything, and neither must an edit
  above the match, nor another match of the same rule being added or deleted elsewhere in the
  file. `line` is a field on the record for locating the hit; it takes no part in the identity —
  see §5 there for why, because the reasoning is what stops this being reverted.
- `window_spec` — `lines-20` in M1, meaning ±20 lines with no tightening. It is on the record for
  the same reason `catalog_version` is: the id depends on `window_sha256`, `window_sha256` depends
  on what the window covered, and that changes once a parser lets it tighten to the enclosing block
  (`STACK.md` §5). Recording it makes that transition an invalidation the tool detects (FR-4.6)
  rather than one that relies on someone remembering. **This said "M4" until M4 was scoped.** M4
  builds the parser and gives `block-20` to the structural source, which is new and re-identifies
  nothing; re-windowing *this* source moves every id already recorded and is a milestone of its
  own. This is an addition to the M1 field
  set rather than a stub for a later milestone — nothing here is a placeholder, the value is real
  and is load-bearing today.
- `match_excerpt` — the matched span with a small margin, truncated to 200 chars. Redact anything
  resembling a credential before writing it (G-3). The redaction applies to the excerpt only: the
  window that feeds `window_sha256` is hashed unredacted, because a digest is not a reproduction
  and redacting first would make every candidate id depend on the redaction rules, so tuning them
  would re-identify candidates that had not changed.
- One line may produce several records if several patterns match it. This is correct and
  intentional — see D-6. Do not deduplicate by location.

---

## 6. Seed patterns

Nine. Ship each with a positive and a negative fixture (`STACK.md` §9). Treat the regexes as
starting points to be refined against real output, not as specifications.

**Eight, until `path.traversal` was added.** §7's last item requires the sweep to flag the region
of a known *path-validation* issue, and none of the original eight targeted path handling at all —
the rule that would have, denylist detection, is one of the two §1 removed to M4. PRD FR-3.4 also
names "path handling and traversal" as minimum code-layer coverage, and no milestone owned it.
A DoD item that no shipped pattern can satisfy is a check that fails for a reason nobody can act
on, so the pattern was added rather than the item renegotiated.

**This does not reverse §1's exclusion**, and the difference is the whole point of that exclusion.
The rule cut to M4 asks *"is this validation a denylist"* — a question about the shape of control
flow, which regex cannot answer. `path.traversal` asks *"is a path being built here at all"* — a
question about the presence of a token, which is exactly what regex answers. The first would have
been a check that appeared to work; the second surfaces a region for a human to read, which under
P4 is all a pattern is for.

### `_base.yaml` — language-agnostic

| id | Targets | Question | Precision |
|---|---|---|---|
| `net.bind_all` | `0\.0\.0\.0`, `--remote-debugging-port`, `--inspect` | Who can connect, and is there authentication? A debug port is an unauthenticated grant of everything the process can reach. | medium |
| `net.fetch_exec` | `curl` or `wget` piped to `sh`/`bash`; `urlretrieve` followed by execution | What is the source, is it pinned, and is integrity verified? | high |
| `log.sensitive` | logging or printing near `token`, `password`, `secret`, `cookie`, `api_key` | Is the value being written or only the name? | low |
| `fs.agent_config_write` | writes to `.claude`, `.cursor`, `.gemini`, `.codex`, `.agents`, `.git/hooks`, `.zshrc`, `.bashrc`, `.profile`, `LaunchAgents`, `autostart` | Is this path reachable from caller-controlled input? Under P7 a write here is code execution, not I/O. Also check whether the comparison is case-sensitive — on macOS `.CLAUDE` and `.claude` are the same directory and on Linux they are not (`STACK.md` §4). | high |

`fs.agent_config_write` is the single most important pattern in the catalog for this domain, and
the simplest to write — it is a path list. Give it the most fixture coverage.

### `python.yaml`

| id | Targets | Question | Precision |
|---|---|---|---|
| `exec.shell_true` | `subprocess.*shell=True` | Where does the string come from; is any part interpolated? | high |
| `exec.dynamic` | `eval(`, `exec(`, `compile(` | Is any part of the argument externally influenced? | medium |
| `deser.unsafe` | `pickle.loads?`, `marshal.loads`, `yaml.load(` without a safe loader | Is the serialised data from a trusted origin? Deserialisation of untrusted data is execution. | high |
| `tls.verify_off` | `verify=False`, `_create_unverified_context`, `CERT_NONE` | Deliberate, or a debugging leftover that shipped? | high |
| `path.traversal` | `os.path.join`, `Path(…) /`, `open(`, `shutil` and `os` file calls whose argument is a name rather than a literal; `..` in a path literal | Where does the component come from, and is the joined result confined to a base directory *after* normalisation — or only checked before it? | low |

`path.traversal` is `precision: low` by design and will match a great deal of ordinary path
handling. That is the correct trade here: it is the only rule standing between the catalog and a
whole FR-3.4 class, a false positive costs one paragraph under P4, and a miss in this class is the
defect the DoD's real-target check exists to catch.

For `deser.unsafe`, the `yaml.load` case needs a negative lookahead to avoid matching
`yaml.load(f, Loader=yaml.SafeLoader)`. Stdlib `re` handles this; no third-party engine needed.

---

## 7. Definition of done

- [x] `secrev recon <path>` emits `recon.json` matching §3 against a real repository.
- [x] `secrev sweep <path>` emits `hits.jsonl` matching §5.
- [x] Both write to the workspace layout in `STACK.md` §6, never into the target.
- [x] Two consecutive runs produce byte-identical `recon.json` and `hits.jsonl`.
- [x] Golden tests pass, including the non-ASCII filename fixture.
- [x] Every seed pattern has a passing positive and negative fixture.
- [x] A malformed catalog file exits 2 with a message naming the offending pattern id.
- [x] Adding an unrelated file to the fixture tree changes no existing candidate `id`.
- [x] The codebase passes the self-application rules in `STACK.md` §2.1 — verified by running
      `secrev sweep` against `src/secrev/` and confirming no unexplained high-precision hits.
- [x] `secrev sweep` run against `gemini-notebook-mcp-cli` produces a plausible candidate set and
      flags the region of the known path-validation issue.

The last item is a sanity check against a target whose contents are already known, not a
regression test. The corpus (Q-1) is M10 and is deliberately not started here.

**The last item was run against the target the DoD names**, identified from §3's own entry-point
example rather than guessed. Cloned read-only; nothing in it was executed. It produced a plausible
candidate set — 164 candidates over 30 files — and reached the region the item requires.

**Where that region is, and what is in it, are deliberately not recorded here.** The owner has an
unfixed finding in this target. Naming the file, the construct, or the shape of the weakness in a
repository heading for public is disclosure — it reaches the maintainer, and everyone else, minus
the part where the maintainer was told first. G-1 and FR-8.4 both land on this: FR-8.4 requires
explicit human action before anything reaches a maintainer, and a commit is not that action.

Earlier drafts of this paragraph did name it, and did pronounce on its soundness. That was a Phase
4 verdict written by a milestone that owns no triage — M1 runs Phase 3, FR-3.2 says patterns are
questions, and §1 puts every stage that turns a candidate into a finding in a later milestone. Both
the location and the characterisation have been removed from this file and from the history behind
it.

This costs the brief nothing that matters. The DoD asks whether the *tool* surfaced the region, and
that is answerable — and answered — without republishing the region. Details live with the owner
until disclosure (Phase 8) says otherwise.

The candidates are unresolved, which is their correct and only M1 status. Whether any describes a
real weakness is not this milestone's to say, and not this repository's to publish.
If that assessment is ever made it goes through disclosure (Phase 8), not through a brief.

**How it got there is the part worth keeping, and that part is about this tool.** The rule that
matched was looking for agent-configuration path strings, and the region happens to contain such
strings for reasons of its own. Nothing in the catalog asked the question that would have aimed at
that region deliberately — that rule is one of the two §1 removed to M4, because it is a question
about the shape of control flow rather than the presence of a token.

So the run is both the DoD item passing and a demonstration of why D-11 promotes structural
analysis to v1: the catalog arrived at the right place through a coincidence of vocabulary.
Coincidence is not coverage, and a DoD item a coincidence can satisfy is weaker evidence than it
looks. That is a finding about `secrev`, which this brief is entitled to record.

The first item's "against a real repository" half is discharged against this repository, which
resolves a git SHA, a declared entry point, three workflows and all three `security_process`
flags. That run also found what a fixture tree structurally cannot — see TASK-M1-012 in
`.claude/TASKS_M1.md`: `STACK.md` §5's exclusion list omits `.venv-audit/` and the tool caches, so
recon of this repository reports 1952 files and 703,763 lines, the great majority of them vendored.
Raised rather than resolved, because §5 enumerates that list verbatim.

---

## 8. Notes for the implementer

- **Patterns are questions, not verdicts** (FR-3.2). Nothing in M1 concludes anything. If a
  function looks like it wants to classify severity or decide whether a hit is real, it belongs to
  a later milestone.
- **Determinism is the hard requirement**, not pattern quality. Patterns will be revised many
  times; the traversal, normalisation, and ID rules will not, and getting them wrong invalidates
  everything built on top (D-4).
- **Prefer boring code.** This tool argues that other people's code should be simple enough to
  review. It should be reviewable itself.
- Where this brief and the PRD conflict, raise it rather than choosing — a conflict usually means
  the PRD needs a correction, and silently resolving it loses that signal.
