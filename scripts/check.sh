#!/bin/sh
# The gate. One script, run identically by CI, by the git hooks, and by
# `/check`. If it passes locally it passes in CI — there is no second list.
#
# `--fast` runs a prefix of that same list: format, lint, types, harness
# guards, self-application, secrets, licences. It skips pytest, the determinism
# check and the dependency audit — the two slow stages and the one that needs a
# network. This is not a second list — it is a staged one, and nothing reaches a
# remote on the strength of it: `.githooks/pre-commit` uses --fast so committing
# stays cheap, `.githooks/pre-push` runs the whole thing, and CI runs the whole
# thing again. The alternative was a full gate on every commit, which is how
# people learn to type --no-verify.
#
# The dependency audit is out of --fast for a reason worth stating: a push has
# a network by definition, a commit does not, and a check that fails because
# the machine is offline teaches people to bypass the hook rather than to fix
# anything.
#
# `--sast` adds a CodeQL run over the Python source. It is opt-in rather than
# part of the gate because it takes minutes: a gate that costs minutes per push
# is a gate people route around, and CI runs CodeQL on every push regardless
# (.github/workflows/codeql.yml). ruff's bandit rules and scripts/self_check.py
# are the fast half of the same question and they do run every time.
#
# POSIX sh only (STACK.md §1). No bashisms, no GNU-only flags.
#
# Exit: 0 all gates pass · 1 a gate failed · 2 the environment is unusable.

set -eu
cd "$(dirname "$0")/.."

FAST=0
SAST=0
for arg in "$@"; do
    case "$arg" in
        --fast) FAST=1 ;;
        --sast) SAST=1 ;;
        -h|--help)
            echo "usage: check.sh [--fast] [--sast]"
            echo "  --fast  skip pytest, determinism and the dependency audit (pre-commit uses this)"
            echo "  --sast  additionally run CodeQL over src/ (minutes; CI runs it on every push)"
            exit 0
            ;;
        *) echo "check.sh: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

if [ "$FAST" = 1 ] && [ "$SAST" = 1 ]; then
    echo "check.sh: --fast and --sast contradict each other" >&2
    exit 2
fi

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
AUDIT_SETUP="python3 -m venv .venv-audit && .venv-audit/bin/pip install -r .github/requirements/audit.txt"
GITLEAKS_SETUP="see CLAUDE.md → Development environment (pinned tarball + sha256), or 'brew install gitleaks'"
missing() {
    printf '\n\033[31m── %s: not installed — cannot check\033[0m\n' "$1" >&2
    printf 'This is not a pass. Run: %s\n' "${2:-$SETUP}" >&2
    exit 2
}

# A gate implemented as a Python script, honouring the same three-way exit as
# this one: 0 pass, 1 finding, 2 could not check. The last is fatal here rather
# than a failure, because "the audit did not run" must not be recorded as "the
# audit found nothing" — the same distinction H-1 draws, one level down.
gate_script() {
    # `status=$?` after a bare `if` is not portable — the shell may have reset
    # it by then. Capture it in the `||` branch, where it is the command's own.
    status=0
    "$PY" "$@" || status=$?
    if [ "$status" = 2 ]; then
        exit 2
    fi
    [ "$status" = 0 ] || fail=1
    return 0
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
if [ "$FAST" = 1 ]; then
    skip "pytest" "--fast; pre-push and CI run it"
elif [ -d tests ]; then
    "$PY" -m pytest --version >/dev/null 2>&1 || missing pytest
    # pytest runs as a child of protected_snapshot.py, which snapshots every
    # protected path in its own memory before and after (owner decision,
    # 2026-09-22). This gate is auto-approved and pytest is code execution, so
    # a test is a write path no guard watches; a review showed one writing into
    # threat-models/. The baseline was a $(mktemp) file until a second review
    # showed a test could re-take it and turn the stage green over a change
    # still in the tree — so it is never written anywhere.
    # `-I -S` on the checker and neither on pytest: pytest needs the project
    # and the venv's packages, and the checker must not be reachable from
    # either. `-I` keeps a module planted in scripts/ from replacing the stdlib
    # it compares with; `-S` keeps a `.pth` planted in the venv's
    # site-packages from running inside it and forging the comparison. The
    # checker is stdlib-only, so neither flag costs it anything.
    printf '\n\033[1m── pytest\033[0m\n'
    gate_script -I -S scripts/protected_snapshot.py run -- "$PY" -m pytest
else
    skip "pytest" "no tests/ yet — nothing to run"
fi

# The harness guards used to run here, as stage 4. They do not any more.
#
# `.claude/` is the layer that *writes* this project; `src/` is the project.
# This gate answers "is the software correct", and a stage asserting that a
# PreToolUse hook still refuses a heredoc is not an answer to that question —
# it is the tooling checking itself inside the build of the thing it tooled.
# `.claude/check.sh` owns them now, with its own full stage list, and
# `.github/workflows/harness.yml` runs it separately.
#
# The two gates share no state and neither invokes the other. A contributor
# without Claude Code runs this one, and nothing about the harness can fail
# their build.

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

# ------------------------------------------------ 6. secrets (gitleaks)
# The one stage that answers a question about the repository rather than about
# the code: is a credential in here. It runs in --fast too, and that placement
# is the whole point — `gitleaks dir` reads the working tree, so a secret is
# caught at the commit that would have introduced it rather than after it is
# history, where removing it is a rewrite and the credential is burned anyway.
#
# What this does not cover, stated rather than discovered: existing history. A
# scan of every past commit belongs to the day this repository gets a remote,
# and it is `gitleaks git` — a different command, not a flag on this one.
#
# Configuration is .gitleaks.toml, which extends the default rule set rather
# than replacing it and scopes out tests/fixtures/ only (P3: the exemption is
# over a path, never over a rule).
printf '\n\033[1m── secrets (gitleaks)\033[0m\n'
# Resolved here rather than left to PATH. Git hooks inherit whatever PATH the
# caller had, and ~/.local/bin — where a release tarball unpacks — is on the
# login PATH of some machines and not others. A gate whose stages depend on
# shell profile configuration fails differently per machine for reasons that
# have nothing to do with the code, and under H-1 that failure is an exit 2
# every time someone commits. GITLEAKS_BIN overrides.
if [ -n "${GITLEAKS_BIN:-}" ]; then
    GITLEAKS=$GITLEAKS_BIN
elif have gitleaks; then
    GITLEAKS=gitleaks
elif [ -x "$HOME/.local/bin/gitleaks" ]; then
    GITLEAKS=$HOME/.local/bin/gitleaks
else
    missing gitleaks "$GITLEAKS_SETUP"
fi
gl_report=$(mktemp)
gl_log=$(mktemp)
if "$GITLEAKS" dir . --no-banner --redact --report-format json \
        --report-path "$gl_report" --exit-code 1 >"$gl_log" 2>&1; then
    echo "no leaks"
elif [ -s "$gl_report" ]; then
    cat "$gl_log"
    printf 'Findings are redacted here; the report is at %s\n' "$gl_report"
    fail=1
else
    # Non-zero and no report: gitleaks failed to run rather than found
    # something. Reading the exit code alone would report a broken scanner as a
    # clean scan — H-1, in the stage most likely to be trusted blindly.
    cat "$gl_log" >&2
    printf 'gitleaks produced no report — this is "cannot check", not "clean".\n' >&2
    rm -f "$gl_report" "$gl_log"
    exit 2
fi
rm -f "$gl_log"
[ "$fail" = 1 ] || rm -f "$gl_report"

# ------------------------------------------------ 7. licences (allowlist)
# Offline: it reads metadata already on disk, so it belongs in --fast next to
# the other cheap stages. STACK.md §2.2 holds the reasoning; the allowlist and
# its per-entry reasons are in scripts/license_check.py.
printf '\n\033[1m── licences (allowlist)\033[0m\n'
[ -x .venv-audit/bin/pip-licenses ] || missing pip-licenses "$AUDIT_SETUP"
gate_script scripts/license_check.py

# ------------------------------------------------ 8. determinism (NFR-3)
# Two runs of every generation script on the same input must be byte-identical.
# This is the hard requirement of M1; it is checked here rather than trusted.
#
# The condition is inventory.py, not the src/secrev directory. That directory
# appears with the *first* file, and if that file is cli.py this stage keeps
# printing "nothing to compare" while traversal order, NFC normalisation and
# id derivation are being written — the rules NFR-3 is actually made of, and
# the ones that cannot be corrected afterwards. determinism_check.py owns the
# same condition; the script decides, this only reports.
if [ "$FAST" = 1 ]; then
    skip "determinism (NFR-3)" "--fast; pre-push and CI run it"
else
    printf '\n\033[1m── determinism (NFR-3)\033[0m\n'
    if "$PY" scripts/determinism_check.py; then
        :
    else
        fail=1
    fi
fi

# ------------------------------------------- 9. dependency audit (CVE)
# Needs the network, so it is out of --fast: a push has one by definition, a
# commit does not. scripts/deps_audit.py distinguishes "no advisories" from
# "could not reach OSV" and exits 2 for the second, which is why it goes
# through gate_script rather than being folded into `fail`.
if [ "$FAST" = 1 ]; then
    skip "dependency audit (CVE)" "--fast; it needs the network — pre-push and CI run it"
else
    printf '\n\033[1m── dependency audit (CVE)\033[0m\n'
    [ -x .venv-audit/bin/pip-audit ] || missing pip-audit "$AUDIT_SETUP"
    gate_script scripts/deps_audit.py
fi

# ------------------------------------------------------- 10. SAST (CodeQL)
# Opt-in with --sast. Everything above runs in seconds; this runs in minutes,
# and a gate that costs minutes per push is a gate people learn to skip. CI
# runs CodeQL on every push regardless (.github/workflows/codeql.yml), so the
# check is not optional — only its position on the local critical path is.
#
# The local CLI is not installed by this repository and is not a dependency of
# it. Absent, --sast exits 2: an explicitly requested check that cannot run is
# the H-1 case, and it is worse here than elsewhere because the flag was typed
# deliberately.
if [ "$SAST" = 1 ]; then
    printf '\n\033[1m── SAST (CodeQL, python)\033[0m\n'
    # The bundle's top-level directory is `codeql/` and the CLI sits directly
    # inside it, so the documented `tar -xf <bundle> -C ~/.local/share/` puts it
    # here. The default used to be one `codeql/` deeper, which no documented
    # install produced: --sast only ever ran with CODEQL_BIN set by hand.
    CODEQL_BIN=${CODEQL_BIN:-$HOME/.local/share/codeql/codeql}
    if [ ! -x "$CODEQL_BIN" ]; then
        missing "codeql" "install the CodeQL CLI, or set CODEQL_BIN to its path"
    fi
    if [ "$HAS_SRC" = 1 ]; then
        gate_script scripts/codeql_check.py --codeql "$CODEQL_BIN"
    else
        echo "no src/secrev yet — nothing to analyse"
    fi
fi

printf '\n'
if [ "$fail" = 0 ]; then
    if [ "$FAST" = 1 ]; then
        printf '\033[32mfast gates pass\033[0m (pytest, determinism and the audit not run)\n'
    else
        printf '\033[32mall gates pass\033[0m\n'
    fi
    # Success marker, in the product's own space. It used to be written into
    # .claude/hooks/state/, which made this the one place the product gate
    # reached into the harness — a dependency pointing the wrong way. The
    # harness may read this file; nothing here writes into the harness.
    #
    # Advisory, guarded, never affects the exit status. CI writes it into a
    # throwaway runner and nothing reads it there.
    if [ "$FAST" = 0 ]; then
        : > .gate-passed 2>/dev/null || true
    fi
    exit 0
fi
printf '\033[31mgate failed\033[0m\n'
exit 1
