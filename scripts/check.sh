#!/bin/sh
# The gate. One script, run identically by CI, by the pre-commit hook, and by
# `/check`. If it passes locally it passes in CI — there is no second list.
#
# POSIX sh only (STACK.md §1). No bashisms, no GNU-only flags.
#
# Exit: 0 all gates pass · 1 a gate failed · 2 the environment is unusable.

set -eu
cd "$(dirname "$0")/.."

fail=0
have() { command -v "$1" >/dev/null 2>&1; }
run()  { printf '\n\033[1m── %s\033[0m\n' "$1"; shift; "$@" || fail=1; }
skip() { printf '\n\033[2m── %s (skipped: %s)\033[0m\n' "$1" "$2"; }

# Prefer the project venv, fall back to whatever is on PATH.
if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
elif have python3; then
    PY=python3
else
    echo "no python3 available" >&2
    exit 2
fi
runpy() { "$PY" -m "$@"; }

HAS_SRC=0
[ -d src/secrev ] && HAS_SRC=1

# A missing tool is not a passing tool (STACK.md §8 H-1). "Nothing to check
# yet" stays a legitimate skip; "cannot check" exits 2 naming what is absent.
#
# This script printed `skipped: not installed` for ruff, mypy and pytest and
# still reached `all gates pass` — with none of the three present, and with CI
# trusting the result. Two states, one word.
SETUP="python3 -m venv .venv && .venv/bin/pip install ruff pytest mypy"
missing() {
    printf '\n\033[31m── %s: not installed — cannot check\033[0m\n' "$1" >&2
    printf 'This is not a pass. Run: %s\n' "$SETUP" >&2
    exit 2
}

# ---------------------------------------------------------------- 1. format
"$PY" -m ruff --version >/dev/null 2>&1 || missing ruff
run "ruff format --check" runpy ruff format --check .
run "ruff check"          runpy ruff check .

# ------------------------------------------------------------------ 2. types
if [ "$HAS_SRC" = 1 ]; then
    "$PY" -m mypy --version >/dev/null 2>&1 || missing mypy
    run "mypy" runpy mypy
else
    skip "mypy" "no src/secrev yet — nothing to type-check"
fi

# ------------------------------------------------------------------ 3. tests
# `[ -d tests ] && pytest --version` collapsed "no tests yet" and "pytest is
# absent" into one branch with one message. Once tests/ existed the message
# was simply false — which is how it was noticed, printed in front of a
# tests/ directory it claimed did not exist.
if [ -d tests ]; then
    "$PY" -m pytest --version >/dev/null 2>&1 || missing pytest
    run "pytest" runpy pytest
else
    skip "pytest" "no tests/ yet — nothing to run"
fi

# ------------------------------------------- 4. harness guards (STACK.md §8)
# H-8: a guard nobody has tried to defeat is an assumption, not a control. The
# driver attempts the bypass against every guard and fails if one stops
# refusing. It is stdlib-only and runs on the system interpreter, so it works
# before .venv exists -- the guards are what stand between an agent and this
# repository, and gating their check on an environment that may be missing
# would be the H-1 mistake this stage exists to catch.
printf '\n\033[1m── harness guards (STACK.md §8 H-8)\033[0m\n'
if [ -f tests/harness/attack.py ]; then
    if guard_out=$("$PY" tests/harness/attack.py 2>&1); then
        printf '%s\n' "$guard_out" | tail -1
    else
        printf '%s\n' "$guard_out"
        fail=1
    fi
else
    echo "no tests/harness/attack.py — nothing to check"
fi

# ------------------------------------------- 5. self-application (STACK §2.1)
# Grep-shaped and deliberately crude. It is a backstop for the ruff bandit
# rules above, and it stays until `secrev sweep src/secrev/` can do the job
# properly (AC-10). Both must pass; neither replaces the other.
printf '\n\033[1m── self-application (STACK.md §2.1)\033[0m\n'
if [ "$HAS_SRC" = 1 ]; then
    if "$PY" scripts/self_check.py; then
        echo "clean"
    else
        fail=1
    fi
else
    echo "no src/secrev yet — nothing to check"
fi

# ------------------------------------------------ 6. determinism (NFR-3)
# Two runs of every generation script on the same input must be byte-identical.
# This is the hard requirement of M1; it is checked here rather than trusted.
printf '\n\033[1m── determinism (NFR-3)\033[0m\n'
if [ "$HAS_SRC" = 1 ] && [ -d tests/fixtures ]; then
    if "$PY" scripts/determinism_check.py; then
        echo "byte-identical across runs"
    else
        fail=1
    fi
else
    echo "no src/secrev + tests/fixtures yet — nothing to compare"
fi

printf '\n'
if [ "$fail" = 0 ]; then
    printf '\033[32mall gates pass\033[0m\n'
    # Success marker, read by .claude/hooks/session-end.sh to tell "verified"
    # from "not yet run". This is the one place the gate touches the harness;
    # it is advisory, guarded, and never affects the exit status. CI writes it
    # into a throwaway runner and nothing reads it there.
    if [ -d .claude/hooks ]; then
        mkdir -p .claude/hooks/state 2>/dev/null || true
        : > .claude/hooks/state/gate-passed 2>/dev/null || true
    fi
    exit 0
fi
printf '\033[31mgate failed\033[0m\n'
exit 1
