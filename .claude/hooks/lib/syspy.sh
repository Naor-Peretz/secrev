# The interpreter a hook starts — one definition, sourced by every hook that
# starts one (H-7). Pinned against `scripts/check.sh`'s copy by an assertion in
# `tests/harness/attack.py`, because two resolutions of the same question drift
# apart without either one looking wrong.
#
# **Why this is not `command -v python3`.** PATH is searched in order, and a
# developer PATH begins with directories the user owns: where this was measured,
# three sat ahead of `/usr/bin`, which is where `python3` actually was. None held
# one, so the lookup landed on a root-owned file — and a test creating
# `~/.cargo/bin/python3` would own every later hook invocation, which means every
# guard: `bash_guard.py` decides whether a write to a protected path is refused,
# and it decides it inside whatever interpreter this resolves to. Redirecting
# HOME for the test run does not help, because PATH carries absolute paths.
#
# So: fixed absolute candidates first, and the one chosen must not be writable by
# the user whose code is being reviewed. Writability rather than ownership,
# because the question is not who owns the file but whether the reviewed code can
# rewrite it — and running as root makes every answer "writable", which is why
# the second pass exists rather than a refusal.
#
# **Silent when it falls back, deliberately, and this is the one place the gate
# and the hooks differ.** `check.sh` prints the fact once per run. A hook runs on
# every tool call, so the same note would arrive dozens of times a session, and a
# guard that is mostly noise is a guard people switch off. The property is
# recorded in `BRIEF_M4.md` §6 instead.
#
# **It does not check that the interpreter can run the module.** A fixed path may
# be an older Python than PATH's — macOS ships 3.9 at `/usr/bin/python3` — and
# verifying it costs an extra interpreter start on every tool call. The answer is
# at the other end instead: a hook whose decider exits with anything outside the
# protocol treats that as "could not check" and refuses (H-1), so an interpreter
# that cannot run the guard produces a loud refusal rather than a silent permit.
# That mapping is the reason this file can afford to be cheap.

# Prints the interpreter, or nothing and a non-zero status. Separate from the
# refusal below because one hook must *not* refuse: `skill-activation.sh` is a
# router on UserPromptSubmit, and exiting 2 there would break every prompt in the
# session to report that a suggestion could not be made. H-1 is about quality
# gates; a router is not one.
syspy_find() {
    for _pass in unwritable any; do
        for _candidate in /usr/bin/python3 /bin/python3 $(command -v python3 2>/dev/null); do
            [ -x "$_candidate" ] || continue
            if [ "$_pass" = unwritable ] && [ -w "$_candidate" ]; then
                continue
            fi
            printf '%s' "$_candidate"
            return 0
        done
    done
    return 1
}

resolve_syspy() {
    SYSPY=$(syspy_find) || {
        echo "${1:-hook}: no python3 — cannot check (STACK.md §8 H-1)." >&2
        exit 2
    }
}

# The companion to the paragraph above: a decider's status, mapped so that
# anything the protocol does not define becomes a refusal.
#
# `bash_guard.py` returns 0 to permit and 2 to refuse. Every other value — a
# SyntaxError under too old an interpreter, an ImportError, a crash, a kill — came
# out as 1, and `PreToolUse` reads 1 as a non-blocking error, so the write went
# ahead. A guard that permits when it breaks is the H-1 collapse this harness was
# built to remove, and it was reachable by any means of breaking the guard.
syspy_status() {
    case "$1" in
      0|2) return "$1" ;;
      *)
        echo "${2:-hook}: the check exited $1, which the hook protocol gives no" >&2
        echo "meaning to — refusing rather than letting the call through (H-1, H-9)." >&2
        return 2
        ;;
    esac
}
