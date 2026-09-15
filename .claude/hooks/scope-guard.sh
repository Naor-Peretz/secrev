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
  M1) ;;

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
      *) ;;
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

printf '%s' "$body" | grep -qE '^import ast|^from ast |ast\.parse' \
  && note "uses the AST — that is structure.py, M4. The ledger format has to settle first."

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
