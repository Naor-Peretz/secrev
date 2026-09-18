# Protected paths — STACK.md §8 H-4. One definition, sourced by every guard.
#
# H-7 is the reason this file exists: two guards each deciding what "protected"
# means is how the two answers drift apart without either one looking wrong.
#
# The two predicates are not the same set, and the difference is deliberate.
#
#   is_self_application_path — Python under src/ and scripts/. What §2.1 forbids
#   is a construct in code the tool ships or runs.
#
#   is_scoped_path — anything under src/, patterns/, surfaces/ and scripts/. Milestone
#   scope is about what is being built, whatever the file format.
#
# patterns/ is in the second and absent from the first, and that is the whole
# point of separating them. The catalog is the tool's *input*: a rule that
# detects `yaml.load` necessarily contains the string `yaml.load`. Running the
# self-application check over it would refuse the catalog for describing the
# construct it exists to find — data read as if it were code, which is the
# mistake this project argues other scanners make. patterns/ still matters at
# least as much as the code (BRIEF_M0.md §3): a rule added or altered without
# review is a check that silently disappears from every later run. That is a
# scope question, and the scope guard asks it.
#
# Two alternatives per directory, never a leading `*` (H-5, as corrected).
#
# `*/src/secrev/*.py` alone needs a leading directory, so it matches only
# because the client happens to send absolute paths — true today,
# undocumented, and not something a control should rest on. `*src/secrev/*.py`
# fixes that and buys `foosrc/secrev/`; the scripts/ equivalent bought
# `transcripts/` and `descripts/`. Spelling the relative case out explicitly
# costs one alternative each and matches neither.
#
# The over-match failed closed rather than open — it refused writes to paths
# this repository does not contain. That is still the wrong behaviour: a
# control that fires on the wrong file teaches people to work around it.

is_self_application_path() {
    case "$1" in
      src/secrev/*.py|*/src/secrev/*.py|scripts/*.py|*/scripts/*.py) return 0 ;;
      *) return 1 ;;
    esac
}

is_scoped_path() {
    case "$1" in
      src/secrev/*|*/src/secrev/*|patterns/*|*/patterns/*|scripts/*|*/scripts/*) return 0 ;;
      # The surface kinds (M2, TASKS_M2.md C-1): data like the catalog, and
      # scoped like it — self-application does not apply, milestone scope does.
      surfaces/*|*/surfaces/*) return 0 ;;
      # The threat models (M3, TASKS_M3.md D-1). Prose rather than data, and
      # read by the reviewing agent rather than by a script — so the mechanism
      # differs from patterns/ and surfaces/ while the failure mode does not: a
      # mandatory question removed here is a check that disappears from every
      # later review of that archetype. Scoped, so an M4 change cannot rewrite
      # the threat model while calling itself structural work.
      threat-models/*|*/threat-models/*) return 0 ;;
      *) return 1 ;;
    esac
}

# The files that own an NFR-3 rule. Here rather than inline in
# determinism-guard.sh for the same reason as the two predicates above: one
# definition, so correcting the glob form is one edit and not a hunt (H-7).
#
# surfaces.py is here before it exists (TASK-M2-001). It is a third consumer of
# the walk and a third generator of ids in hits.jsonl, and a guard that starts
# watching after the first write has already missed the write that matters.
#
# structure.py and parser.py are here on the same terms (M4, BRIEF_M4.md C2),
# both before either file exists. structure.py is the fourth consumer of the
# walk and the third generator of ids. parser.py is less obvious and is here
# deliberately: it decides the order nodes are visited in, and a traversal order
# that is not a property of the input reaches the output exactly as os.walk's
# does. It is the inventory.py of the AST, not the catalog.py of it.
#
# The rule *loader* is deliberately absent, matching catalog.py and kinds.py,
# which are also absent. Rule order does reach record order — but that is fixed
# by sorting at the point records are emitted, which is structure.py's job and
# is where the guard should fire.
is_nfr3_path() {
    case "$1" in
      src/secrev/ids.py|*/src/secrev/ids.py) return 0 ;;
      src/secrev/inventory.py|*/src/secrev/inventory.py) return 0 ;;
      src/secrev/sweep.py|*/src/secrev/sweep.py) return 0 ;;
      src/secrev/recon.py|*/src/secrev/recon.py) return 0 ;;
      src/secrev/surfaces.py|*/src/secrev/surfaces.py) return 0 ;;
      src/secrev/ledger.py|*/src/secrev/ledger.py) return 0 ;;
      src/secrev/structure.py|*/src/secrev/structure.py) return 0 ;;
      src/secrev/parser.py|*/src/secrev/parser.py) return 0 ;;
      *) return 1 ;;
    esac
}
