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
# So: fixed absolute candidates first, and the one chosen must not be
# *replaceable* by the user whose code is being reviewed — see
# `syspy_replaceable`, which is a different and stronger question than "is the
# file writable". Replaceability rather than ownership, because the question is
# not who owns the file but whether the reviewed code can make the path run
# something else — and running as root makes every answer "replaceable", which is
# why the second pass exists rather than a refusal.
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
# With `major minor`, a candidate must also report at least that version. That
# costs one interpreter start per candidate, so the hooks ask for no floor and
# pay nothing: they run on every tool call, and their modules are plain enough to
# run under an old Python — CI proved it, with every hook working under macOS's
# 3.9 at `/usr/bin/python3`. The harness *gate* asks for a floor, because
# `tests/harness/attack.py` uses `sys.stdlib_module_names` (3.10) and because
# Apple's interpreter sets a bytecode cache prefix that moves `__pycache__` out
# of the tree, which the planted-`.pyc` assertion is specifically about. The gate
# runs once; a process start there is free.
#
# Without the floor this would have been the worst kind of wrong: the status
# mapping below turns an interpreter that cannot run a guard into a refusal, so
# every Bash command on such a machine would be refused by a guard that never
# ran. Correctness first, then the property.
# Could the current user make this path run a different program? Status 0 means
# yes — the candidate is rejected by the first pass.
#
# **`[ -w "$candidate" ]` was the wrong question, and it answered "safe" for a
# path the user could replace in one command.** Two holes, both measured:
# replacing a file needs write permission on its *directory*, not on the file —
# delete the entry, create another — and `-w` follows symlinks, so on a link it
# reports about the target and says nothing about the link. A `python3` symlink in
# a user-owned directory pointing at a root-owned interpreter passed as
# unwritable, was chosen in the first pass, and the gate printed no note: it
# claimed the property while the path could be repointed with `ln -sf`. That is
# not hypothetical on macOS, where Apple's 3.9 cannot meet the gate's floor so the
# chosen candidate always comes from PATH — and `/usr/local/bin` is user-owned
# under Homebrew, `~/.local/bin` by construction.
#
# So: the file, every ancestor directory of it, and the same for each hop of a
# symlink chain. `readlink` without `-f`, because `-f` is GNU and this has to run
# on macOS; ancestors are walked with parameter expansion rather than `dirname`,
# so the whole check costs one fork per symlink hop and none at all for a plain
# file. The hooks still pay nothing they did not pay before.
#
# Unknown is treated as replaceable: if `readlink` is absent or fails, or a chain
# is absurdly long, the answer is "assume it can be replaced", which costs a note
# and never a false claim.
#
# **One case this does not cover, chosen deliberately and written here so the gap
# is not read as coverage.** The hop loop resolves a symlink that is the *final*
# component. It does not resolve a symlink that is an *ancestor*: walking
# `/opt/tool/bin/python3` tests `/opt/tool/bin`, `/opt/tool`, `/opt` and `/`, and
# if `/opt/tool` is a link to `/srv/a/b` then every one of those tests follows the
# link and answers about the target, never reaching `/srv/a` — which the user
# might own. It is the same mechanism as the bug this function exists to fix
# (`-w` answering about the target), one level out.
#
# Not fixed, for two reasons rather than one. The configuration cannot be *created*
# by the code under review: planting it needs a symlink inside a directory the
# reviewed code cannot write, so it has to pre-exist on the machine — unlike the
# cases above, which a test creates in one command. And a component-by-component
# canonicaliser in `sh` is the kind of code whose bugs are silent in the direction
# that matters, in the one function every guard's integrity rests on, and it could
# not be tested here: isolating the case needs a symlink in a root-owned directory,
# which an unprivileged test cannot make. On the standard systems this would apply
# to, the targets are root-owned anyway — merged-`/usr` on Linux, `/private` on
# macOS.
syspy_replaceable() {
    _path=$1
    _hops=0
    while :; do
        if [ -w "$_path" ] || [ -O "$_path" ]; then
            return 0
        fi
        # A directory you can write is a directory whose entries you can delete
        # and recreate — including one that is itself a directory on the way.
        #
        # **`-O` beside `-w`, and the owner's second correction.** Permission is
        # not the capability: a directory the user owns at mode 0555 answers "no"
        # to `-w`, and its owner reaches it with one `chmod u+w`. Measured — the
        # file was replaced after exactly that. Ownership *is* write access to
        # anyone who can run `chmod`, which is precisely what the reviewed code
        # can do. `-O` is a builtin in dash and in BSD `test`, so this still
        # costs no process.
        _walk=$_path
        while [ -n "$_walk" ] && [ "$_walk" != "/" ]; do
            _parent=${_walk%/*}
            if [ -z "$_parent" ]; then
                _parent=/
            fi
            if [ -w "$_parent" ] || [ -O "$_parent" ]; then
                return 0
            fi
            _walk=$_parent
        done
        if [ ! -L "$_path" ]; then
            return 1
        fi
        _target=$(readlink "$_path" 2>/dev/null) || return 0
        case "$_target" in
          /*) _path=$_target ;;
          *)  _path=${_path%/*}/$_target ;;
        esac
        _hops=$((_hops + 1))
        if [ "$_hops" -gt 8 ]; then
            return 0
        fi
    done
}

syspy_find() {
    _min_major=${1:-0}
    _min_minor=${2:-0}
    for _pass in unreplaceable any; do
        for _candidate in /usr/bin/python3 /bin/python3 $(command -v python3 2>/dev/null); do
            [ -x "$_candidate" ] || continue
            if [ "$_pass" = unreplaceable ] && syspy_replaceable "$_candidate"; then
                continue
            fi
            if [ "$_min_major" != 0 ]; then
                "$_candidate" -I -S -c \
                    "import sys; sys.exit(0 if sys.version_info >= ($_min_major, $_min_minor) else 1)" \
                    2>/dev/null || continue
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
