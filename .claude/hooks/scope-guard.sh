#!/bin/sh
# PreToolUse (Write|Edit) — milestone scope discipline (BRIEF_M1.md §1, §8).
#
# The realistic failure mode when building M1 is not a bug. It is an agent
# adding something that looks like an obvious improvement and is explicitly a
# later milestone: a severity decision, a dedup by location, a `multiline`
# field "for later". Each of those is forbidden by name in the brief, and each
# looks reasonable to anyone who has not read it.
#
# This does not block. It returns `ask`, which puts the call in front of the
# human — BRIEF_M1.md §8: raise a conflict, do not resolve it silently.

set -eu
INPUT=$(cat)

ROOT="${CLAUDE_PROJECT_DIR:-.}"
READER="$ROOT/.claude/hooks/lib/hook_input.py"

# JSON is read by lib/hook_input.py, not jq (STACK.md §2). Every path that
# cannot complete the check exits 2, never 0 (H-1).
SYSPY=$(command -v python3 2>/dev/null) || {
    echo "scope-guard: no python3 — cannot check (STACK.md §8 H-1)." >&2
    exit 2
}
[ -f "$READER" ] || {
    echo "scope-guard: $READER is missing — cannot check (H-1)." >&2
    exit 2
}

PATHS="$ROOT/.claude/hooks/lib/paths.sh"
[ -f "$PATHS" ] || {
    echo "scope-guard: $PATHS is missing — cannot check (H-1)." >&2
    exit 2
}
. "$PATHS"

read_field() {
    printf '%s' "$INPUT" | "$SYSPY" "$READER" "$1" || {
        echo "scope-guard: unreadable hook payload — refusing (H-1)." >&2
        exit 2
    }
}

# The path filter runs FIRST, and the order is load-bearing. H-6 makes an
# unknown milestone exit 2; with the milestone checked first, that refusal
# would land on every write in the repository rather than on the scoped ones.
# A guard that refuses everything is as useless as one that refuses nothing.
path=$(read_field file_path)
is_scoped_path "$path" || exit 0

# H-6: a guard with no rules for the current state refuses. This was
# `|| echo M1` followed by `|| exit 0` — two H-1 breaches in two lines. Unable
# to read the marker it assumed the one milestone it had rules for, and given
# a milestone it did not recognise it reported no objection. Both are "I did
# not check" wearing the face of "I checked and it is fine".
MILESTONE=$(cat "$ROOT/.claude/MILESTONE" 2>/dev/null) || {
    echo "scope-guard: cannot read $ROOT/.claude/MILESTONE — cannot check (H-1)." >&2
    exit 2
}
MILESTONE=$(printf '%s' "$MILESTONE" | tr -d ' \t\n\r')

refuse_no_rules() {
    {
      echo "BLOCKED — milestone ${MILESTONE:-<empty>} has no rules permitting this write, and it"
      echo "touches ${path##*/}, which is inside the scoped tree (src/, patterns/, surfaces/, scripts/)."
      echo
      echo "STACK.md §8 H-6: a guard with no rules for the current state refuses. Not knowing"
      echo "what is permitted is not the same as concluding that everything is."
      echo
      echo "Either .claude/MILESTONE is stale, or this milestone needs its own rules added here."
    } >&2
    exit 2
}

case "$MILESTONE" in
  # M1 is the pattern sweep. Its remit is src/, patterns/ and their tests, and
  # the bare `;;` it had said so by permitting everything scoped — which was
  # true while src/, patterns/ and scripts/ were the whole scoped tree, and
  # stopped being true the moment surfaces/ and threat-models/ joined it. Same
  # omission as M2's, found in the same assertion (TASKS_M3.md D-1): a branch
  # written before a directory existed answers "permit" for it by silence.
  M1)
    case "$path" in
      *threat-models/*)
        {
          echo "BLOCKED — M1 is the pattern sweep; the threat models are M3."
          echo "$path is in threat-models/, whose overlays decide which questions"
          echo "every later review of an archetype asks (BRIEF_M3.md §1)."
          echo
          echo "A closed milestone editing them is how a question disappears with"
          echo "nothing reporting it."
        } >&2
        exit 2
        ;;
      *) ;;
    esac
    ;;

  # M2 is the surface source (BRIEF_M2.md). src/ is its remit — surfaces.py,
  # the cli subcommand, their tests — and so is surfaces/, the kind data the
  # source reads (TASKS_M2.md C-1, NFR-6). patterns/ is not: M2 adds a *source*,
  # not rules, and catalog packs are M5. Refusing it here is the same reasoning
  # as M0's, one milestone on: a milestone that can write anything has no scope.
  #
  # This branch exists because closing M1 moved the marker to M2, and until it
  # was written H-6 correctly refused every write to the scoped tree. The
  # answer to "no rules for this milestone" is to write the rules — never to
  # move the marker back to buy write access.
  M2)
    case "$path" in
      *patterns/*)
        {
          echo "BLOCKED — M2 adds a candidate source, not catalog rules."
          echo "$path is in patterns/, and instruction and manifest packs are M5"
          echo "(BRIEF_M2.md §1). If a seed pattern is genuinely wrong, that is an"
          echo "M1 correction and belongs in its own commit, not in M2's work."
        } >&2
        exit 2
        ;;
      # Added when threat-models/ entered the scoped tree (TASKS_M3.md D-1).
      # An assertion written for M3 found this branch letting M2 write an
      # overlay: it refused patterns/ by name and passed everything else, so
      # scoping a new directory did not police it. The catalog's reasoning
      # applies unchanged — a milestone that can write anything has no scope —
      # and the questions M3 writes are checks exactly as a pattern is.
      *threat-models/*)
        {
          echo "BLOCKED — M2 is the surface source; the threat models are M3."
          echo "$path is in threat-models/, whose overlays decide which questions"
          echo "every later review of an archetype asks (BRIEF_M3.md §1)."
          echo
          echo "A closed milestone editing them is how a question disappears with"
          echo "nothing reporting it. If an overlay is genuinely wrong, that is an"
          echo "M3 correction and belongs in its own commit."
        } >&2
        exit 2
        ;;
      *) ;;
    esac
    ;;

  # M3 is the threat-model layer (BRIEF_M3.md): the core, two overlays and the
  # classifier, as prose in threat-models/ at the repository root. That path is
  # outside the scoped tree, so this guard never sees M3's actual deliverables
  # — which is the point. What it does see is a write to src/, patterns/,
  # surfaces/ or scripts/, and under M3 every one of those is out of remit:
  # structure.py is M4, the instruction and manifest packs are M5, SKILL.md and
  # the phase gate are M6, and M3 adds no surface kinds.
  #
  # Refused here with its own message rather than by falling through to
  # refuse_no_rules, which says "this milestone needs its own rules added
  # here". Once M3 has rules that sentence is false, and a guard that refuses
  # for a reason it no longer holds teaches a reader to stop believing the
  # message (H-9: answer in the protocol, and say the true thing).
  M3)
    case "$path" in
      *threat-models/*) exit 0 ;;
      *)
        {
          echo "BLOCKED — M3 is the threat-model layer, and it writes prose."
          echo "$path is in the scoped tree, and M3's deliverables are"
          echo "threat-models/*.md (BRIEF_M3.md §1, §2)."
          echo
          echo "structure.py is M4; the instruction and manifest packs are M5;"
          echo "SKILL.md and the Phase 2 gate are M6. If a pattern or a kind is"
          echo "genuinely wrong, that is a correction to its own milestone and"
          echo "belongs in its own commit, not inside M3's work."
        } >&2
        exit 2
        ;;
    esac
    ;;

  # M3.5 is the hardening pass (BRIEF_M3.5.md): the reviewer against a hostile
  # target. Its remit is the machinery — src/ for the walk, the ledger, recon
  # and the CLI; scripts/ for self_check.py, which P3 makes a finding as it
  # stands; and patterns/ for exactly one rewrite, log.sensitive, which is
  # quadratic on a crafted line.
  #
  # patterns/ is permitted here and was refused under M2. That is a real
  # widening, and it is bounded by the brief rather than by this guard:
  # BRIEF_M3.5.md §2 says no pattern is added and no question changes. A guard
  # cannot check that; a reviewer can, and the positive/negative fixture pair
  # every pattern ships is what catches a changed rule.
  #
  # surfaces/ and threat-models/ are refused by name rather than by omission.
  # That is the D-1 lesson from M3, which cost a failed assertion to learn: a
  # branch written before a directory existed answers "permit" for it silently,
  # so every scoped directory is answered here explicitly.
  M3.5)
    case "$path" in
      *surfaces/*)
        {
          echo "BLOCKED — M3.5 hardens the machinery; it adds no reachability classes."
          echo "$path is in surfaces/, and a surface kind decides which entry points"
          echo "enter the ledger at all (P11, NFR-6). New kinds are M8."
          echo
          echo "Fixing how the surface source *reads* files is in remit —"
          echo "src/secrev/surfaces.py is permitted. Changing what it looks for is not."
        } >&2
        exit 2
        ;;
      *threat-models/*)
        {
          echo "BLOCKED — M3.5 hardens the machinery; the threat models are M3's, and closed."
          echo "$path is in threat-models/, whose overlays decide which questions"
          echo "every later review of an archetype asks (BRIEF_M3.md §1)."
          echo
          echo "A milestone editing them is how a question disappears with nothing"
          echo "reporting it. If an overlay is genuinely wrong, that is an M3"
          echo "correction and belongs in its own commit."
        } >&2
        exit 2
        ;;
      *) exit 0 ;;
    esac
    ;;

  # M4 is the structural source (BRIEF_M4.md): the third and last peer candidate
  # source. Its remit is src/ for structure.py, the Parser interface, the CLI
  # subcommand and recon's coverage-gap line; scripts/ for determinism_check.py,
  # which must compare the structure block as it already compares the other two;
  # structure/ for the rule data; and tests/golden/ for the new goldens.
  #
  # patterns/ is refused, and that is a narrowing from M3.5 rather than an
  # omission. M3.5 was permitted patterns/ for exactly one rewrite; BRIEF_M4.md
  # §1 says no pattern is added and no surface kind changes. A structural rule
  # that wants a pattern is a finding about the catalog, recorded.
  #
  # **structure/ is permitted on the assumption Q1 resolves that way, and the
  # refusal below says so.** BRIEF_M4.md §6 Q1 is open: the PRD's §7 tree puts
  # the rule file at patterns/_structure.yaml, while M2 set the opposite
  # precedent by giving surface kinds a directory of their own. If the owner
  # resolves Q1 toward the PRD tree, this case changes with it — a guard that
  # silently permitted both would answer a question the owner has not.
  #
  # Every scoped directory is answered by name, which is the D-1 lesson M3 paid
  # a failed assertion to learn.
  M4)
    case "$path" in
      *surfaces/*)
        {
          echo "BLOCKED — M4 adds a candidate source, not a reachability class."
          echo "$path is in surfaces/, and a kind decides which entry points enter"
          echo "the ledger at all (P11, NFR-6). New kinds are M8."
          echo
          echo "src/secrev/surfaces.py is not in remit either: the sources are peers"
          echo "and M4 has no business inside another one (D-11)."
        } >&2
        exit 2
        ;;
      *patterns/*)
        {
          echo "BLOCKED — M4 adds no patterns. BRIEF_M4.md §1."
          echo "$path is in patterns/. A structural rule that wants a pattern that"
          echo "does not exist is a finding about the catalog, recorded in the"
          echo "ledger — not a pack edited inside the milestone that would benefit."
          echo
          echo "Q1 is answered: the rule file is structure/_structure.yaml, not"
          echo "patterns/_structure.yaml, so this branch stays right. It said to"
          echo "change it only when the owner answered — they did, the other way."
        } >&2
        exit 2
        ;;
      # Answered by name, not by falling through to the permit below. A branch
      # written before a directory exists permits that directory by silence,
      # which is the D-1 lesson M3 paid a failed assertion for — and structure/
      # is precisely a directory that did not exist when this case was written.
      *structure/*) exit 0 ;;
      *threat-models/*)
        {
          echo "BLOCKED — the threat models are M3's, and closed."
          echo "$path is in threat-models/, whose overlays decide which questions"
          echo "every later review of an archetype asks (BRIEF_M3.md §1)."
          echo
          echo "M4 writes the analysis that answers some of those questions. Editing"
          echo "the questions to suit the analysis is P11 in the small, which is the"
          echo "reason BRIEF_M3.md deferred this milestone in the first place."
        } >&2
        exit 2
        ;;
      *) exit 0 ;;
    esac
    ;;

  # M0 is harness repair (BRIEF_M0.md). Its own §2 edits scripts/check.sh, so
  # scripts/ is inside its remit; src/ and patterns/ are the tool and its
  # catalog, which M0 has no business touching. H-6 asks a guard to know what
  # is permitted — the answer to "no rules for this milestone" is to write the
  # rules, not to leave the guard ruleless and call the refusal correct.
  #
  # Every branch here ends in a decision. An earlier draft let M0 fall out of
  # the case and into the M1 severity checks below, which silently gave M0 the
  # rules of a different milestone.
  M0)
    case "$path" in
      *scripts/*) exit 0 ;;
      *) refuse_no_rules ;;
    esac
    ;;

  *) refuse_no_rules ;;
esac

body=$(read_field body)
[ -n "$body" ] || exit 0

concerns=""
note() { concerns="${concerns}• $1 "; }

# severity_hint is a legitimate M1 catalog field; deciding a severity is not.
printf '%s' "$body" \
  | grep -vE 'severity_hint' \
  | grep -qE '\bseverity\b[[:space:]]*[:=]|def .*(severity|triage|classify)' \
  && note "assigns or computes a severity — Phase 6 / M6. In M1 patterns are questions, not verdicts (FR-3.2)."

printf '%s' "$body" | grep -qE 'dedup|deduplicat|seen_locations|\(file,[[:space:]]*line\)[[:space:]]*in ' \
  && note "deduplicates by location — D-6 says two patterns on one line stay two hits, always."

printf '%s' "$body" | grep -qE '\bmultiline\b|re\.MULTILINE|re\.DOTALL' \
  && note "introduces multi-line matching — BRIEF §4 forbids it in M1; cross-line reasoning is a structural rule (M4) by definition."

# Skipped under scripts/, where `scripts/self_check.py` has been AST-based
# since M0 — deliberately, because `shell=True` is a structure question and a
# grep there would be the exact mistake the catalog is designed not to make
# (CLAUDE.md records the reasoning). Objecting to it under M3.5, whose remit
# includes hardening that very file, is the shape that teaches people to click
# through a guard — the same reason M2 does not fire the surfaces heuristic on
# the milestone that owns surfaces.
# Skipped under M4, where the AST is the milestone's entire subject — the same
# reason M2 does not fire the surfaces heuristic on the milestone that owns
# surfaces. A guard that objects to the work it exists to permit teaches people
# to click through it, and that costs every other check in this file its
# credibility.
#
# The objection stays correct for M1, M2 and M3, so it is scoped rather than
# removed. Its own message names M4 as the answer; firing it under M4 would be
# the guard contradicting itself.
if [ "$MILESTONE" != "M4" ]; then
  case "$path" in
    scripts/*|*/scripts/*) ;;
    *)
      printf '%s' "$body" | grep -qE '^import ast|^from ast |ast\.parse' \
        && note "uses the AST — that is structure.py, M4. The ledger format has to settle first."
      ;;
  esac
fi

# Skipped under M2, where this is the milestone's entire subject. A guard that
# objects to the work it exists to permit teaches people to click through it,
# and that costs every other check in this file its credibility.
if [ "$MILESTONE" != "M2" ]; then
    printf '%s' "$body" | grep -qE '\bsurfaces?\b.*entry.?point|def .*surface' \
      && note "enumerates surfaces — M2, a separate candidate source with separate semantics."
fi

printf '%s' "$body" | grep -qE '\bunresolved\b.*(count|gate|block)|def verify_ledger' \
  && note "gates on the ledger — M7. Nothing to gate until three sources exist."

[ -z "$concerns" ] && exit 0

reason="Milestone scope check (BRIEF_${MILESTONE}.md §1). This write appears to reach past
${MILESTONE}: ${concerns}
Building it now is not merely early — the brief says each of these gets designed wrong before its
prerequisite lands. If it is genuinely needed, that is a conflict with the brief and should be
raised (BRIEF_M1.md §8 states the rule), not resolved here."

printf '%s' "$reason" | "$SYSPY" "$ROOT/.claude/hooks/lib/hook_ask.py"
exit 0
