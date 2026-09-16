#!/usr/bin/env python3
"""Attack driver for the .claude/ guards — H-8 as a standing control.

STACK.md §8 H-8: "Guards are verified by attempting the bypass. After any guard
change, deliberately try the thing it should block. A guard nobody has tried to
defeat is an assumption, not a control." This turns that from a one-time
observation into something that fails when it stops being true.

Stdlib only, and runnable as `python3 tests/harness/attack.py` with no venv:
the harness it tests is what stands between an agent and this repository, and
requiring an environment that does not exist yet (BRIEF_M0.md §2) to check it
would be its own H-1 violation.

The `test_*` functions are collectable by pytest once .venv exists (TASK-005).
They take no fixtures and assert plain booleans, so both entry points agree.

Self-application (STACK.md §2.1): subprocess is called with argument lists only,
never a shell string. The strings below that look like violations -- `eval(`,
`yaml.load` -- are payloads fed to the guards on stdin. They are never executed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
HOOKS = REPO / ".claude" / "hooks"

# Exit codes the PreToolUse protocol assigns meaning to.
# Absolute, not a PATH lookup: the guards under test are what stands between
# an agent and this repository, and resolving their interpreter through an
# environment variable is a dependency the test does not need. /bin/sh exists
# on both supported platforms (STACK.md §4).
SH = "/bin/sh"

PASS_THROUGH = 0  # guard had no opinion, or returned an `ask` payload on stdout
BLOCK = 2  # guard refused; stderr reaches the agent


# --------------------------------------------------------------------- driver


def run_hook(
    hook: str, payload: dict[str, object], project_dir: Path | None = None
) -> tuple[int, str, str]:
    """Feed one hook a PreToolUse/PostToolUse JSON body on stdin.

    Argument list, never a shell string (STACK.md §2.1). The hooks resolve
    their own paths from CLAUDE_PROJECT_DIR, so pointing that at a temporary
    tree is how a test varies MILESTONE without mutating the repository.
    """
    root = project_dir if project_dir is not None else REPO
    proc = subprocess.run(
        [SH, str(HOOKS / hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(root)},
        cwd=str(root),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_payload(path: str, body: str) -> dict[str, object]:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": body}}


def asks(stdout: str) -> bool:
    """True when the guard returned a PreToolUse `ask` decision."""
    if not stdout.strip():
        return False
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    hook_out = parsed.get("hookSpecificOutput", {})
    return bool(hook_out.get("permissionDecision") == "ask")


def invokes_jq(script: Path) -> bool:
    """True when a shell script actually calls jq, ignoring prose about it.

    Comments explaining why jq was removed are not calls. Checking the raw text
    would make the removal untestable in any hook that documents it.
    """
    for line in script.read_text(encoding="utf-8").splitlines():
        code = line.split("#", 1)[0]
        if re.search(r"\bjq\b", code):
            return True
    return False


def milestone_tree(value: str | None) -> tempfile.TemporaryDirectory[str]:
    """A throwaway project dir with a different MILESTONE, used to vary it
    without mutating the repository.

    It carries hooks/lib/ as well as the MILESTONE file. A tree holding only
    the marker is not a checkout: the guards refuse when their reader is
    absent (H-1), so a bare fixture measures the missing reader rather than
    the milestone it was built to test.
    """
    tmp = tempfile.TemporaryDirectory()
    claude = Path(tmp.name) / ".claude"
    claude.mkdir(parents=True)
    if value is not None:
        (claude / "MILESTONE").write_text(value + "\n", encoding="utf-8")
    # The whole lib/, not a file-type guess: an earlier version copied *.py and
    # missed paths.sh the moment it was added, and the guards then refused for
    # want of it rather than for the milestone under test.
    shutil.copytree(HOOKS / "lib", claude / "hooks" / "lib")
    return tmp


# ------------------------------------------------------- self-application-guard

ABS_SRC = str(REPO / "src" / "secrev" / "cli.py")


def test_self_application_blocks_eval() -> None:
    rc, _, err = run_hook("self-application-guard.sh", write_payload(ABS_SRC, "x = eval('1')\n"))
    assert rc == BLOCK, f"eval into src/secrev must be refused, got rc={rc}"
    assert "eval(" in err, "the refusal must name the construct it caught"


def test_self_application_blocks_yaml_load() -> None:
    rc, _, err = run_hook(
        "self-application-guard.sh",
        write_payload(ABS_SRC, "cfg = yaml.load(fh)\n"),
    )
    assert rc == BLOCK, f"yaml.load into src/secrev must be refused, got rc={rc}"
    assert "safe_load" in err, "the refusal must point at the sanctioned call"


def test_self_application_permits_clean_source() -> None:
    """The negative fixture. A guard that refuses everything is not a guard."""
    rc, _, _ = run_hook(
        "self-application-guard.sh",
        write_payload(ABS_SRC, "def sweep(root: Path) -> None:\n    return None\n"),
    )
    assert rc == PASS_THROUGH, f"clean source must pass, got rc={rc}"


def test_self_application_uses_no_jq() -> None:
    """STACK.md §2 removed jq: a non-Python external dependency, undeclared, in
    a repository that requires a written reason for every dependency."""
    assert not invokes_jq(HOOKS / "self-application-guard.sh"), (
        "self-application-guard.sh still shells out to jq"
    )


def test_self_application_refuses_malformed_payload() -> None:
    """H-1: a check that cannot run exits 2, never 0.

    With jq this exited 5 -- jq's parse-error code leaking through `set -e`.
    The PreToolUse protocol assigns meaning to 0 and 2; 5 is undefined, so the
    guard's answer to a payload it could not read was not an answer at all.
    """
    proc = subprocess.run(
        [SH, str(HOOKS / "self-application-guard.sh")],
        input="{not json at all",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == BLOCK, f"malformed payload must refuse, got rc={proc.returncode}"


# ------------------------------------------------------------------ scope-guard


def test_scope_guard_asks_on_severity() -> None:
    # The milestone is named, not inherited from .claude/MILESTONE. Reading it
    # from the repo made these assertions change meaning when the marker moved.
    rc, out = scope_at("M1", "src/secrev/sweep.py", "severity = 'high'\n")
    assert rc == PASS_THROUGH, f"scope-guard asks, never blocks, got rc={rc}"
    assert asks(out), "assigning a severity in M1 must reach the human"


def test_scope_guard_permits_in_scope_write() -> None:
    rc, out = scope_at("M1", "src/secrev/sweep.py", "line_no = idx + 1\n")
    assert rc == PASS_THROUGH and not asks(out), "in-scope M1 work must not prompt"


def test_scope_guard_ignores_paths_outside_its_remit() -> None:
    rc, out, _ = run_hook(
        "scope-guard.sh", write_payload(str(REPO / "README.md"), "severity = 'high'\n")
    )
    assert rc == PASS_THROUGH and not asks(out), "scope-guard owns src/ and patterns/"


# ------------------------------------------------------------------- spec-guard


def test_spec_guard_asks_on_stack_edit() -> None:
    rc, out, _ = run_hook(
        "spec-guard.sh", write_payload(str(REPO / "STACK.md"), "## 10. New section\n")
    )
    assert rc == PASS_THROUGH, f"spec-guard asks, never blocks, got rc={rc}"
    assert asks(out), "an edit to a binding document is a decision, not a write"


def test_spec_guard_ignores_ordinary_files() -> None:
    rc, out, _ = run_hook("spec-guard.sh", write_payload(str(REPO / "CLAUDE.md"), "# notes\n"))
    assert rc == PASS_THROUGH and not asks(out), "CLAUDE.md is not one of the three"


# ------------------------------------------------------------ determinism-guard


def test_determinism_guard_speaks_on_nfr3_file() -> None:
    rc, out, _ = run_hook(
        "determinism-guard.sh", write_payload(str(REPO / "src" / "secrev" / "ids.py"), "")
    )
    assert rc == PASS_THROUGH, (
        f"got rc={rc}. Since inventory.py exists this hook re-runs the determinism "
        f"check, so rc=2 here means NFR-3 is currently broken — read the determinism "
        f"stage of the gate, not this assertion. It is not 'the guard blocked wrongly'."
    )
    assert "NFR-3" in out, "touching ids.py must restate the determinism rules"


def test_determinism_guard_silent_elsewhere() -> None:
    rc, out, _ = run_hook(
        "determinism-guard.sh", write_payload(str(REPO / "src" / "secrev" / "cli.py"), "")
    )
    assert rc == PASS_THROUGH and not out.strip(), "cli.py owns no NFR-3 rule"


def test_determinism_guard_speaks_on_surfaces_before_it_exists() -> None:
    """TASK-M2-001. `surfaces.py` derives ids into the same ledger as `sweep.py`,
    so it owns an NFR-3 rule from its first line. The guard has to be watching
    before that line is written: a check that starts after the first write has
    already missed the one that decided the ids.
    """
    rc, out, _ = run_hook(
        "determinism-guard.sh", write_payload(str(REPO / "src" / "secrev" / "surfaces.py"), "")
    )
    assert rc == PASS_THROUGH, (
        f"got rc={rc}. rc=2 means the determinism check it re-ran failed — read the "
        f"determinism stage of the gate, not this assertion."
    )
    assert "surfaces.py" in out and "NFR-3" in out, (
        "touching surfaces.py must restate the determinism rules — is_nfr3_path "
        "in .claude/hooks/lib/paths.sh does not name it"
    )


# ----------------------------------------------------------------- plan-review


def test_plan_review_fires_on_exit_plan_mode() -> None:
    rc, out, _ = run_hook("plan-review.sh", {"tool_name": "ExitPlanMode"})
    assert rc == PASS_THROUGH and "plan-review-workflow" in out


def test_plan_review_silent_on_other_tools() -> None:
    rc, out, _ = run_hook("plan-review.sh", {"tool_name": "Write"})
    assert rc == PASS_THROUGH and not out.strip()


# ------------------------------------------------------------------ bash-guard
#
# BRIEF_M0.md §1, the highest-severity item: guards hook Write|Edit|MultiEdit,
# so a write through Bash bypasses all of them. H-2 requires an allowlist --
# `tee`, heredocs, `sed -i`, `>`, `cp`, `mv`, `python3 -c`, `dd` is not a
# closeable list, and reaching for another verb is the signal that the polarity
# is wrong.


def bash(command: str) -> int:
    rc, _, _ = run_hook("bash-guard.sh", {"tool_name": "Bash", "tool_input": {"command": command}})
    return rc


def test_the_refusal_names_the_token_that_matched() -> None:
    """The trigger is a test over spellings, so a bare word equal to a
    protected name is refused like a path — the subcommand `secrev surfaces`
    and the branch `m2/surfaces` both are. Naming the token lets a reader tell
    that case from a real write. Narrowing the rule instead would admit
    `rm -rf src`, which the assertion below holds."""
    rc, _, err = run_hook(
        "bash-guard.sh",
        {"tool_name": "Bash", "tool_input": {"command": "python3 -m secrev surfaces /tmp/x"}},
    )
    assert rc == BLOCK
    assert "surfaces" in err
    assert "false positive" in err


def test_a_bare_protected_directory_is_still_refused() -> None:
    """What the trailing `$` in the trigger buys, and why requiring a `/`
    would be a regression rather than a fix."""
    assert bash("rm -rf src") == BLOCK
    assert bash("mv surfaces old") == BLOCK


def test_the_guard_still_records_what_it_cannot_do() -> None:
    """The KNOWN LIMIT section is the honest half of a spelling test: a glob,
    a variable or a `cd` defeats it. STACK.md §8 H-2 now says the same
    outwards. Deleting the section would leave the claim looking stronger than
    the mechanism, which is the H-1 shape applied to documentation."""
    source = (HOOKS / "bash_guard.py").read_text(encoding="utf-8")
    assert "KNOWN LIMIT" in source


def test_bash_refuses_heredoc_write() -> None:
    """The brief's own verification: 'Attempt to modify src/secrev/cli.py via
    heredoc. It must be refused.'

    A rule phrased as 'every command segment must be read-only' permits this,
    because `cat` is read-only and the write is done by the redirection.
    """
    assert bash("cat > src/secrev/cli.py <<'EOF'\nx = 1\nEOF") == BLOCK


def test_bash_permits_reading_the_same_path() -> None:
    """The negative fixture. A guard that refuses everything is not a guard."""
    assert bash("cat src/secrev/cli.py") == PASS_THROUGH


def test_bash_refuses_truncating_redirect() -> None:
    assert bash("echo x > src/secrev/cli.py") == BLOCK


def test_bash_permits_the_documented_gate_invocations() -> None:
    """`--fast` and `--sast` are what CLAUDE.md documents and the git hooks run,
    and the guard refused both: the execute rule rejected a dash-token in *any*
    position, not only before the script.

    A guard that forbids the project's own documented workflow does not stop
    the workflow. It moves it somewhere the guard cannot see, and every other
    refusal in that file loses credibility with it. That cost does not appear
    as a failure anywhere, which is why it survived until someone tried to run
    the SAST stage.
    """
    assert bash("sh scripts/check.sh") == PASS_THROUGH
    assert bash("sh scripts/check.sh --fast") == PASS_THROUGH
    assert bash("sh scripts/check.sh --sast") == PASS_THROUGH
    assert bash("python3 scripts/codeql_check.py --codeql /opt/codeql/codeql") == PASS_THROUGH


def test_bash_still_refuses_an_interpreter_flag_before_the_script() -> None:
    """The property the old rule was protecting, kept exactly.

    `-c` makes the interpreter evaluate a string, and both spellings are writes
    wearing an interpreter's name. The flag has to come *before* the script for
    that to work, so checking only the first argument loses nothing — there is
    no later position that turns an interpreter into an evaluator.
    """
    assert bash("python3 -c \"open('src/secrev/pwn.py','w').write('x')\"") == BLOCK
    assert bash("sh -c 'echo x > src/secrev/pwn.py'") == BLOCK
    assert bash("python3 -m http.server --directory src/secrev") == BLOCK


def test_bash_refuses_appending_redirect() -> None:
    assert bash("echo x >> scripts/check.sh") == BLOCK


def test_bash_refuses_clobber_redirect() -> None:
    """`>|` is why the operator set is not enumerated: miss one and an
    allowlisted command carries the write straight through."""
    assert bash("echo x >| src/secrev/cli.py") == BLOCK


def test_bash_refuses_sed_in_place() -> None:
    assert bash("sed -i 's/a/b/' src/secrev/cli.py") == BLOCK


def test_bash_refuses_tee() -> None:
    assert bash("echo x | tee src/secrev/cli.py") == BLOCK


def test_bash_refuses_writing_the_surface_kinds() -> None:
    """H-4 as amended in M2. The kinds decide which entry points enter the
    ledger at all, so an unreviewed edit narrows the review with nothing
    reporting it — the same reason `patterns/` is protected."""
    assert bash("echo x | tee surfaces/_surfaces.yaml") == BLOCK


def test_bash_permits_reading_the_surface_kinds() -> None:
    assert bash("cat surfaces/_surfaces.yaml") == PASS_THROUGH


def test_bash_does_not_protect_a_file_merely_named_surfaces() -> None:
    """The negative. `surfaces` is protected as a directory, not as a word:
    `src/secrev/surfaces.py` must not read as the data directory, and neither
    must an unrelated `surfaces.txt`."""
    assert bash("echo x > build/surfaces.txt") == PASS_THROUGH


def test_bash_refuses_python_dash_c() -> None:
    assert bash("python3 -c \"open('scripts/check.sh','w')\"") == BLOCK


def test_bash_refuses_cd_into_a_protected_tree() -> None:
    """No special case for `cd`. It is refused because it is not read-only,
    which is the same reason `pushd`, `git -C`, `env -C` and `make -C` are --
    an open set that never needed enumerating."""
    assert bash("cd src/secrev && sed -i 's/a/b/' cli.py") == BLOCK


def test_bash_refuses_command_substitution() -> None:
    """Substitution defeats the guard's ability to establish what runs."""
    assert bash("cat $(ls src/secrev/cli.py)") == BLOCK


def test_bash_refuses_unparseable_command() -> None:
    """H-1: a check that cannot run exits 2, never 0."""
    assert bash("cat 'src/secrev/cli.py") == BLOCK


def test_bash_refuses_a_read_only_pipeline() -> None:
    """The cost of the operator ban, asserted rather than discovered.

    This used to pass: every segment was read-only, so the safe-separator
    design permitted it. It is refused now, and that is the price of closing
    the chain below. Reading a protected file takes one command, or the Read
    tool.
    """
    assert bash("cat src/secrev/cli.py | grep -n eval | head -5") == BLOCK


# ------------------------------------------------------- execute, and the chain
#
# Running a script in scripts/ is not writing it, and the brief's allowlist has
# two categories where three are needed. The category is safe only alongside
# the operator ban: with chaining permitted, an allowlisted first command
# carries any write that follows it.


def test_bash_permits_running_the_gate() -> None:
    assert bash("sh scripts/check.sh") == PASS_THROUGH


def test_bash_permits_running_a_python_script() -> None:
    assert bash("python3 scripts/self_check.py") == PASS_THROUGH


def test_bash_permits_an_absolute_script_path() -> None:
    assert bash(f"sh {REPO}/scripts/check.sh") == PASS_THROUGH


def test_bash_refuses_the_chained_write() -> None:
    """The case that makes the operator ban mandatory rather than tidy.

    `sh scripts/check.sh` is permitted, the command mentions a protected path,
    and without the ban a segment-by-segment rule would have to catch the write
    in the *second* segment. It does — but only because that segment happens to
    contain a redirect. `sh scripts/check.sh; rm -rf src/` has no redirect at
    all, and the ban is what refuses both without depending on which.
    """
    assert bash("sh scripts/check.sh; cat > src/secrev/x.py") == BLOCK
    assert bash("sh scripts/check.sh; rm -rf src/") == BLOCK
    assert bash("sh scripts/check.sh && rm -rf src/secrev") == BLOCK
    assert bash("sh scripts/check.sh\nrm -rf src/") == BLOCK


def test_bash_refuses_a_flag_after_the_interpreter() -> None:
    """`-c` is why the execute category is a shape and not a name."""
    assert bash("python3 -c \"open('scripts/check.sh','w')\"") == BLOCK
    assert bash("sh -c 'echo x > scripts/check.sh'") == BLOCK


def test_bash_refuses_bash_as_an_interpreter() -> None:
    """STACK.md §1: POSIX sh, never bash. The execute category is not a place
    to quietly readmit it."""
    assert bash("bash scripts/check.sh") == BLOCK


def test_bash_refuses_an_interpreter_extension_mismatch() -> None:
    """`sh scripts/check.py` is not running a shell script; it is something
    else, and the guard should not have to work out what."""
    assert bash("sh scripts/self_check.py") == BLOCK


def test_bash_permits_allowlisted_git_subcommand() -> None:
    assert bash("git diff src/secrev/cli.py") == PASS_THROUGH


def test_bash_refuses_unlisted_git_subcommand() -> None:
    """`git` is not the unit of trust; `git diff` and `git log` are."""
    assert bash("git checkout -- src/secrev/cli.py") == BLOCK


# ------------------------------------------------- the harness guards itself
#
# Open question 4, decided. Nothing guarded .claude/: a `sed -i` on
# bash-guard.sh removed the control and no component was defective on its own.
# That is composition risk (PRD FR-0.8) found in the reviewer rather than the
# reviewed — the class of issue a per-artifact review structurally cannot see.


def test_bash_refuses_writing_to_a_guard() -> None:
    assert bash("sed -i 's/REFUSE/PERMIT/' .claude/hooks/bash_guard.py") == BLOCK
    assert bash("echo x > .claude/hooks/bash-guard.sh") == BLOCK
    assert bash("rm .claude/hooks/self-application-guard.sh") == BLOCK


def test_bash_refuses_writing_to_settings() -> None:
    """Unwiring a guard is as complete a disable as deleting it."""
    assert bash("cat > .claude/settings.json <<'EOF'") == BLOCK


def test_bash_permits_reading_a_guard() -> None:
    """The bootstrap objection, answered. Repair stays possible and stays
    visible: reading is untouched, and Write/Edit is where changes go, in
    front of the hooks that watch it."""
    assert bash("cat .claude/hooks/bash_guard.py") == PASS_THROUGH
    assert bash("grep -n REFUSE .claude/hooks/bash_guard.py") == PASS_THROUGH


def test_write_edit_to_the_harness_is_not_this_guard_s_business() -> None:
    """.claude/ is protected against Bash only, so the Write/Edit predicates in
    paths.sh must not have grown it. Repairing the harness through the tools
    the other guards can see is exactly the intended route."""
    paths = (HOOKS / "lib" / "paths.sh").read_text(encoding="utf-8")
    code = "\n".join(line.split("#", 1)[0] for line in paths.splitlines())
    assert ".claude" not in code, (
        "paths.sh governs Write/Edit; adding .claude/ there would close the "
        "repair route the bootstrap answer depends on"
    )


def test_bash_ignores_commands_that_touch_nothing_protected() -> None:
    """Documents open question 8, it does not settle it: the trigger is a test
    over path spellings, so anything it does not recognise passes untouched.
    Inherited from H-2's own wording, not invented here."""
    assert bash("rm -rf /tmp/scratch") == PASS_THROUGH


# ------------------------------------------------------------- documentation
#
# The harness documents what it enforces, and a description of a control is
# read as evidence of the control. Stale here is the same failure as a stale
# stack section (H-7), one level up.

CLAUDE_MD = REPO / "CLAUDE.md"
HARNESS_README = REPO / ".claude" / "README.md"


def test_readme_hook_count_is_current() -> None:
    """Mechanical, so it drifts loudly. `# N sh hooks` in the layout block has
    to equal the number of .sh files actually in hooks/."""
    text = HARNESS_README.read_text(encoding="utf-8")
    match = re.search(r"#\s*(\d+)\s+sh hooks", text)
    assert match, "the layout block no longer states a hook count"
    assert int(match.group(1)) == len(list(HOOKS.glob("*.sh"))), (
        f"README says {match.group(1)} sh hooks; there are {len(list(HOOKS.glob('*.sh')))}"
    )


def test_docs_do_not_claim_finished_work_is_open() -> None:
    """Each string below described the tree accurately when it was written and
    describes a repaired state now. A status table that has stopped being
    checked is worse than no status table: it is read, and believed."""
    stale = {
        "Violated — six hooks do": "jq was removed in TASK-007",
        "`scope-guard.sh:17` exits 0": "TASK-010 made it refuse",
        "`*/src/secrev/*` in three hooks": "TASK-009 unanchored them",
        "`scripts/` uncovered": "TASK-008 covered it",
        'carries a full "Technology Stack" section': "TASK-012 replaced it",
        "`.claude/MILESTONE` says `M1`": "TASK-011 set it to M0",
        "The repository has no commits": "TASK-000 made the baseline commit",
        "No source yet": "src/secrev/inventory.py exists (M1)",
        "every gate stage past `ruff` skips": "every stage runs since inventory.py landed",
    }
    # "recorded in STACK.md §2 with reasons" was on this list until TASK-014 put
    # mypy in §2 and made the sentence true. An assertion that pins a claim as
    # false has to be retired when the claim stops being false, or it starts
    # forbidding an accurate statement.
    text = CLAUDE_MD.read_text(encoding="utf-8")
    offenders = [f"{claim!r} ({why})" for claim, why in stale.items() if claim in text]
    assert not offenders, f"CLAUDE.md still claims: {offenders}"


def test_setup_advice_matches_stack_md() -> None:
    """STACK.md §3 stopped making `uv` the default in TASK-014. Anything that
    tells a human what to run has to say the same thing, or the decision lives
    in one file and the instructions live in another."""
    offenders = []
    for path in (CLAUDE_MD, REPO / "scripts" / "check.sh", HOOKS / "session-start.sh"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "uv sync" in line:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"still tells the reader to run `uv sync`: {offenders}"


def test_docs_name_the_bash_guard() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "bash-guard.sh" in text, "the highest-severity control is undocumented"


# ---------------------------------------------------- the environment (H-1, H-9)

QUALITY_HOOKS = ("async-check.sh", "determinism-guard.sh")


def test_no_quality_check_swallows_its_status() -> None:
    """H-1. `|| true` on a quality check turns "the tool is absent" into "the
    tool passed". async-check.sh did it three times per run, against a system
    python3 that had neither ruff nor pytest -- so it checked nothing and
    reported nothing, for as long as it existed."""
    offenders = []
    for name in QUALITY_HOOKS:
        for number, line in enumerate((HOOKS / name).read_text("utf-8").splitlines(), 1):
            if "|| true" in line.split("#", 1)[0]:
                offenders.append(f"{name}:{number}")
    assert not offenders, f"quality check swallowing its status: {offenders}"


def test_quality_checks_do_not_fall_back_to_path() -> None:
    """The tools live in .venv. System python3 has none of them, so a fallback
    is not a fallback -- it is a guaranteed failure, swallowed.

    Reading the payload is the opposite case and deliberately still uses system
    python3: lib/hook_input.py is stdlib, and a guard that stops working when
    .venv is missing is worse than one that works everywhere. The distinction
    is between running a tool and reading a JSON body.
    """
    for name in QUALITY_HOOKS:
        text = (HOOKS / name).read_text(encoding="utf-8")
        assert ".venv/bin/python" in text, f"{name} does not resolve .venv"
        code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
        # Boundary, not substring: `SYSPY=$(command -v python3` ends with
        # `PY=$(command -v python3`, and that assignment is the deliberate
        # stdlib reader rather than a fallback for running tools.
        assert not re.search(r"(?:^|[^A-Za-z_])PY=\$\(command -v python3", code), (
            f"{name} still falls back to PATH for running tools"
        )


def test_no_quality_check_loses_its_status_to_set_e() -> None:
    """`out=$(cmd)` followed by `status=$?` never reaches the second line.

    Under `set -e` a failing command substitution in an assignment exits the
    script immediately, so the explicit status handling is dead code and the
    hook returns the tool's own exit value — 1, which the hook protocol gives
    no meaning to (H-9). It also killed async-check.sh's loop mid-run, so one
    failing tool meant the remaining checks never ran and the log just stopped.

    Introduced by the fix for the `cmd | head` defect and found the same way:
    by breaking something else and reading the exit code carefully. The
    capture has to sit in an `if` condition, where `set -e` stands down.
    """
    offenders = []
    for name in QUALITY_HOOKS:
        text = (HOOKS / name).read_text(encoding="utf-8")
        code = [line.split("#", 1)[0] for line in text.splitlines()]
        for number, line in enumerate(code, 1):
            if re.search(r"^\s*(out|result)=\$\(", line):
                preceding = code[max(0, number - 3) : number - 1]
                if not any(stripped.strip().startswith("if") for stripped in preceding):
                    offenders.append(f"{name}:{number}")
    assert not offenders, f"capture outside an `if`, so set -e eats the status: {offenders}"


def test_no_quality_check_pipes_away_its_status() -> None:
    """POSIX sh has no PIPESTATUS, so `tool | head` makes `$?` the status of
    `head` — which succeeds whatever the tool did.

    This was introduced by TASK-005 and caught one turn later by the background
    gate reporting `[ok] pytest` under a failing test: the exact H-1 shape that
    task existed to remove, reintroduced by the fix for it. Capture first, trim
    second.
    """
    offenders = []
    for name in QUALITY_HOOKS:
        for number, line in enumerate((HOOKS / name).read_text("utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if '"$PY"' in code and re.search(r"\|\s*(head|tail)\b", code):
                offenders.append(f"{name}:{number}")
    assert not offenders, f"status lost to a pipe: {offenders}"


def test_async_check_reports_a_missing_environment_as_missing() -> None:
    """H-9: not a silent pass, and not silence. The log has to say the checks
    did not run, because async-check-report.sh prints it and a reader takes an
    empty section for a clean one."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".claude" / "hooks").mkdir(parents=True)
        shutil.copytree(HOOKS / "lib", root / ".claude" / "hooks" / "lib")
        rc, _, _ = run_hook(
            "async-check.sh",
            {"tool_name": "Write", "tool_input": {"file_path": "x.py", "content": "y"}},
            project_dir=root,
        )
        assert rc == PASS_THROUGH, "a PostToolUse hook must not block"
        log = (root / ".claude" / "hooks" / "state" / "async-check.log").read_text("utf-8")
    assert "did NOT run" in log, f"a missing .venv must be stated, got: {log!r}"


# ------------------------------------------------- single source of truth (H-7)

AGENTS = REPO / ".claude" / "agents"

# Verbatim mechanism copied out of STACK.md. Chosen because each appears in the
# restatement and nowhere a *reference* would legitimately put it. `CRLF` is
# deliberately not here: python-reviewer.md and plan-reviewer.md name §2.1's
# constructs as review checklists, which is arguably H-7 and arguably not --
# open question 7, and not a thing to settle by picking a grep string.
STACK_VERBATIM = (
    "Technology Stack",
    "That is the entire list",
    "the answer is WSL",
    "security-review/<target-slug>",
    "Python 3.11+",
)


def test_no_agent_restates_stack_md() -> None:
    """H-7: agent definitions reference STACK.md, never restate it.

    Disabled agents are included, which settles the question TASK-012 left
    open. disabled/README.md used to say a copy could stay until someone
    restored the file — the H-7 failure wearing a procedure, deferring the
    correction to a day when the copy would be older and relying on whoever
    did the restoring to remember. Both copies were already stale when
    removed. A file that is correct while disabled is correct when enabled.
    """
    offenders = []
    agents = sorted(AGENTS.glob("*.md")) + sorted((REPO / ".claude" / "disabled").glob("*.md"))
    # README.md is not an agent definition; it is the file that records why the
    # copies were removed, and it names the section it removed. Prose about a
    # restatement is not a restatement — the same distinction the jq assertion
    # makes between a call and a comment about one.
    for agent in (a for a in agents if a.name != "README.md"):
        text = agent.read_text(encoding="utf-8")
        for marker in STACK_VERBATIM:
            if marker in text:
                offenders.append(f"{agent.name}: {marker!r}")
    assert not offenders, f"STACK.md restated: {offenders}"


def test_documentation_architect_still_points_at_stack_md() -> None:
    """Deleting the section is only half of H-7. An agent that no longer knows
    where the mechanism lives has been made ignorant rather than accurate."""
    text = (AGENTS / "documentation-architect.md").read_text(encoding="utf-8")
    assert "STACK.md" in text, "the reference has to replace the copy, not vanish with it"


# ------------------------------------------------------------ current milestone


def test_milestone_marker_is_m3() -> None:
    """M2 is closed, so the marker moves again.

    It read M1 while BRIEF_M0.md sat unbuilt beside it, and TASK-011 pulled it
    back; leaving it at M0 after M0 closed would have refused every write to
    src/ and patterns/, which is exactly what M1 was. The marker is the
    harness's only notion of where the project is and it is wrong in both
    directions if nobody moves it.

    The M2 move was made before scope-guard.sh had M2 rules, so H-6 correctly
    refused every write to the scoped tree until BRIEF_M2.md existed — the
    guard saying the project claimed a milestone nobody had scoped. This move
    was made the other way round: the M3 branch and its assertions landed
    first, and only then the marker. Either order is survivable; only one of
    them is survivable without a window in which nothing can be written.
    """
    assert (REPO / ".claude" / "MILESTONE").read_text(encoding="utf-8").strip() == "M3"


def _unticked(brief: str) -> list[str]:
    text = (REPO / brief).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip().startswith("- [ ]")]


def test_m0_definition_of_done_is_fully_ticked() -> None:
    """The marker may not move ahead of the work. That is the failure TASK-011
    existed to fix, and moving it on a whose-turn-is-it basis would reproduce
    it a milestone later."""
    assert not _unticked("BRIEF_M0.md"), (
        f"M0 closed with open DoD items: {_unticked('BRIEF_M0.md')}"
    )


def test_the_marker_may_not_pass_a_brief_with_open_boxes() -> None:
    """The general form of the assertion above, which guarded M0 alone.

    Guarding only the milestone already closed is guarding the one that can no
    longer regress. The marker reaching `M2` while `BRIEF_M1.md` still has an
    unticked box is the same defect one milestone later, and it would be
    invisible: `scope-guard.sh` would simply stop policing the boundary M1 was
    supposed to hold, and every stage would stay green while doing so.

    Keyed off the marker rather than hardcoded, so it keeps working at M3
    without anyone remembering to extend it — which is exactly what did not
    happen the first time.
    """
    marker = (REPO / ".claude" / "MILESTONE").read_text(encoding="utf-8").strip()
    if not (match := re.fullmatch(r"M(\d+)", marker)):
        raise AssertionError(f"MILESTONE holds {marker!r}, which is not a milestone token")

    for number in range(int(match.group(1))):
        brief = f"BRIEF_M{number}.md"
        if (REPO / brief).is_file():
            assert not _unticked(brief), (
                f"MILESTONE is {marker} but {brief} still has open DoD items: {_unticked(brief)}"
            )


def test_session_start_reports_the_marker_and_says_when_the_brief_is_absent() -> None:
    """M1 is closed, so the marker reads M2 and there is no `BRIEF_M2.md` yet.

    The assertion is on the *pairing*, not on a fixed milestone. Reporting a
    marker with no brief is the honest state at exactly this moment — between
    one milestone closing and the next being written — and the hook must say so
    rather than print a scope line naming a file nobody can read. A version of
    this test that hardcoded `M1` would have had to be edited anyway; one that
    hardcoded the brief's *presence* would fail here for the wrong reason.
    """
    proc = subprocess.run(
        [SH, str(HOOKS / "session-start.sh")],
        input="",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == PASS_THROUGH

    marker = (REPO / ".claude" / "MILESTONE").read_text(encoding="utf-8").strip()
    assert f"Milestone: {marker}" in proc.stdout

    brief = f"BRIEF_{marker}.md"
    if (REPO / brief).is_file():
        assert brief in proc.stdout
        assert f"No {brief} in the repo" not in proc.stdout
    else:
        assert f"No {brief} in the repo" in proc.stdout


def test_m0_permits_the_work_m0_is_defined_to_do() -> None:
    """H-6 says a guard with no rules refuses. The answer to that is to give it
    rules, not to leave it ruleless and call the refusal correct: BRIEF_M0.md §2
    edits scripts/check.sh, so refusing scripts/ under M0 would block the
    milestone from doing the thing it exists to do.
    """
    rc, out = scope_at("M0", "scripts/check.sh", "printf 'all gates pass'\n")
    assert rc == PASS_THROUGH and not asks(out), "M0 is harness repair; scripts/ is its remit"


def test_m0_refuses_patterns() -> None:
    rc, _ = scope_at("M0", "patterns/_base.yaml", "- id: py.eval\n")
    assert rc == BLOCK, "the catalog is M1; M0 has no business there"


def test_m0_leaves_the_harness_itself_unscoped() -> None:
    """.claude/ is not in the scoped tree. That is open question 4, not an
    oversight -- guarding the harness with the harness has a bootstrap problem
    this milestone does not solve."""
    rc, out = scope_at("M0", ".claude/hooks/bash-guard.sh", "exit 0\n")
    assert rc == PASS_THROUGH and not out.strip()


# --------------------------------------------------------- scope, off-milestone
#
# STACK.md §8 H-6: a guard with no rules for the current state refuses. It
# exited 0, so the moment MILESTONE advanced, scope enforcement vanished with
# no signal -- indistinguishable from a guard that looked and found nothing.


def scope_at(
    milestone: str | None, relative: str, body: str, absolute: bool = True
) -> tuple[int, str]:
    """Run scope-guard against a named milestone rather than the repo's marker.

    `absolute=False` sends the path as given, which is how the client may or
    may not spell it (H-5) -- joining it to the temp root would quietly turn a
    relative-path test into an absolute-path one.
    """
    with milestone_tree(milestone) as tmp:
        path = str(Path(tmp) / relative) if absolute else relative
        rc, out, _ = run_hook("scope-guard.sh", write_payload(path, body), project_dir=Path(tmp))
    return rc, out


def test_bash_refuses_writing_a_threat_model() -> None:
    """M3's overlays are tool input in the sense that matters: a mandatory
    question removed is a check that disappears from every later review of that
    archetype (TASKS_M3.md D-1, STACK.md §8 H-4)."""
    assert bash("echo x > threat-models/_agentic-core.md") == BLOCK


def test_bash_permits_reading_a_threat_model() -> None:
    """Protected against writing, not against being read — the same shape as
    the catalog and the surface kinds."""
    assert bash("cat threat-models/_agentic-core.md") == PASS_THROUGH


def test_m3_permits_its_own_deliverables() -> None:
    """A milestone that cannot write its own remit teaches people to click
    through the guard, which is the cost side of H-2 that never shows up as a
    refusal (the M2 precedent)."""
    rc, out = scope_at("M3", "threat-models/_agentic-core.md", "# Core\n")
    assert rc == PASS_THROUGH and not asks(out), "M3 must be able to write threat-models/"


def test_another_milestone_may_not_rewrite_the_threat_model() -> None:
    """Scoping is what stops a later milestone rewriting the questions while
    calling itself structural work. M1 and M2 are closed and own no overlay.

    Both are checked because the first draft of this test checked only M2 and
    found it permitting the write: a milestone branch refuses the directories
    it was written against and answers "permit" by omission for every one added
    later. M1's branch was a bare `;;`, which permitted the whole scoped tree.
    Adding a directory to `is_scoped_path` decides which paths the guard is
    *consulted* about, never what any milestone answers.
    """
    for milestone in ("M1", "M2"):
        rc, _ = scope_at(milestone, "threat-models/skill.md", "# Skill\n")
        assert rc == BLOCK, f"threat-models/ is outside {milestone}'s remit, got rc={rc}"


def test_m3_refuses_the_scoped_tree_for_its_own_reason() -> None:
    """M3 is the threat-model layer and writes prose into `threat-models/`,
    which is outside the scoped tree — so every write the guard *does* see
    under M3 is out of remit. The message has to be M3's own: falling through
    to `refuse_no_rules` would say "this milestone needs its own rules added
    here", which is false once they exist, and a refusal that gives a reason it
    no longer holds teaches a reader to stop believing the message."""
    for relative in ("src/secrev/structure.py", "patterns/_instruction.yaml"):
        # run_hook rather than scope_at: a refusal is written to stderr, and
        # scope_at hands back stdout, which carries `ask` payloads. The message
        # is the substance of this assertion, so the test has to read the
        # stream the message is on.
        with milestone_tree("M3") as tmp:
            path = str(Path(tmp) / relative)
            rc, _, err = run_hook(
                "scope-guard.sh", write_payload(path, "x = 1\n"), project_dir=Path(tmp)
            )
        assert rc == BLOCK, f"M3 must refuse {relative}, got rc={rc}"
        assert "threat-model" in err, f"M3's refusal must name its own remit: {err}"
        assert "no rules permitting this write" not in err, (
            f"M3 has rules; it must not refuse as though it had none: {err}"
        )


def test_scope_guard_refuses_on_unknown_milestone() -> None:
    """Inverted from a known-open assertion in TASK-001."""
    rc, _ = scope_at("M9", "src/secrev/sweep.py", "severity = 1\n")
    assert rc == BLOCK, f"no rules for M9, so it must refuse, got rc={rc}"


def test_m2_permits_the_work_m2_is_defined_to_do() -> None:
    """The same reasoning as the M0 case, one milestone on.

    Closing M1 moved the marker to M2 and H-6 correctly refused every write to
    the scoped tree until M2 had rules. The answer to that is to write the
    rules — never to move the marker back to buy write access, which would be
    the marker being wrong in the third distinct direction.
    """
    rc, out = scope_at("M2", "src/secrev/surfaces.py", "def enumerate_surfaces():\n    pass\n")
    assert rc == PASS_THROUGH and not asks(out), "M2 is the surface source; src/ is its remit"


def test_m2_refuses_catalog_writes() -> None:
    """M2 adds a candidate *source*, not rules. Packs are M5 (BRIEF_M2.md §1).
    A milestone that can write anything has no scope."""
    rc, _ = scope_at("M2", "patterns/_manifest.yaml", 'version: "2026.09.1"\n')
    assert rc == BLOCK, f"patterns/ is outside M2's remit, got rc={rc}"


def test_m2_does_not_object_to_its_own_subject() -> None:
    """The surfaces heuristic fires under M1 and must not under M2.

    A guard that objects to the work it exists to permit teaches people to
    click through it, and every other check in that file is then read the same
    way. This is the cost side of H-2/H-6 that does not show up as a refusal.
    """
    body = "def surface_entry_point(node):\n    return node\n"
    rc_m2, out_m2 = scope_at("M2", "src/secrev/surfaces.py", body)
    assert rc_m2 == PASS_THROUGH and not asks(out_m2), "M2 must not be asked about surfaces"

    _, out_m1 = scope_at("M1", "src/secrev/sweep.py", body)
    assert asks(out_m1), "under M1 the same body must still raise the question"


def test_scope_guard_refuses_on_unknown_milestone_even_when_clean() -> None:
    """The refusal is about having no rules, not about what the body contains.
    A guard that only refuses suspicious content has rules after all."""
    rc, _ = scope_at("M9", "src/secrev/sweep.py", "line_no = idx + 1\n")
    assert rc == BLOCK


def test_scope_guard_leaves_unscoped_paths_alone_off_milestone() -> None:
    """The ordering test. If the milestone check ran before the path filter,
    exit 2 would refuse every write in the repository -- a guard that refuses
    everything is as useless as one that refuses nothing, and considerably
    more annoying."""
    rc, out = scope_at("M9", "README.md", "severity = 1\n")
    assert rc == PASS_THROUGH and not out.strip()


def test_scope_guard_refuses_when_milestone_is_missing() -> None:
    """`|| echo M1` was its own H-1 breach: unable to read the marker, it
    assumed the one milestone it had rules for."""
    rc, _ = scope_at(None, "src/secrev/sweep.py", "severity = 1\n")
    assert rc == BLOCK


def test_scope_guard_refuses_during_m0() -> None:
    """What TASK-011 makes live. M0 is harness repair and writes nothing under
    src/ or patterns/, so refusing there is the correct rule for it and not
    merely the absence of one."""
    rc, _ = scope_at("M0", "src/secrev/sweep.py", "line_no = 1\n")
    assert rc == BLOCK


def test_scope_guard_still_asks_on_m1() -> None:
    """The regression that matters: M1 behaviour is unchanged."""
    rc, out = scope_at("M1", "src/secrev/sweep.py", "severity = 'high'\n")
    assert rc == PASS_THROUGH and asks(out)


# ------------------------------------------------------------- path anchoring
#
# STACK.md §8 H-5. `*/src/secrev/*.py` needs a leading directory, so it matches
# only because the client happens to send absolute paths -- true today,
# undocumented, and not something a control should rest on.


def test_relative_path_reaches_self_application_guard() -> None:
    """Inverted from a known-open assertion in TASK-001."""
    rc, _, _ = run_hook(
        "self-application-guard.sh", write_payload("src/secrev/cli.py", "x = eval('1')\n")
    )
    assert rc == BLOCK, f"relative path must be guarded, got rc={rc}"


def test_relative_path_reaches_scripts_coverage() -> None:
    rc, _, _ = run_hook(
        "self-application-guard.sh", write_payload("scripts/self_check.py", "x = eval('1')\n")
    )
    assert rc == BLOCK


def test_relative_path_reaches_scope_guard() -> None:
    rc, out = scope_at("M1", "src/secrev/sweep.py", "severity = 'high'\n", absolute=False)
    assert rc == PASS_THROUGH and asks(out)


def test_relative_path_reaches_determinism_guard() -> None:
    rc, out, _ = run_hook("determinism-guard.sh", write_payload("src/secrev/ids.py", ""))
    assert rc == PASS_THROUGH and "NFR-3" in out


def test_determinism_guard_speaks_on_the_shared_ledger_module() -> None:
    """TASKS_M2 Q2. `ledger.py` holds the record, its serialisation, the window
    and redaction for every source, so it decides bytes in every ledger. It
    owns NFR-3 rules as surely as `sweep.py` did when they lived there."""
    rc, out, _ = run_hook("determinism-guard.sh", write_payload("src/secrev/ledger.py", ""))
    assert rc == PASS_THROUGH and "ledger.py" in out and "NFR-3" in out, (
        "touching ledger.py must restate the determinism rules — is_nfr3_path "
        "in .claude/hooks/lib/paths.sh does not name it"
    )


def test_relative_path_reaches_determinism_guard_for_surfaces() -> None:
    rc, out, _ = run_hook("determinism-guard.sh", write_payload("src/secrev/surfaces.py", ""))
    assert rc == PASS_THROUGH and "surfaces.py" in out and "NFR-3" in out


def test_every_anchored_glob_has_a_relative_sibling() -> None:
    """H-5, as corrected: `*/src/secrev/*.py` is fine *paired with*
    `src/secrev/*.py`, and wrong alone.

    The earlier version of this assertion banned `*/dir/` outright, which was
    right while the fix was "drop the anchor" and became wrong when the fix
    became "spell both spellings". An assertion tied to a mechanism rather than
    to its reason has to be rewritten when the mechanism is corrected.
    """
    offenders = []
    scripts = sorted(list(HOOKS.glob("*.sh")) + list((HOOKS / "lib").glob("*.sh")))
    for script in scripts:
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for anchored in re.findall(r"\*/((?:src|patterns|scripts)[^ |)]*)", code):
                if not re.search(r"(?:^|[|(\s])" + re.escape(anchored), code):
                    offenders.append(f"{script.name}:{number} — {anchored} only ever anchored")
    assert not offenders, f"anchored-only globs: {offenders}"


def test_glob_does_not_overmatch_a_similar_name() -> None:
    """Inverted from the assertion that recorded the over-match in TASK-009.

    H-5 said `*src/secrev/*.py`, which drops the dependency on absolute paths
    and also matches `foosrc/secrev/`; the scripts/ form matched `transcripts/`
    and `descripts/`. Corrected in STACK.md to the two-alternative form, which
    meets the stated rationale without the collateral. The old failure was
    closed rather than open -- but a control that fires on the wrong file
    teaches people to work around it, and that is how a control dies.
    """
    for path in ("foosrc/secrev/x.py", "/home/u/transcripts/notes.py", "/var/lib/descripts/a.py"):
        rc, _, _ = run_hook("self-application-guard.sh", write_payload(path, "x = eval('1')\n"))
        assert rc == PASS_THROUGH, f"{path} is not this project's tree, got rc={rc}"


def test_glob_still_matches_both_spellings() -> None:
    """The half that must survive the correction: relative and absolute."""
    for path in (
        "src/secrev/cli.py",
        str(REPO / "src" / "secrev" / "cli.py"),
        "scripts/x.py",
        str(REPO / "scripts" / "x.py"),
    ):
        rc, _, _ = run_hook("self-application-guard.sh", write_payload(path, "x = eval('1')\n"))
        assert rc == BLOCK, f"{path} must stay guarded, got rc={rc}"


# ----------------------------------------------------------- protected paths
#
# STACK.md §8 H-4. `patterns/` especially: it is the tool's input, and a rule
# added or altered without review is a check that silently disappears from
# every later run.


def test_self_application_guards_scripts() -> None:
    """Inverted from a known-open assertion in TASK-001.

    BRIEF_M0.md §3 says the gate catches this after the fact. It does not:
    self_check.py:18 scans src/secrev only, so nothing else in the gate looks
    at scripts/. This hook is the only control over that directory, which
    raises the bar on it rather than lowering it.
    """
    rc, _, err = run_hook(
        "self-application-guard.sh",
        write_payload(str(REPO / "scripts" / "self_check.py"), "x = eval('1')\n"),
    )
    assert rc == BLOCK, f"eval into scripts/ must be refused, got rc={rc}"
    assert "eval(" in err
    assert "src/secrev" not in err, (
        "the refusal names the file it refused; it said src/secrev for a "
        "write to scripts/, which was true only while the guard covered one "
        "directory"
    )


def test_self_application_permits_clean_scripts() -> None:
    rc, _, _ = run_hook(
        "self-application-guard.sh",
        write_payload(str(REPO / "scripts" / "check_thing.py"), "import ast\n"),
    )
    assert rc == PASS_THROUGH


def test_self_application_ignores_pattern_data() -> None:
    """patterns/ is the catalog, and a rule that detects `yaml.load` contains
    the string `yaml.load`. Refusing it would block the tool's own input for
    describing the construct it exists to find -- data read as if it were code.
    Coverage of patterns/ belongs to the scope guard, which asks about the rule
    being added, not to this one.
    """
    rc, _, _ = run_hook(
        "self-application-guard.sh",
        write_payload(
            str(REPO / "patterns" / "_base.yaml"),
            "- id: py.yaml_load\n  regex: 'yaml\\.load\\('\n",
        ),
    )
    assert rc == PASS_THROUGH, "a catalog rule is data, not a self-application breach"


def test_scope_guard_covers_scripts() -> None:
    rc, out = scope_at("M1", "scripts/render.py", "severity = 'high'\n")
    assert rc == PASS_THROUGH and asks(out), "scripts/ is in the scope guard's remit"


def test_scope_guard_covers_patterns() -> None:
    rc, out = scope_at("M1", "patterns/_base.yaml", "multiline: true\n")
    assert rc == PASS_THROUGH and asks(out), "patterns/ is the tool's input"


def test_scope_guard_covers_surfaces() -> None:
    """surfaces/ is in the scoped tree: a milestone with no business there
    refuses it, as M0 refuses patterns/."""
    rc, _ = scope_at("M0", "surfaces/_surfaces.yaml", 'version: "2026.09.1"\n')
    assert rc == BLOCK, f"surfaces/ is outside M0's remit, got rc={rc}"


def test_m2_permits_the_surface_kinds() -> None:
    """...and the milestone that owns the surface source may write its data."""
    rc, out = scope_at("M2", "surfaces/_surfaces.yaml", 'version: "2026.09.1"\n')
    assert rc == PASS_THROUGH and not asks(out), "surfaces/ is M2's remit"


def test_protected_paths_have_one_definition() -> None:
    """H-7. Two guards deciding separately what `protected` means is how the
    two answers drift apart without either looking wrong."""
    for hook in ("self-application-guard.sh", "scope-guard.sh"):
        src = (HOOKS / hook).read_text(encoding="utf-8")
        assert "lib/paths.sh" in src, f"{hook} does not source the shared definition"


# ------------------------------------------------------------ dependency: jq
#
# STACK.md §2 records jq as removed -- a non-Python external dependency,
# undeclared, in a repository requiring a written reason for every one, and
# exactly what §1's prefer-Python rule exists to avoid. The document has said
# so in the past tense the whole time; six hooks called it anyway.


def test_no_hook_invokes_jq() -> None:
    """The sweep. Named hooks below fail with a useful message; this catches a
    seventh hook appearing later with jq in it."""
    offenders = sorted(script.name for script in HOOKS.glob("*.sh") if invokes_jq(script))
    assert not offenders, f"hooks still shelling out to jq: {offenders}"


def test_scope_guard_uses_no_jq() -> None:
    assert not invokes_jq(HOOKS / "scope-guard.sh")


def test_spec_guard_uses_no_jq() -> None:
    assert not invokes_jq(HOOKS / "spec-guard.sh")


def test_plan_review_uses_no_jq() -> None:
    assert not invokes_jq(HOOKS / "plan-review.sh")


def test_determinism_guard_uses_no_jq() -> None:
    assert not invokes_jq(HOOKS / "determinism-guard.sh")


def test_async_check_uses_no_jq() -> None:
    assert not invokes_jq(HOOKS / "async-check.sh")


def test_scope_guard_refuses_malformed_payload() -> None:
    """H-1, same defect the self-application guard had: jq's parse-error code
    leaked through `set -e` as an exit value the protocol gives no meaning."""
    proc = subprocess.run(
        [SH, str(HOOKS / "scope-guard.sh")],
        input="{not json at all",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == BLOCK, f"got rc={proc.returncode}"


def test_spec_guard_refuses_malformed_payload() -> None:
    proc = subprocess.run(
        [SH, str(HOOKS / "spec-guard.sh")],
        input="{not json at all",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == BLOCK, f"got rc={proc.returncode}"


# ---------------------------------------------------------------- known-open
#
# These assert what the harness does TODAY, which is not what it should do.
# Each names the task that inverts it. They are here so the repair is visible
# as a diff in this file rather than as a silent change in behaviour -- and so
# that a guard which starts refusing correctly cannot do so unnoticed.


def test_bash_guard_is_wired() -> None:
    """The last of the four known-open assertions from TASK-001, inverted.

    BRIEF_M0.md §1's highest-severity item, and the reason the guard file
    existing was never the control: settings.json is what invokes it.
    """
    settings = json.loads((REPO / ".claude" / "settings.json").read_text("utf-8"))
    pre = settings.get("hooks", {}).get("PreToolUse", [])
    bash_entries = [entry for entry in pre if "Bash" in entry.get("matcher", "")]
    assert bash_entries, "no PreToolUse matcher covers Bash — the bypass is open"
    commands = [
        hook.get("command", "") for entry in bash_entries for hook in entry.get("hooks", [])
    ]
    assert any("bash-guard.sh" in command for command in commands), (
        "a Bash matcher exists but does not invoke bash-guard.sh"
    )


def test_docs_no_longer_call_the_bypass_open() -> None:
    """Paired with the wiring. Documenting a closed bypass as open is the same
    class of error as documenting an open one as closed — the status table is
    read, and believed."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "The Bash bypass is still open" not in text
    assert "not wired" not in text


def test_gate_never_skips_a_missing_tool() -> None:
    """H-1 in the gate itself, which is where it mattered most.

    With ruff, mypy and pytest all absent, check.sh printed
    `skipped: not installed` three times and still reached `all gates pass`.
    CI trusts that script. "Nothing to check yet" is a legitimate skip;
    "cannot check" is not, and the two were the same word.

    Structural rather than executed: hiding a tool from the gate from inside
    the gate's own test suite costs more than it proves. The executed version
    is in the receipt.
    """
    gate = (REPO / "scripts" / "check.sh").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in gate.splitlines()
        if line.strip().startswith("skip ") and "not installed" in line
    ]
    assert not offenders, f"a missing tool is still skipped: {offenders}"
    assert "missing()" in gate, "the gate has no branch that refuses on a missing tool"


def test_gate_separates_no_tests_from_no_pytest() -> None:
    """`[ -d tests ] && pytest --version` collapsed both states into one
    message — and once tests/ existed the message was simply false, which is
    how it was noticed."""
    gate = (REPO / "scripts" / "check.sh").read_text(encoding="utf-8")
    assert "no tests/ or pytest not installed" not in gate


def test_the_harness_gate_runs_the_attack_driver() -> None:
    """The instrument has to be wired to a gate, or it is a check nobody sees.

    Inverted from an assertion that named `scripts/check.sh`. It ran here
    until the two gates were separated: `.claude/` is the layer that writes
    this project, and a stage asserting that a PreToolUse hook still refuses a
    heredoc is not an answer to "is the software correct".

    Reads the script rather than running it — the gate invokes this file, so
    executing it here would recurse. That the wiring fires is established by
    defeating a guard and watching the gate go red, which a text check cannot
    do and does not pretend to.
    """
    gate = (REPO / ".claude" / "check.sh").read_text(encoding="utf-8")
    assert "tests/harness/attack.py" in gate, ".claude/check.sh runs no guard assertions"


def test_the_product_gate_does_not_reach_into_the_harness() -> None:
    """The separation, asserted in the direction that actually erodes.

    Nobody deletes a boundary deliberately; someone adds one convenient line.
    The product gate ran the guard assertions and wrote its success marker into
    `.claude/hooks/state/`, so a contributor without Claude Code could have
    their build fail on a layer they never run, and the dependency pointed from
    the thing being built into the thing building it.

    Reading across is fine — the harness may read `.gate-passed`. Writing
    across is not.
    """
    gate = (REPO / "scripts" / "check.sh").read_text(encoding="utf-8")
    code = "\n".join(line.split("#", 1)[0] for line in gate.splitlines())
    assert ".claude" not in code, (
        "scripts/check.sh references .claude/ outside a comment — the product "
        "gate must not read from, write to, or invoke the harness"
    )
    assert "tests/harness" not in code, (
        "scripts/check.sh runs a harness test; that is .claude/check.sh's job"
    )


# ------------------------------------------------------------------- runner


def main() -> int:
    tests = sorted(
        (name, obj) for name, obj in globals().items() if name.startswith("test_") and callable(obj)
    )
    failures: list[tuple[str, str]] = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures.append((name, str(exc) or "assertion failed"))
            print(f"FAIL  {name}")
        except Exception as exc:  # a guard that crashes is a guard that is not running
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"ERROR {name}")
        else:
            print(f"ok    {name}")

    print()
    if failures:
        print(f"{len(failures)} of {len(tests)} failed:")
        for name, why in failures:
            print(f"  {name}: {why}")
        return 1
    print(f"all {len(tests)} guard assertions hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
