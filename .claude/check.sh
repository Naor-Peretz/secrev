#!/bin/sh
# The harness gate. Separate from scripts/check.sh, and it does not call it.
#
# `.claude/` is the layer that *writes* this project; `src/` is the project.
# The product gate answers "is the software correct". A stage asserting that a
# PreToolUse hook still refuses a heredoc is not an answer to that question, so
# it does not belong there — it is the tooling checking itself inside the build
# of the thing it tooled. It lived there until now, which also meant a
# contributor without Claude Code could have their build fail on a layer they
# never run.
#
# The two gates share no state and neither invokes the other. This one may
# *read* the product's `.gate-passed` marker; nothing here writes into `src/`,
# `tests/` (beyond `tests/harness/`), `scripts/` or `patterns/`, and nothing
# there writes into `.claude/`.
#
# Same stage list as any serious pipeline, applied to the harness: format,
# lint, types, tests, secrets. Two stages are absent for a stated reason rather
# than by omission — see the end.
#
# POSIX sh only (STACK.md §1).
#
# Exit: 0 all stages pass · 1 a stage failed · 2 the environment is unusable.

set -eu
cd "$(dirname "$0")/.."

CONFIG=.claude/ruff.toml
PATHS=".claude/hooks .claude/skills tests/harness"

fail=0
have() { command -v "$1" >/dev/null 2>&1; }
run()  { printf '\n\033[1m── %s\033[0m\n' "$1"; shift; "$@" || fail=1; }

# Tools come from the project venv when it exists. That is a convenience, not a
# coupling: the guard assertions below are stdlib-only and run on an interpreter
# of their own, so the stage that actually protects this repository never
# depends on an environment being built first. A second venv to lint four files
# would be cost without benefit, and this sentence is here so that stays a
# decision rather than becoming an oversight.
#
# **That sentence was false until M4's sixth review.** It said the assertions ran
# on the system interpreter; they ran under `$PY`, which is `.venv/bin/python` —
# writable by the test suite and watched by nothing. A test overwriting it owned
# the stage that prints "all N guard assertions hold". `$GUARD_PY` is now
# resolved by `lib/syspy.sh`, the same resolution every hook uses: fixed absolute
# candidates ahead of PATH, and the chosen one not replaceable by the user whose
# code is under review.
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
elif have python3; then
    PY=python3
else
    echo "no python3 available" >&2
    exit 2
fi

SYSPY_LIB="$(dirname "$0")/hooks/lib/syspy.sh"
[ -f "$SYSPY_LIB" ] || {
    echo "harness gate: $SYSPY_LIB is missing — cannot check (H-1)." >&2
    exit 2
}
. "$SYSPY_LIB"
# With a floor, unlike the hooks: the driver uses `sys.stdlib_module_names`
# (3.10), and macOS's `/usr/bin/python3` is 3.9 — unreplaceable, and unable to run
# the assertions. CI found that by going red on exactly the two assertions that
# depend on a newer interpreter, which is the right way round: an interpreter
# that cannot run the check must not be chosen *for* the check, and the floor is
# what keeps the security property from costing correctness.
GUARD_PY=$(syspy_find 3 11) || {
    echo "harness gate: no python3 ≥ 3.11 — cannot run the guard assertions (H-1)." >&2
    exit 2
}
# `syspy_replaceable`, not `[ -w ]`: a link in a directory this user owns is
# replaceable without any write permission on the interpreter it points at, and
# the note is the whole value of this line.
if syspy_replaceable "$GUARD_PY"; then
    printf 'note: %s can be replaced by this user, so the guard assertions run\n' \
        "$GUARD_PY" >&2
    printf '      under an interpreter the reviewed code could have replaced.\n' >&2
fi

missing() {
    printf '\n\033[31m── %s: not installed — cannot check\033[0m\n' "$1" >&2
    printf 'This is not a pass (STACK.md §8 H-1).\n' >&2
    exit 2
}

# ------------------------------------------------------- 1. format · 2. lint
"$PY" -m ruff --version >/dev/null 2>&1 || missing ruff
# shellcheck disable=SC2086
run "ruff format --check (harness)" "$PY" -m ruff format --check --config "$CONFIG" $PATHS
# shellcheck disable=SC2086
run "ruff check (harness)"          "$PY" -m ruff check --config "$CONFIG" $PATHS

# ------------------------------------------------------------------ 3. types
"$PY" -m mypy --version >/dev/null 2>&1 || missing mypy
# Every hook module by glob, not by name. It named two modules until M4, and a
# third — commit_review.py — passed the gate unchecked while mypy printed the
# same "4 source files" it had printed before the file existed. A count that
# does not move when a module is added is a list someone has to remember.
# shellcheck disable=SC2086
run "mypy --strict (harness)" "$PY" -m mypy --strict --ignore-missing-imports \
    .claude/hooks/lib .claude/hooks/*.py

# ------------------------------------------------------------------ 4. tests
# H-8: a guard nobody has tried to defeat is an assumption, not a control. The
# driver attempts the bypass against every guard and fails if one stops
# refusing. Stdlib-only, so it runs on an interpreter resolved for the purpose
# rather than on the venv's: the guards are what stand between an agent and this
# repository, gating their check on an environment that may be missing is the H-1
# mistake this stage exists to catch — and running it under an interpreter the
# reviewed code can overwrite is the same mistake with the answer forged instead
# of absent.
printf '\n\033[1m── guard assertions (STACK.md §8 H-8)\033[0m\n'
if [ -f tests/harness/attack.py ]; then
    if guard_out=$("$GUARD_PY" tests/harness/attack.py 2>&1); then
        printf '%s\n' "$guard_out" | tail -1
    else
        printf '%s\n' "$guard_out"
        fail=1
    fi
else
    echo "no tests/harness/attack.py — nothing to check" >&2
    exit 2
fi

# ---------------------------------------------------------------- 5. secrets
# The harness holds permission rules, deny lists and absolute home paths in
# settings.local.json — which is gitignored precisely because it holds them.
# Scanning is how that stays true rather than remaining an intention.
printf '\n\033[1m── secrets (gitleaks, harness)\033[0m\n'
if [ -x .venv-audit/bin/gitleaks ]; then
    GITLEAKS=.venv-audit/bin/gitleaks
elif have gitleaks; then
    GITLEAKS=gitleaks
elif [ -x "$HOME/.local/bin/gitleaks" ]; then
    GITLEAKS=$HOME/.local/bin/gitleaks
else
    missing gitleaks
fi
if "$GITLEAKS" dir .claude tests/harness --no-banner --redact 2>&1; then
    echo "clean"
else
    fail=1
fi

# ---------------------------------------------------------------- not staged
#
# Named rather than omitted, because a stage that is silently absent and a
# stage that has nothing to check read identically from outside (H-1).
#
#   dependency audit  — the harness imports json, sys, re, shlex, hashlib,
#                       unicodedata, pathlib, subprocess, tempfile, shutil.
#                       Stdlib only. There is no dependency to audit, and that
#                       is a property worth keeping: a third-party import here
#                       would put a package on the critical path of every
#                       prompt in every session.
#   licence check     — same reason. No dependency, no licence.
#   SAST              — CodeQL runs over the whole repository in CI
#                       (.github/workflows/codeql.yml), which already includes
#                       .claude/. A second scan of four files would duplicate
#                       it without adding coverage.

printf '\n'
if [ "$fail" = 0 ]; then
    printf '\033[32mharness gates pass\033[0m\n'
    mkdir -p .claude/hooks/state 2>/dev/null || true
    : > .claude/hooks/state/harness-passed 2>/dev/null || true
    exit 0
fi
printf '\033[31mharness gate failed\033[0m\n'
exit 1
