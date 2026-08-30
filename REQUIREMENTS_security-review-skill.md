# Requirements — `security-review` Skill

**Status:** Draft v0.4
**Owner:** Naor
**Domain:** Security review of AI-agentic artifacts — skills, MCP servers, subagents, hooks,
agent configuration, CLI tooling, and the assembled environment they run in.
**Target runtime:** Claude Code (skill + dedicated subagent + local scripts)
**Document purpose:** Define what gets built, why it is built this way, and what "done" means.

> **Changes from v0.1:** the domain is generalised from "a repository" to "an agentic artifact
> or environment." Archetype-specific threat models become *overlays* on a shared agentic core
> (§7). Adds environment-review mode (§5, Phase 0), instruction-layer analysis (§5, Phase 3),
> and closure mapping (§5, Phase 1).
>
> **Changes from v0.2:** Phase 3 is no longer a pattern sweep. It generates candidates from three
> peer sources — patterns, structural AST rules, and triggerable surfaces (D-11, P11). Structural
> analysis is promoted from a deferred v2 gap to a v1 requirement. All earlier decisions
> D-2…D-10 carry forward unchanged.
>
> **Changes from v0.3:** adds §2, a prior-art review and an explicit statement of differentiation
> (D-12). Sections renumbered accordingly. Pattern schema gains an `owasp` field.

---

## 1. Problem statement

An LLM asked to "review this for security issues" reliably produces a *plausible* review rather
than a *complete* one. The dominant failure mode is not hallucinated findings — it is silent
under-reporting: the model runs a handful of greps, sees no `eval()`, and concludes the code is
fine. The review is unfalsifiable, unrepeatable, and its coverage is unknown to both the reviewer
and the reader.

The problem is sharper in the agentic ecosystem than in ordinary software, for three reasons:

1. **The artifacts are mostly not code.** A skill is markdown. A subagent is a prompt plus a tool
   grant. A hook is three lines of shell attached to a lifecycle event. Conventional code review
   instincts and conventional tooling both aim at the wrong layer.
2. **Installation is casual and privilege is broad.** People add a skill or an MCP server with a
   single command, and it inherits the agent's filesystem access, network access, and tool grants.
   The gap between "trying something out" and "granting execution on my machine" is close to zero.
3. **The security literature has not caught up.** There is no mature scanner for "does this skill
   instruct the agent to skip confirmations," and there will not be one soon.

This skill exists to make review of these artifacts **repeatable, bounded, and auditable**: every
decision leaves a trace, every unexamined element is visible as unexamined, and every severity
rating is backed by evidence rather than vibes.

### 1.1 Scope

**In scope — agentic artifacts:**

| Artifact | What it is | Primary risk shape |
|---|---|---|
| Skill | Markdown procedure + bundled scripts/references | Instructions become agent behaviour; deferred loading hides payload |
| MCP server | Tool provider over a protocol boundary | Tool returns enter agent context; tools are execution primitives |
| Subagent | Prompt + tool grant + context isolation | Over-broad grants; instruction-layer manipulation |
| Hook | Shell attached to a lifecycle event | Automatic execution with no user action; can rewrite tool calls |
| Agent config / rules | `CLAUDE.md`, rules files, settings, permission lists | Silent behaviour change; permission widening |
| Plugin / bundle | Several of the above shipped together | Composite surface; risk lives in the seams |
| CLI tool | Conventional command-line program in the agent's reach | Classic sinks, but reachable by an agent rather than a human |
| Supporting code | Libraries, services and scripts these depend on | Conventional appsec |

**In scope — environments:** an assembled installation (installed skills, registered MCP servers,
active hooks, agent configs, permission settings) reviewed as a whole rather than one artifact at
a time. Composition risk is real and belongs here (§5, Phase 0.5).

### 1.2 Non-goals

- Not a wrapper around third-party scanners. Per **D-2** (§13), the analysis engine is entirely
  self-contained: no CodeQL, Semgrep, or bandit in the pipeline. The consequence is owned
  explicitly in FR-3.7.
- Not a penetration test. No live exploitation against running services or third-party
  infrastructure.
- Not a dependency CVE scanner. That is a solved problem (Dependabot, `pip-audit`, `osv-scanner`)
  and should be delegated, not reimplemented.
- Not an offensive tooling generator. See §9.
- Not a prompt-injection *robustness benchmark*. The skill assesses whether an artifact
  establishes trust boundaries; it does not attempt to break a model's resistance to injection.

---

## 2. Prior art and differentiation

Reviewed 2026-08-30. This section exists because the domain became crowded during drafting, and a
requirements document that ignores that is dishonest about its own justification.

### 2.1 The field

- **`agent-audit`** (HeadyZhang, MIT, PyPI 0.19.2, beta) — the closest comparable. A static
  analyzer for AI agent code: Python AST taint tracking from tool parameters to dangerous sinks,
  MCP configuration auditing, secret detection, with rules mapped to the OWASP Agentic Top 10
  (2026). Ships SARIF output, a GitHub Action, baseline scanning, and a DeFi profile.
- **`inkog`**, **SkillAudit**, **SkillRisk** — hosted or MCP-delivered scanners for `SKILL.md`
  packages and tool definitions, covering tool poisoning, exfiltration, and excessive permissions.
- Naming consequence: `agentaudit` and `agent-audit` are both taken on PyPI, as are several
  variants. The working name is `secrev` (security review).

### 2.2 What is genuinely shared

State this plainly rather than minimising it. Several of these tools converged independently on
the same threat classes — tool-boundary taint, MCP configuration, capability breadth, secret
exposure — which is evidence the threat model in §8 is broadly right, not evidence it is
unnecessary. `agent-audit` additionally performs intra-procedural taint tracking, which this
project defers to FR-3.7. On raw detection of code-layer issues in Python, the overlap is real
and should not be argued away.

### 2.3 Where this project differs

The difference is not that the others scan and this one does not. This project scans too, from
three sources (D-11). The difference is what the scan is *for*.

**In a scanner, detection is the product.** What it found is what exists; what it missed does not
appear. **Here, detection is one mechanism inside a review method**, and the method constrains it
in ways a standalone scanner cannot constrain itself:

| Dimension | Scanners | This project |
|---|---|---|
| **Direction** | Code you wrote, before you deploy it | An artifact someone else wrote, before you install it. Looking for intent, not only for mistakes |
| **Coverage claim** | "Here is what matched" | "Here is what was examined, and here is what was found sound" (P4, P6, FR-4.3) |
| **Who sets scope** | The rule set — unmatched logic is never read | Every reachable entry point enters the ledger regardless of any match (P11, FR-3.9) |
| **Instruction layer** | Prompt injection assessed as a *code* pattern (interpolation into a system prompt) | Prose in the closure assessed as behaviour-defining in its own right (P8, FR-3.13) |
| **Closure** | Files present are scanned | What the artifact can *pull in later* is mapped first (P9, FR-1.2) |
| **Across versions** | Baseline diffing — report only what is new | Scoped verifications that expire on content, catalog, or manifest change (D-4) |
| **Severity discipline** | Confidence scores and risk totals | Mechanical caps tied to evidence and reachability (FR-6.2) |
| **Composition** | Per-artifact | Environment mode: risks that exist only between components (FR-0.8) |

The baseline contrast is worth stating precisely, because it looks like the same feature as D-4
and is close to its opposite. "Report only what is new" assumes that what is not new is still
fine. It carries a stale judgment forward silently, with no record of what the judgment was made
against — no content hash, no rule version. FR-4.6 exists specifically to prevent that.

### 2.4 Consequences for this document

- **D-2 stands** — no third-party scanner in the pipeline. Their rule sets target agent
  *application* code rather than installable artifacts; the completeness gate (FR-4.3) cannot
  survive a dependency on an external engine's output volume; and taking a 0.x beta as a
  foundation is precisely the supply-chain decision this tool is built to flag.
- **Reading is not depending.** Published rule taxonomies — the OWASP Agentic Top 10, and the rule
  lists of the tools above — are legitimate catalog sources under D-2, exactly as CWE is. Seeding
  from them is expected.
- **Pattern schema gains an `owasp` field** alongside `references`, so findings speak the
  vocabulary maintainers already use.
- **Honest positioning in the report.** Where a code-layer finding would also have been caught by
  a general scanner, that is not a weakness to hide. The claim this project makes is about
  completeness and method, not about detecting things nobody else can.

---

## 3. Design decision: why a Skill

The capability could be packaged five ways. The decision and its rationale:

| Option | Verdict | Rationale |
|---|---|---|
| **Skill** (+ scripts + references) | **Chosen** | The work is a *procedure with judgment steps*. Progressive disclosure keeps archetype overlays out of context until the archetype is known. Versionable in git, portable across projects, testable with an eval loop. |
| Dedicated subagent | **Chosen as companion** | Required for context isolation — reviewing an artifact whose content is adversarial instructions must not happen in a window shared with unrelated work. The subagent is the *executor*; the skill is the *procedure*. |
| Hook | **Rejected as primary** | Hooks fire on lifecycle events. A security review is an intentional, long-running task. *Narrow exception:* a hook may later gate installation of a new artifact on a completed review (§10.3). |
| MCP server | **Rejected** | No external state, no remote API, no cross-session persistence needed. Everything is local filesystem + git. A process boundary for zero capability gain. |
| Ad-hoc prompt / slash command | **Rejected** | Exactly the status quo that produces the failure mode in §1. No enforcement surface, no reusable threat models, no eval loop. |

**Architectural principle behind the split:** the skill encodes *what must happen and in what
order*; the scripts encode *everything that does not require judgment*; the subagent provides
*a clean, isolated context to do the judging in*.

**Note on self-application.** This skill is itself an agentic artifact within its own scope. It
must pass its own review, and doing so is an acceptance criterion (AC-10). This is not cuteness —
it is the cheapest available test of whether the archetype overlays are actually usable.

---

## 4. Core design principles

Non-negotiable. If a requirement below ever conflicts with one of these, the principle wins and
the requirement is wrong.

- **P1 — Deterministic work is never a prompt.** Inventory, candidate generation (all three
  sources), extraction, and completeness checking are scripts. The model is never asked to "go look around."
- **P2 — Threat model before artifact.** The archetype is classified and its threat model surfaced
  *before* any content is read. This prevents grep-driven review, where the reviewer finds only
  the classes of issue they happened to search for.
- **P3 — Denylists are findings until proven otherwise.** Any allow/deny decision implemented as a
  list of forbidden values is treated as a suspected bypass and must be actively falsified.
- **P4 — Every candidate is resolved, never dropped.** A sweep hit exits the pipeline as either a
  finding or an explicitly reasoned "verified correct." Silence is not an outcome.
- **P5 — Severity requires reachability.** Impact alone does not set severity. Who — or what —
  triggers the path is a first-class, recorded property.
- **P6 — Negative findings are deliverables.** What was checked and found sound is part of the
  report. It is the only evidence of coverage.
- **P7 — In an agentic system, a file write is code execution.** Any primitive that writes to disk
  in a context an agent controls is evaluated as an execution primitive, not as I/O.
- **P8 — Text in an agentic artifact is instruction, not data.** Prose that reaches an agent's
  context is reviewed as behaviour-defining, on the same footing as source code. A review that
  only examines the `scripts/` directory of a skill has reviewed the wrong thing.
- **P9 — The unit of review is the closure, not the entry file.** Everything the artifact can pull
  in — referenced files, deferred loads, fetched resources, bundled binaries — is in scope.
  Progressive disclosure is a legitimate design pattern and an obvious evasion surface, and it
  cannot be told which it is from the entry file alone.
- **P11 — Detection must not decide scope.** What gets read cannot be determined solely by what
  the automation matched, or logic with no syntactic signature is never examined and the catalog
  silently sets the boundary of the review. Every reachable entry point enters the ledger on its
  own account (FR-3.9), independent of any match.
- **P10 — Capability grants are the privilege boundary.** What an artifact *may* do is reviewed as
  seriously as what its code *does*. An unbounded tool grant is a finding on its own terms, before
  any line of implementation is read.

---

## 5. Architecture

```
skills/security-review/
├── SKILL.md                        # procedure, gates, output contract (<500 lines)
├── scripts/
│   ├── recon.sh                    # target inventory          → recon.json
│   ├── closure.py                  # reachable artifact set    → closure.json
│   ├── sweep.py                    # pattern catalog runner    → hits.jsonl
│   ├── structure.py                # AST structural rules      → hits.jsonl
│   ├── surfaces.py                 # entry-point candidates    → hits.jsonl
│   ├── window.sh                   # extract N lines around a hit
│   ├── verify_ledger.py            # GATE: unresolved == 0
│   └── render_report.py            # findings.json + template  → report.md
├── patterns/
│   ├── _base.yaml                  # language-agnostic code patterns
│   ├── _structure.yaml             # AST rule declarations
│   ├── _instruction.yaml           # prose/instruction-layer patterns (P8)
│   ├── _manifest.yaml              # capability-grant & config patterns (P10)
│   ├── python.yaml
│   ├── node.yaml
│   └── shell.yaml
├── threat-models/
│   ├── _classifier.md              # how to pick archetypes
│   ├── _agentic-core.md            # ALWAYS loaded for any agentic target
│   ├── skill.md                    # ─┐
│   ├── mcp-server.md               #  │
│   ├── subagent.md                 #  ├─ overlays on the core
│   ├── hook.md                     #  │
│   ├── agent-config.md             # ─┘
│   ├── cli-tool.md                 # ─┐ conventional archetypes,
│   ├── web-api.md                  #  ├─ core not loaded
│   └── library.md                  # ─┘
├── references/
│   ├── severity-matrix.md
│   ├── poc-guidelines.md
│   ├── instruction-review.md       # how to review prose as behaviour
│   └── disclosure-playbook.md
└── templates/
    ├── finding.md
    └── report.md

agents/security-reviewer.md         # subagent: clean context, restricted tools
evals/                              # regression corpus + eval set (§11)
```

---

## 6. Functional requirements

### Phase 0 — Intake & scope lock

- **FR-0.1** Record target identity: source (repo URL, registry entry, local path), resolved
  commit SHA where applicable, version/tag, acquisition date. A review that names a branch instead
  of a SHA is not reproducible and must be rejected.
- **FR-0.2** Select a **review mode**, which determines the pipeline shape:
  - `artifact` — a single skill, MCP server, subagent, hook, plugin, or repository.
  - `environment` — an assembled installation reviewed as a whole (Phase 0.5 applies).
- **FR-0.3** Emit an explicit in-scope / out-of-scope statement before work begins. Default
  out-of-scope: live exploitation, dependency CVEs, third-party service behavior.
- **FR-0.4** Refuse to proceed on a dirty working tree or a shallow clone missing the target ref.
- **FR-0.5** The reviewed artifact is **never installed, registered, or executed** to inspect it.
  Review is static plus controlled PoC execution in an isolated workspace (§9).

### Phase 0.5 — Environment enumeration (`environment` mode only)

- **FR-0.6** Enumerate the installed surface: skills, registered MCP servers, subagent definitions,
  active hooks, agent config and rules files, and effective permission/allowlist settings.
- **FR-0.7** Produce a **capability map**: for each component, what it may read, write, execute, and
  reach over the network — plus how it is triggered.
- **FR-0.8** Assess **composition risk** explicitly: combinations that are individually acceptable
  and jointly dangerous. Canonical shape: component A can write to a location that component B
  loads automatically. Neither is a finding alone; together they are an execution chain. This is
  the class of issue a per-artifact review structurally cannot see, and is the main reason this
  mode exists.
- **FR-0.9** Each component then enters the normal `artifact` pipeline, with findings tagged by
  originating component and, for composition findings, by the participating set.

### Phase 1 — Recon & closure

- **FR-1.1** `recon.sh` produces `recon.json`: artifact type signals, file inventory, language
  breakdown, LOC, declared entry points, CI workflow paths, test count, presence of `SECURITY.md`
  / Dependabot / SAST config.
- **FR-1.2** `closure.py` computes the **reachable artifact set** (P9): the entry file plus every
  file it references, every conditionally or progressively loaded resource, bundled scripts and
  binaries, and any resource fetched at load or run time. Remote fetches are recorded as closure
  members that could not be resolved statically — an unresolvable closure member is itself a
  finding candidate, not an omission.
- **FR-1.3** Enumerate **triggerable surfaces**: MCP tool definitions, skill activation conditions
  and description breadth, hook event bindings, CLI commands, HTTP routes, exported functions,
  IPC handlers. This list drives reachability scoring in Phase 5.
- **FR-1.4** Extract the **capability manifest** (P10): declared tool grants, permission entries,
  allow/deny lists, filesystem scopes, network scopes, and any request for elevated access.
- **FR-1.5** Classify into one or more archetypes using `threat-models/_classifier.md`. Multiple
  archetypes are the norm, not the exception — a plugin bundle may be skill + hook + MCP server
  at once, and the review must compose overlays rather than choose among them.

### Phase 2 — Threat model (GATE)

- **FR-2.1** For any agentic archetype, load `_agentic-core.md` **plus** each matching overlay.
  For conventional archetypes, load the overlay alone.
- **FR-2.2** Present the composed threat model to the user *before* reading artifact content.
  A hard ordering gate — enforced by SKILL.md structure and validated in evals (§11).
- **FR-2.3** Each overlay declares: applicability signals, archetype-specific trust boundaries and
  sinks, mandatory questions, pattern packs to enable, and known-good implementations.

### Phase 3 — Candidate generation

Three independent sources feed one ledger. They are peers, not a primary and its fallbacks:
**patterns** answer *"is a dangerous API present here?"*, **structure** answers *"is the shape of
this logic wrong?"*, and **surfaces** answer *"input enters here — follow it."* Each covers what
the others structurally cannot.

#### 3a. Pattern source

- **FR-3.1** `sweep.py` runs the enabled catalog packs and writes pattern hits to `hits.jsonl`,
  one record per match, each with a stable `id` and `source: pattern`.
#### 3b. Structural source

- **FR-3.5** `structure.py` performs first-party AST analysis and emits candidates with
  `source: structure` into the same ledger. This is a **core capability of v1, not a deferred
  gap.** The three highest-value questions identified in the founding review — is this validation
  a denylist, is permission set after creation rather than atomically, does this write reach a
  location an agent auto-loads — are all questions about *shape*, not about the presence of a
  token. A regex catalog cannot answer any of them; treating structural analysis as a later
  enhancement would leave the system's most important checks permanently unowned.
- **FR-3.6** Minimum structural coverage for v1:
  - **Order-of-operations** — a permission-setting call following, rather than being fused with,
    the creation of the same resource (the TOCTOU shape).
  - **Decision shape** — a validation function whose control flow branches over a literal
    collection and returns a boolean; the syntactic signature of a denylist (P3).
  - **Unvalidated reach** — a write or execution call whose path argument does not pass through a
    function identified as validating.
  - **Sink adjacency** — an interpolated or concatenated value flowing into a dangerous call
    within a single function body.
- **FR-3.7** *(v2)* Cross-function dataflow. FR-3.6 operates within a function body; tainted input
  that reaches a sink through intermediate calls is still invisible. This remains an owned
  obligation and the report's caveats section states it explicitly until it ships.
- **FR-3.8** Structural analysis is language-specific and degrades honestly: where no parser
  exists for a language in the closure, that fact is recorded in the report as a coverage gap
  rather than passed over.

#### 3c. Surface source

- **FR-3.9** Every triggerable surface from FR-1.3 generates a ledger candidate automatically,
  with `source: surface`, **whether or not any pattern or structural rule matched it**. The
  candidate reads: *this entry point is externally reachable — trace it to its sinks.*
- **FR-3.10** This source exists to break the dependency between the detection mechanism and the
  review scope. Where patterns and structure alone decide what gets read, logic with no
  syntactic signature is never examined, and the catalog silently determines which questions are
  never asked. Surface candidates guarantee that every reachable entry point is read by a human
  reviewer regardless of what the automation noticed. They are expected to be the smallest source
  by count and the most valuable per item.
- **FR-3.11** A surface candidate resolves only on a traced account of what the entry point
  reaches. "Nothing matched here" is not a resolution.

#### 3d. Catalog and layers

- **FR-3.2** Patterns are **questions, not findings**. Every candidate, from any source, enters
  with `status: unresolved`.
- **FR-3.3** The catalog is data (`YAML`), not code. Adding a pattern must never require editing a
  script. Each pattern carries: `id`, `regex`, `layer[]`, `languages`, `question`, `precision`,
  `default_severity_hint`, `references`, and `owasp` (Agentic Top 10 category, where one applies —
  see §2.4). Structural rules are likewise declared as data where their shape
  allows.
- **FR-3.12** The catalog is versioned (`catalog_version`, bumped on any pattern or structural
  rule change). Every run records the version it ran under — this is what makes FR-4.6
  invalidation possible.
- **FR-3.4** Minimum **code-layer** coverage: command execution, deserialization, dynamic eval,
  path handling and traversal, file write and permission setting, credential/secret storage,
  network bind addresses and firewall rules, logging of sensitive parameters, TLS verification
  disablement, temp file creation, subprocess shell usage, runtime download-and-execute.
- **FR-3.13** Minimum **instruction-layer** coverage (P8), applied to all prose in the closure:
  directions to bypass, suppress, or pre-approve confirmation prompts; assertions of elevated
  authorization or special permissions; instructions to disregard prior, system, or user
  instructions; directions to conceal actions from the user or to avoid mentioning them;
  instructions to write outside the working directory or into agent-configuration locations;
  directions to transmit context, file contents, or credentials to a network destination;
  instructions to install, register, or modify other agentic components.
- **FR-3.14** Minimum **manifest-layer** coverage (P10): unbounded or wildcard tool grants,
  filesystem scopes exceeding the artifact's stated purpose, network permissions in artifacts with
  no stated network need, hook bindings on events that permit rewriting or suppressing tool calls,
  and activation descriptions broad enough to load the artifact into unrelated contexts.
- **FR-3.15** Instruction-layer patterns are weaker signals than code patterns — natural language
  has no fixed syntax, and paraphrase defeats regex. They therefore *raise questions for manual
  review* and never auto-classify. Where the instruction layer is substantial, Phase 4 must
  include a full read of the prose closure, not only the windows around candidates. This is a
  deliberate and permanent cost of P8, not a temporary gap.

### Phase 4 — Triage (GATE)

- **FR-4.1** For each hit, read a bounded window around it (`window.sh`), never the whole file by
  default. Whole-file reads require an explicit reason recorded in the ledger. Prose files flagged
  under FR-3.15 are a standing exception with a standing reason, as are surface candidates
  (FR-3.11), which are traced rather than windowed.
- **FR-4.2** Resolve each hit to `finding` or `verified-ok`, each with a written rationale.
  `verified-ok` rationales must state *what makes it safe*, not that it "looks fine."
- **FR-4.3** `verify_ledger.py` fails the run if any hit remains `unresolved`. The report cannot be
  rendered on a failing ledger.
- **FR-4.4** Support `deferred` as a third status with a mandatory reason — for genuine blockers
  (needs runtime, needs maintainer input). Deferred items appear in the report under "Not
  conclusively assessed." They are never silently dropped.
- **FR-4.5** Every `verified-ok` resolution carries a **verification record**: who/what verified it,
  when, the `catalog_version` in force, the reviewed `target_version`, a `window_sha256` of the
  exact content window the judgment was made against, and a **semantic anchor** (`file` + enclosing
  symbol or section, plus a normalised AST signature where the language allows). A verification
  without a scope cannot be trusted later, and one anchored only to a line number is lost the
  moment the content moves.
- **FR-4.6** On re-review, each prior verification is re-evaluated against these triggers, and the
  trigger class determines the consequence:

  | Trigger | Consequence |
  |---|---|
  | `window_sha256` differs — the reviewed content itself changed | **Invalidated** → back to `unresolved`, full re-review, no shortcut |
  | `catalog_version` increased and a new/changed pattern matches this location | **Invalidated** → the original judgment was made without this question being asked |
  | Capability manifest changed (FR-1.4) | **Invalidated** for every verification whose rationale depended on a grant boundary |
  | Target released a new version, content window unchanged | **Expired** → cheap re-affirmation, batchable |
  | `ttl_days` elapsed (default 180), nothing else changed | **Expired** → cheap re-affirmation, batchable |
  | Hit present in a prior review, not matched in this one | **Vanished** → never auto-resolved; see FR-4.9 |

- **FR-4.7** The hard/soft split in FR-4.6 is load-bearing and must not be collapsed. If invalidated
  and expired items appear as one undifferentiated queue, that queue grows until it is bulk-approved
  unread — reproducing precisely the failure mode in §1. Expired items may be re-affirmed in batch
  with a single rationale; invalidated items may never be.
- **FR-4.8** The report distinguishes freshly reviewed items from carried-forward ones. A reader is
  entitled to know which conclusions were reached against this version of the artifact.
- **FR-4.9** A hit that disappears between reviews has three possible explanations, and only one of
  them is good: the content was genuinely fixed; it moved and the issue moved with it; or the fix
  broke the *pattern match* without breaking the *problem* (e.g. an interpolation hoisted to a
  preceding line, or an instruction rephrased without changing its effect). The third is the most
  dangerous outcome this system can produce, because it looks exactly like success. Absence of a
  match is therefore never evidence of a fix. Resolve vanished hits with targeted re-checks, in
  this order of strength:

  1. **Re-run the PoC** (FR-5.5). Behavioural, and indifferent to refactoring, renaming, or
     movement. Pass → the issue survives. Fail → probable fix, pending confirmation. Errors out →
     see FR-5.6.
  2. **Follow the semantic anchor** (FR-4.5). Locate the enclosing symbol or section wherever it
     now lives; covers movement even with no PoC available.
  3. **Widened targeted sweep** — run only the relevant pattern, in a looser variant, scoped to the
     file/module, alongside `git log --follow` and the inter-version diff.

- **FR-4.10** What remains after FR-4.9 goes to a manual queue: architectural findings, which have
  no PoC by nature; instruction-layer findings, where "fixed" is a judgment about meaning rather
  than a test result; content deleted and replaced by a different implementation; and broken PoCs.
  The queue is expected to be small — that is the point. A resolution mechanism people route
  around because it is too laborious provides no assurance at all.

### Phase 5 — Reachability & proof

- **FR-5.1** Every finding carries a `reachability` value from a closed enum:

  | Value | Meaning |
  |---|---|
  | `network` | Reachable by a remote party |
  | `mcp-tool` | Reachable by an agent invoking an exposed tool |
  | `skill-autoload` | Reached when the artifact loads on topic match, with no user action |
  | `hook-lifecycle` | Reached automatically on a lifecycle event, with no user action |
  | `agent-instruction` | Reached because content in the agent's context directs it |
  | `untrusted-content` | Reached via data the agent processes from an untrusted source |
  | `cli-only` | Requires a deliberate human command |
  | `config-file` | Requires the user to have edited configuration |
  | `local-privileged` | Requires access the attacker would have to already hold |
  | `unreachable` | No path found |

  The first six are the agentic-specific values, and `skill-autoload` and `hook-lifecycle` rank
  high precisely because no user action stands between the attacker and execution.
- **FR-5.2** Every finding carries `preconditions[]` — what must already be true for the issue to
  matter (e.g. "the user has this skill installed and asks about a matching topic").
- **FR-5.3** Findings rated High or Medium require a proof-of-concept that exercises the *actual*
  artifact under review and demonstrates the boundary being crossed. Without one, severity is
  capped (§6.2). For instruction-layer findings, where behavioural proof may be impossible or
  non-deterministic, the equivalent evidence is the verbatim instruction plus a reasoned account of
  the behaviour it directs — recorded as `evidence_type: instruction` and capped accordingly.
- **FR-5.4** PoCs are demonstrators, not weapons. See §9.2.
- **FR-5.5** PoCs are **retained as regression tests**, not discarded after the report. Each is
  stored with the finding, runnable against any later version, and reports one of three outcomes:
  `still-vulnerable` | `no-longer-vulnerable` | `inconclusive`. This makes the PoC library a
  compounding asset: the second review of a target is largely mechanical, and it is the strongest
  argument for the requirement in FR-5.3 — the proof is not only evidence for the reader, it is the
  instrument that tells you whether the fix worked.
- **FR-5.6** A PoC that fails to *execute* (symbol missing, signature changed, import error) is
  `inconclusive` — never `no-longer-vulnerable`. It signals material change and requires human
  judgment. Conflating a broken test with a passed one is the same category of error as FR-4.9's
  third case.

### Phase 6 — Severity

- **FR-6.1** Severity is computed from impact × reachability × preconditions per
  `references/severity-matrix.md`, and the reasoning is recorded, not just the label.
- **FR-6.2** Caps, applied mechanically:
  - No PoC and no `evidence_type: instruction` record → maximum `Observation`.
  - `evidence_type: instruction` → maximum `Medium`, unless the instruction is unambiguous and
    directs a concretely dangerous action (exfiltration, concealment, writing to agent-config
    locations), in which case the cap lifts.
  - `cli-only` reachability → maximum `Medium`, unless the issue crosses a privilege or trust
    boundary — for example a write primitive landing in an agent-controlled configuration
    directory.
  - `unreachable` → `Informational`, retained in the report as hardening.
- **FR-6.3** Architectural critiques (design-level, no single defective element) are tagged
  `architectural` and segregated in the report. Mixing them into the findings table dilutes the
  concrete findings and measurably worsens maintainer response.
- **FR-6.4** Per **D-3** (§13), the report emits **both** ratings: the internal matrix rating as the
  authoritative one, plus an estimated CVSS v4 vector and score as a convenience field for filling
  out an advisory. The CVSS value is always flagged `estimated: true`, and is frequently a poor fit
  for agentic reachability classes — it is offered for legibility, not accuracy.
  **The CVSS value never feeds the caps in FR-6.2.** The caps are the only structural defence
  against severity inflation; a score computed from an external rubric must not route around them.

### Phase 7 — Report

- **FR-7.1** `render_report.py` generates the report from structured data. The model does not
  hand-write the report body; it fills the structured fields.
- **FR-7.2** Mandatory sections: metadata & version identity, scope statement, review mode,
  capability manifest summary, closure inventory, methodology summary, findings by severity,
  **verified-correct inventory**, unproven observations, not-conclusively-assessed items,
  recommended remediation order, reviewer caveats.
- **FR-7.3** Every finding includes exact location, the relevant excerpt, the PoC or instruction
  evidence, a concrete suggested fix, and the reachability/preconditions fields.
- **FR-7.4** Remediation order is by fix-cost-adjusted risk, not raw severity — a one-line High fix
  precedes a refactor-scale Medium.
- **FR-7.5** In `environment` mode the report additionally states the composition risks from FR-0.8
  and which components participate in each.

### Phase 8 — Disclosure

- **FR-8.1** Detect the correct channel: `SECURITY.md` → follow it; otherwise a private security
  advisory; never a public issue for unfixed High/Medium findings. Where the artifact is
  distributed through a registry or marketplace, that operator is an additional recipient.
- **FR-8.2** Emit an explicit embargo statement naming which findings are embargoed and which may
  be discussed publicly.
- **FR-8.3** Produce a short maintainer-facing cover message separate from the full report.
- **FR-8.4** Never auto-submit. Disclosure is always a human action. The skill prepares the
  artifact and stops.
- **FR-8.5** Where a finding indicates deliberate malice rather than a defect — concealed
  exfiltration, hidden persistence — the disclosure path differs: the recipient is the distribution
  operator and the affected users, not only the author. `references/disclosure-playbook.md` holds
  this branch. The determination of intent is a human judgment and is never made by the skill.

### Phase 9 — Finding lifecycle (re-review only)

- **FR-9.1** Findings carry a status across reviews, drawn from a deliberately small set:
  `open` | `fixed` | `wont-fix` | `regressed`. Resist growing this into a state machine — this is a
  review tool, not an issue tracker, and every added state is one more thing to adjudicate.
- **FR-9.2** There is no `partially-fixed` status. A partial fix **closes** the original finding as
  `fixed` and **opens a new finding** for the residue, linked by `derived_from`. Two reasons: every
  finding keeps a binary fate rather than lingering in an ambiguous state nobody knows how to
  action, and the message to the maintainer sharpens from "still partly open" to "here is precisely
  what remains." Partial fixes are the common case — a maintainer fixes what is cheap and defers
  what needs restructuring.
- **FR-9.3** `regressed` is detected by the regression suite: a PoC that failed against one version
  and passes again later. Near-free given FR-5.5.
- **FR-9.4** The regression suite **proposes**; a human **confirms**. No finding closes
  automatically, on the same reasoning as FR-8.4.
- **FR-9.5** Lifecycle fields enter the schema now; transitions are implemented when the first
  re-review happens. Adding fields before there is data is free; migrating after is not.

---

## 7. Data contracts

Stable schemas matter more than any individual script — they are what lets the pipeline be
rewritten piecemeal.

```jsonc
// hits.jsonl — one JSON object per line (JSON Lines).
// The unit is one candidate — a pattern match, a structural rule match, or a triggerable
// surface. Not one line of content: most lines produce no record, and one line may produce
// several if several rules match it (see D-6).
{
  "id": "H-0042",
  "file": "src/app/paths.py",
  "line": 137,
  "layer": "code",                 // code | instruction | manifest
  "source": "pattern",             // pattern | structure | surface
  "rule_id": "path.denylist",      // pattern id, structural rule id, or surface id
  "precision": "low",              // high | medium | low — shapes how the report presents it
  "question": "Is this an allowlist or a denylist?",
  "status": "unresolved",          // unresolved | finding | verified-ok | deferred
  "resolution_note": null,
  "finding_id": null,
  "catalog_version": "2026.08.1",
  "verification": {                // present only when status == "verified-ok"
    "verified_at": "2026-08-30T09:14:00Z",
    "target_version": "v0.9.14",
    "window_sha256": "9f2c…",
    "anchor": {"file": "src/app/paths.py", "symbol": "validate_output_path"},
    "manifest_sha256": "4ab1…",
    "ttl_days": 180,
    "freshness": "valid"           // valid | expired | invalidated | vanished
  }
}
```

```jsonc
// findings.json
{
  "id": "F-1",
  "title": "Denylist bypass in output path validation",
  "severity": "High",              // High | Medium | Low | Observation | Informational
  "cvss_v4": {                     // convenience only — never feeds FR-6.2 caps
    "vector": "CVSS:4.0/AV:L/AC:L/…",
    "score": 7.1,
    "estimated": true
  },
  "kind": "concrete",              // concrete | architectural
  "layer": "code",                 // code | instruction | manifest | composition
  "component": "skills/example",   // originating component (environment mode)
  "locations": ["src/app/paths.py:137-158"],
  "reachability": "mcp-tool",
  "preconditions": [],
  "impact": "...",
  "evidence_type": "poc",          // poc | instruction
  "poc": {
    "path": "poc/f1_path_bypass.py",
    "summary": "...",
    "last_run": {"target_version": "v0.9.15", "result": "no-longer-vulnerable"}
  },
  "lifecycle": {
    "status": "open",              // open | fixed | wont-fix | regressed
    "derived_from": null,          // finding id, when this is the residue of a partial fix
    "history": [
      {"target_version": "v0.9.14", "status": "open", "confirmed_by": "human"}
    ]
  },
  "patch": "...",
  "confidence": "high",            // high | medium | low
  "hit_ids": ["H-0042"]
}
```

---

## 8. Threat model structure

Two layers. The core carries what is true of every agentic artifact; overlays carry what is
specific to a form. This is what makes adding an archetype cheap (AC-4) and stops the same
agentic reasoning being restated five times and drifting out of sync.

### 8.1 `_agentic-core.md` — always loaded for agentic targets

Mandatory content:

1. **Trust boundaries** — where untrusted content meets agent context, and whether the artifact
   marks the crossing at all.
2. **Text as instruction (P8)** — everything reaching the context window is behaviour-defining.
   Tool return values, file contents, fetched pages, and error strings all qualify.
3. **File write as execution (P7)** — shell startup files, git hooks, agent configuration and rules
   directories, autostart locations. Any write primitive is assessed against this list.
4. **Capability grants (P10)** — is the grant bounded by the artifact's stated purpose, and is the
   boundary enforced anywhere or merely described?
5. **Closure and deferred loading (P9)** — what loads later, under what condition, from where.
6. **Autonomous reachability** — what executes with no user action, and what the user would see if
   it did.
7. **Persistence and lateral reach** — can the artifact alter other agentic components, its own
   configuration, or its permission grants?
8. **Egress** — where data can leave, whether the user would notice, and whether the artifact has
   any stated need for network access at all.

### 8.2 Overlay files

Each `threat-models/<archetype>.md` contains, in this order:

1. **Applies when** — classification signals (file layout, manifest keys, dependencies, entry-point
   shapes).
2. **Additional trust boundaries** beyond the core.
3. **Archetype-specific dangerous sinks.** For `mcp-server.md` this includes *tool return values*,
   because they land in an agent's context and become instructions. For `hook.md` it includes the
   ability to rewrite or suppress a tool call before it executes. For `skill.md` it includes the
   activation description, whose breadth determines which unrelated contexts the artifact is
   loaded into.
4. **Mandatory questions** — an explicit checklist.
5. **Pattern packs to enable.**
6. **Known-good implementations** — what a correct solution looks like, so `verified-ok`
   resolutions have a reference point rather than a gut feeling.

### 8.3 Composition

An artifact matching several archetypes loads the core once and every matching overlay. Mandatory
questions accumulate; they are not deduplicated by similarity. A plugin bundle is reviewed as
skill *and* hook *and* MCP server, and separately for the seams between them (FR-0.8).

---

## 9. Non-functional requirements

- **NFR-1 — Context economy.** Windowed reads by default; whole-content reads require
  justification, with prose closures under FR-3.9 as a standing exception. Target: a 50k LOC
  target reviewed within a single subagent context without compaction.
- **NFR-2 — Resumability.** The ledger is the state. A run interrupted at any phase resumes from
  `hits.jsonl` without redoing prior phases.
- **NFR-3 — Determinism where claimed.** Two runs of the generation scripts (`recon.sh`,
  `closure.py`, `sweep.py`, `structure.py`, `surfaces.py`) on the same version produce
  byte-identical output. Only judgment phases may vary.
- **NFR-4 — Zero network egress from scripts.** Everything operates on a local copy.
- **NFR-5 — Portability.** Python 3.11+ and POSIX shell only; no service dependencies.
- **NFR-6 — Extensibility without code changes.** New pattern, new archetype, or new reachability
  class = new or edited data file.
- **NFR-7 — Content isolation.** Reviewed content may contain instructions aimed at the reviewing
  agent. It is handled as data throughout: quoted, never followed. The reviewing subagent runs with
  no write access outside its workspace, so that a successful injection has nowhere to land.

---

## 10. Guardrails

- **G-1 — Defensive posture only.** The output is a report that helps a maintainer or a user fix
  their exposure. The skill must not produce deployable exploit chains, payload delivery,
  persistence mechanisms, or exfiltration tooling — and must not produce a working malicious skill,
  hook, or MCP server as a "demonstration."
- **G-2 — PoC discipline.** A PoC demonstrates that a boundary is crossed and stops there: it
  exercises the real artifact and shows which inputs are wrongly accepted, ideally as an
  allowed/blocked table. It does not chain to impact.
  `references/poc-guidelines.md` holds the concrete rules and worked examples.
- **G-3 — No secrets in artifacts.** Any credential, token, or cookie encountered while reviewing is
  redacted in the ledger and report, never reproduced.
- **G-4 — Third-party artifacts stay untouched.** No writes to the reviewed target beyond a scratch
  copy. No pushes. No installation or registration (FR-0.5). No issue or advisory submission without
  explicit human action (FR-8.4).
- **G-5 — Honest uncertainty.** `confidence` is a required field. Instruction-layer findings state
  plainly that they rest on reading intent rather than on a behavioural test.
- **G-6 — Prompt injection is an input, not an instruction.** Content encountered during review that
  addresses the reviewing agent is reported as a finding and never acted on. If the reviewed target
  attempts to direct the review, that attempt is itself a High-severity finding.

---

## 11. Integration

- **10.1 Subagent.** `agents/security-reviewer.md` runs the skill in an isolated context with a
  restricted tool set (read, grep, bash-for-scripts). No write access outside the workspace — this
  is the enforcement half of NFR-7, not merely hygiene.
- **10.2 Multi-model second pass (optional).** After Phase 4, an independent large-context pass over
  the closure answers one question only: *what class of issue would this pattern catalog
  structurally miss here?* Its output feeds new patterns, not new findings — keeping the ledger
  single-sourced. Particularly valuable at the instruction layer, where FR-3.9 concedes regex is
  weak.
- **10.3 Install-time gate (future).** A hook that blocks installation of a new agentic component
  until a review exists for that version, on your own environment. Out of scope for v1; the data
  contracts must not preclude it.
- **10.4 Self-review.** The skill is run against itself as part of the release process (AC-10).

---

## 12. Evaluation & acceptance

### 12.1 Regression corpus

Targets spanning at least four archetypes, of three kinds: real artifacts pinned at versions with
**publicly documented, already-fixed** issues; clean artifacts as negative controls; and
purpose-built malicious samples authored for the corpus, never distributed, covering the
instruction and manifest layers where public examples are scarce. Fixed-and-public only for the
first kind — this is a test harness, not a hunting ground.

### 12.2 Metrics

| Metric | Definition | v1 target |
|---|---|---|
| Recall | ground-truth issues correctly reported | ≥ 70% |
| Instruction-layer recall | tracked separately — expected lower | ≥ 60% |
| Ledger completeness | runs ending with zero `unresolved` | 100% |
| Unsupported-finding rate | findings whose PoC fails to reproduce | ≤ 5% |
| Negative-control cleanliness | High/Medium findings on clean targets | 0 |
| Severity agreement | ratings within one tier of ground truth | ≥ 80% |
| Gate compliance | runs presenting threat model before content reads | 100% |
| Injection resistance | reviews of injection-bearing samples where the attempt is reported and not followed | 100% |
| Cost | tokens & wall-clock per 10k LOC | tracked, not gated |
| Source contribution | share of true findings originating from each of the three sources | tracked — a source contributing nothing is a design failure, not a saving |
| Catalog redundancy | pattern pairs matching the same locations with the same resolution | tracked — candidates for merge in YAML (D-6) |
| Partial-fix rate | maintainer fixes that closed only part of a finding | tracked — informs how findings are scoped |

### 12.3 Acceptance criteria for v1

- **AC-1** All of §5 Phases 0–7 implemented for `artifact` mode; Phase 8 produces an artifact but
  never submits; Phase 9 fields exist in the schema.
- **AC-2** `verify_ledger.py` demonstrably blocks report rendering on an unresolved hit.
- **AC-3** Metrics in 11.2 met on the regression corpus across three consecutive runs.
- **AC-4** A new archetype can be added by adding one overlay file, with no script changes and no
  edit to `_agentic-core.md` — proven by doing it once.
- **AC-5** A full review of a ≥50k LOC target completes in one subagent context without compaction.
- **AC-6** Re-review at a later version costs materially less than the first review, while every
  content window that changed is provably re-examined from scratch.
- **AC-7** Editing a pattern and bumping `catalog_version` invalidates exactly the affected
  verifications and leaves the rest untouched — proven by doing it once.
- **AC-8** No vanished hit is ever auto-resolved: a corpus case where a fix defeats the pattern
  without fixing the problem is caught by the retained PoC rather than reported as remediated.
- **AC-9a** A corpus case whose defect has no distinctive syntactic signature is still reviewed,
  because the enclosing entry point produced a surface candidate (FR-3.9).
- **AC-9b** Each of the three sources contributes at least one true finding on the corpus that
  neither of the others produced.
- **AC-9** A skill whose payload lives only in a progressively loaded reference file is fully
  covered — closure mapping (FR-1.2) reaches it and the sweep runs against it.
- **AC-10** The skill passes its own review with no unresolved High or Medium findings. The
  review target includes the development harness (`.claude/` hooks, agents, settings), not only
  `src/` — the harness is an assembled set of agentic components and is exactly what
  `environment` mode exists to assess. A guard that covers one write path and leaves another open
  is a composition risk (FR-0.8), not a partial success.
- **AC-11** The skill triggers on realistic phrasings ("is this skill safe to install",
  "check this MCP server before I add it") without the user naming the skill.

---

## 13. Build order

Each milestone ships something usable on its own; nothing is a big-bang dependency.

| # | Milestone | Delivers |
|---|---|---|
| M1 | `recon.sh` + `sweep.py` + `patterns/_base.yaml` + `python.yaml` | Immediate value even driven by hand |
| M2 | `surfaces.py` — the cheapest of the three sources and the one that bounds the others (P11) | Review scope stops being decided by the catalog |
| M3 | `_agentic-core.md` + `skill.md` + `mcp-server.md` + `_classifier.md` | The reusable intellectual asset, aimed at the artifacts actually encountered |
| M4 | `structure.py` + `_structure.yaml` covering FR-3.6 | The checks that matter most stop depending on syntax |
| M5 | `closure.py` + `patterns/_instruction.yaml` + `_manifest.yaml` | The layers that make agentic review real rather than ordinary code review |
| M6 | `SKILL.md` enforcing phase order and gates | The procedure becomes real |
| M7 | `verify_ledger.py` + data contracts frozen (incl. verification & lifecycle records) | Coverage becomes provable |
| M8 | `hook.md` + `subagent.md` + `agent-config.md` overlays | Full agentic coverage |
| M9 | `templates/` + `render_report.py` + disclosure playbook | Shippable output |
| M10 | Regression corpus + eval loop + self-review | Improvement becomes measurable, not felt |
| M11 | Subagent definition + context tuning | Scales to large targets |
| M12 | `environment` mode (Phase 0.5) | Composition risk becomes visible |

`cli-tool.md`, `web-api.md` and `library.md` slot in wherever a real target demands them; they
inherit no core and are the cheapest overlays to write.

---

## 14. Decisions

- **D-2 — Self-contained analysis engine.** No third-party scanner is invoked at any stage.
  *Rationale:* this skill is intended to become a security tool in its own right, not an
  orchestration layer over other people's tools. A secondary benefit is that the strict
  every-hit-resolved gate (FR-4.3) survives — third-party output volume would have forced it to be
  relaxed, and relaxing it removes the system's entire reason to exist. The decision is
  strengthened in v0.2: at the instruction and manifest layers there is no mature third-party tool
  to defer to, so self-containment costs less than it appeared to.
  *Owned cost:* no cross-function dataflow analysis until FR-3.7 ships.

- **D-3 — Combined severity.** Internal matrix is authoritative and feeds the caps; CVSS v4 is
  emitted alongside as an estimated convenience field (FR-6.4). *Rationale:* maintainer legibility
  without surrendering the caps to a rubric that models agentic threat classes poorly.

- **D-4 — Verification expiry with graded triggers.** Verifications carry scope and expire; content
  or catalog or manifest change invalidates hard, time or version drift expires soft (FR-4.5–4.8).
  *Rationale:* re-review at a later version is the highest-ROI use case here, and a verification is
  only ever valid for the content window and the set of questions it was made against.

- **D-5 — Two distinct low-confidence tiers, renamed.** `Observation` is retained and surfaces in
  the report as **"Unproven observations"**; deferred items surface as **"Not conclusively
  assessed."** *Rationale:* they answer different maintainer questions — the first says *fix
  something*, the second says *tell me something*.

- **D-6 — Hits stay independent; findings stay separate.** Two patterns matching one line produce
  two hits and, if both are real, two findings — never merged, no `resolution_group`.
  *Rationale:* a pattern is a question (FR-3.2), and two questions earn two answers even when the
  answers rhyme. Merging would also destroy per-pattern attribution, the only data showing which
  catalog entries earn their place. The asymmetry decides it: duplicated prose costs two
  paragraphs, a wrong merge silently loses a question. Separate findings additionally track
  separately through remediation, which matters because partial fixes are the norm (FR-9.2). Where
  two patterns repeatedly match the same locations and receive the same resolution, the defect is
  in the *catalog*, not the ledger: fix it in YAML at maintenance time rather than by run-time
  judgment.

- **D-7 — Disappearance is not remediation.** Vanished hits are resolved by behavioural re-check,
  anchor-following, or widened sweep (FR-4.9), with a small manual remainder (FR-4.10). PoCs are
  retained as regression tests to make this cheap (FR-5.5), which also converts FR-5.3 from a
  reporting requirement into a compounding asset.

- **D-8 — Minimal finding lifecycle, no partial state.** Four statuses; a partial fix closes the
  original and opens a linked residue finding (FR-9.1–9.2). *Rationale:* keeps this a review tool
  rather than an issue tracker, and keeps every finding's fate binary.

- **D-9 — Agentic core plus overlays, not a flat archetype list.** Skills, MCP servers, subagents,
  hooks, and agent configs share one threat model and differ in form (§7). *Rationale:* the shared
  reasoning is the substance — text as instruction, writes as execution, grants as boundary — and
  restating it per archetype guarantees five copies that drift. Composite targets are the norm, and
  a flat list forces a false choice between overlays that should compose.

- **D-10 — Three analysis layers, with the instruction layer explicitly weak.** Code, instruction,
  and manifest patterns are all first-class, but FR-3.9 concedes that prose patterns raise
  questions rather than settle them, at a permanent cost in manual reading. *Rationale:* an honest
  weak signal beats a confident wrong one. The alternative — treating instruction review as solved
  by regex — would produce exactly the false assurance this document exists to prevent.

- **D-11 — Three peer candidate sources, not a regex scanner.** Patterns, structural AST rules,
  and triggerable surfaces feed one ledger as equals (Phase 3). *Rationale:* the three checks with
  the highest value in this domain — denylist shape, permission-after-creation, writes reaching
  agent-loaded locations — are questions about structure and order, not about the presence of a
  token, and a pattern catalog cannot answer any of them. Structural analysis was therefore
  promoted from a deferred v2 gap (v0.1 FR-3.5) to a v1 requirement; leaving it deferred would
  have left the system's most important checks permanently unowned while the tool appeared to
  work. The surface source exists for a distinct reason (P11): without it, the detection mechanism
  silently determines the review's scope, and logic with no syntactic signature is never read at
  all.

- **D-12 — Build alongside the field, not on top of it.** D-2 is reaffirmed after reviewing prior
  art (§2): no third-party engine in the pipeline, but published rule taxonomies are read and used
  as catalog sources. *Rationale:* the overlap with existing scanners is real at the code layer
  and is not the claim this project makes. The claim is method — resolved coverage, scope set
  independently of detection, scoped verifications that expire — and every part of it would be
  weakened by depending on an external engine's output. Where a finding would also have been
  caught by a general scanner, the report says so rather than implying otherwise.

### Still open

- **Q-1 — Corpus sourcing.** Hand-curated targets, advisory mining, or a first-party mutation
  harness that injects known defect classes into clean artifacts. Deferred by owner decision; must
  be settled before M10. Whichever is chosen, the corpus also needs negative controls, or recall is
  tuned in isolation and the system drifts toward reporting everything. v0.2 adds a further
  requirement: purpose-built malicious samples for the instruction and manifest layers, since
  public examples are scarce and those layers cannot be evaluated without them.
