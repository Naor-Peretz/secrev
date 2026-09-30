# Configuration-driven code execution, turned off for the git calls the hooks
# make — STACK.md §8. One definition, sourced by every hook that shells to git
# (H-7), and pinned equal to `commit_review.GIT_DISARMED` by an assertion in
# `tests/harness/attack.py`, because two lists of the same mechanisms drift
# apart without either one looking wrong.
#
# **Why this file exists.** The fourth review of M4 demonstrated three git
# configuration keys executing a command from inside a hook, and the fix went
# into `commit_review.py`, which runs `git diff`. A fifth review then measured
# `core.fsmonitor` still firing on `git status --porcelain` — the trigger the
# brief had *named* — in `session-start.sh` and `session-end.sh`. Those two run
# on SessionStart and on Stop: more often than the commit checkpoint, and
# `session-start.sh` runs before the owner has read anything. The fix had been
# applied to the file where the finding was demonstrated rather than to the
# hooks that make the call, which is this milestone's whole pattern.
#
# This disarms **our** calls. It does not make a planted key harmless — the
# owner's own `git add` still runs a clean filter, which is why
# `protected_snapshot.py` watches `.git/` and why the class stays open until
# the test run is confined (HARNESS-FS). Nor is it an allowlist: naming
# mechanisms is a denylist and git adds more of them. It is the narrow half
# that is free.
#
# `filter.<driver>.clean` and the other name-arbitrary families are *not* here,
# and cannot be: no fixed list of options reaches a driver whose name the
# target chooses. `commit_review.py` handles those by asking git which keys are
# actually configured and blanking each one through `GIT_CONFIG_COUNT`. These
# hooks do not read worktree content — `git status --porcelain` runs no clean
# filter — so the fixed keys are the whole exposure here. A hook that starts
# diffing content needs that mechanism, not another entry below.

# Run git with the keys that execute a command turned off.
#
# A function rather than a variable, because `$GIT_FLAGS git status` re-splits
# on whitespace and an empty or unset variable silently becomes a bare `git` —
# the same "it looked like it was applied" failure one layer down.
git_ro() {
    git -c core.fsmonitor=false \
        -c core.hooksPath=/dev/null \
        -c protocol.ext.allow=never \
        -c diff.external= \
        "$@"
}
