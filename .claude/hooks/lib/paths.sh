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
#   is_scoped_path — anything under src/, patterns/ and scripts/. Milestone
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
# No leading anchor (H-5). `*/src/secrev/*.py` needs a leading directory, so
# it matches only because the client happens to send absolute paths — true
# today, undocumented, and not something a control should rest on.
#
# The literal form H-5 gives also matches `foosrc/secrev/`, which is not this
# project. `src/secrev/*.py|*/src/secrev/*.py` would meet H-5's stated
# rationale without that, but H-5 states the mechanism verbatim and STACK.md
# wins on mechanism, so the deviation is raised in the ledger rather than
# taken here. The over-match refuses a write to a path this repository does
# not contain, which is the direction to err in.

is_self_application_path() {
    case "$1" in
      *src/secrev/*.py|*scripts/*.py) return 0 ;;
      *) return 1 ;;
    esac
}

is_scoped_path() {
    case "$1" in
      *src/secrev/*|*patterns/*|*scripts/*) return 0 ;;
      *) return 1 ;;
    esac
}
