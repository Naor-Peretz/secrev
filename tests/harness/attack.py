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
        ["sh", str(HOOKS / hook)],
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
    rc, _, err = run_hook(
        "self-application-guard.sh", write_payload(ABS_SRC, "x = eval('1')\n")
    )
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
        ["sh", str(HOOKS / "self-application-guard.sh")],
        input="{not json at all",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == BLOCK, (
        f"malformed payload must refuse, got rc={proc.returncode}"
    )


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
    rc, out, _ = run_hook(
        "spec-guard.sh", write_payload(str(REPO / "CLAUDE.md"), "# notes\n")
    )
    assert rc == PASS_THROUGH and not asks(out), "CLAUDE.md is not one of the three"


# ------------------------------------------------------------ determinism-guard


def test_determinism_guard_speaks_on_nfr3_file() -> None:
    rc, out, _ = run_hook(
        "determinism-guard.sh", write_payload(str(REPO / "src" / "secrev" / "ids.py"), "")
    )
    assert rc == PASS_THROUGH, f"PostToolUse guard must not block, got rc={rc}"
    assert "NFR-3" in out, "touching ids.py must restate the determinism rules"


def test_determinism_guard_silent_elsewhere() -> None:
    rc, out, _ = run_hook(
        "determinism-guard.sh", write_payload(str(REPO / "src" / "secrev" / "cli.py"), "")
    )
    assert rc == PASS_THROUGH and not out.strip(), "cli.py owns no NFR-3 rule"


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
    rc, _, _ = run_hook(
        "bash-guard.sh", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    return rc


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


def test_bash_permits_read_only_pipeline() -> None:
    assert bash("cat src/secrev/cli.py | grep -n eval | head -5") == PASS_THROUGH


def test_bash_permits_allowlisted_git_subcommand() -> None:
    assert bash("git diff src/secrev/cli.py") == PASS_THROUGH


def test_bash_refuses_unlisted_git_subcommand() -> None:
    """`git` is not the unit of trust; `git diff` and `git log` are."""
    assert bash("git checkout -- src/secrev/cli.py") == BLOCK


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
        "carries a full \"Technology Stack\" section": "TASK-012 replaced it",
        "`.claude/MILESTONE` says `M1`": "TASK-011 set it to M0",
        "The repository has no commits": "TASK-000 made the baseline commit",
        "recorded in `STACK.md` §2 with reasons": "mypy is not in §2; open question 10",
    }
    text = CLAUDE_MD.read_text(encoding="utf-8")
    offenders = [f"{claim!r} ({why})" for claim, why in stale.items() if claim in text]
    assert not offenders, f"CLAUDE.md still claims: {offenders}"


def test_docs_name_the_bash_guard() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "bash-guard.sh" in text, "the highest-severity control is undocumented"


def test_known_open_docs_say_the_bash_guard_is_unwired() -> None:
    """TASK-004 inverts this. The guard exists and is tested; settings.json
    does not reference it, so nothing invokes it. Documenting it as active
    would be the exact false-assurance this milestone exists to remove.
    """
    settings = json.loads((REPO / ".claude" / "settings.json").read_text("utf-8"))
    matchers = [
        entry.get("matcher", "")
        for entry in settings.get("hooks", {}).get("PreToolUse", [])
    ]
    if any("Bash" in m for m in matchers):
        raise AssertionError("Bash matcher wired — invert this and update the docs.")
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "not wired" in text or "unwired" in text, (
        "the docs must say the Bash guard is not yet invoked"
    )


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


def test_no_live_agent_restates_stack_md() -> None:
    """H-7: agent definitions reference STACK.md, never restate it. A copied
    stack section goes stale silently, which is the failure mode STACK.md
    exists to prevent."""
    offenders = []
    for agent in sorted(AGENTS.glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        for marker in STACK_VERBATIM:
            if marker in text:
                offenders.append(f"{agent.name}: {marker!r}")
    assert not offenders, f"STACK.md restated in live agents: {offenders}"


def test_documentation_architect_still_points_at_stack_md() -> None:
    """Deleting the section is only half of H-7. An agent that no longer knows
    where the mechanism lives has been made ignorant rather than accurate."""
    text = (AGENTS / "documentation-architect.md").read_text(encoding="utf-8")
    assert "STACK.md" in text, "the reference has to replace the copy, not vanish with it"


# ------------------------------------------------------------ current milestone


def test_milestone_marker_is_m0() -> None:
    """.claude/MILESTONE was M1 while BRIEF_M0.md sat unbuilt beside it. The
    marker is the harness's only notion of where the project is, and it had
    been set forward past a milestone that never happened."""
    assert (REPO / ".claude" / "MILESTONE").read_text(encoding="utf-8").strip() == "M0"


def test_session_start_reports_m0_and_finds_its_brief() -> None:
    proc = subprocess.run(
        ["sh", str(HOOKS / "session-start.sh")],
        input="",
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(REPO)},
        cwd=str(REPO),
        check=False,
    )
    assert proc.returncode == PASS_THROUGH
    assert "Milestone: M0" in proc.stdout
    assert "BRIEF_M0.md" in proc.stdout
    assert "No BRIEF_M0.md in the repo" not in proc.stdout


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
        rc, out, _ = run_hook(
            "scope-guard.sh", write_payload(path, body), project_dir=Path(tmp)
        )
    return rc, out


def test_scope_guard_refuses_on_unknown_milestone() -> None:
    """Inverted from a known-open assertion in TASK-001."""
    rc, _ = scope_at("M9", "src/secrev/sweep.py", "severity = 1\n")
    assert rc == BLOCK, f"no rules for M9, so it must refuse, got rc={rc}"


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


def test_no_glob_carries_a_leading_anchor() -> None:
    """The sweep, so a seventh hook cannot reintroduce the pattern quietly."""
    offenders = []
    for script in sorted(list(HOOKS.glob("*.sh")) + list((HOOKS / "lib").glob("*.sh"))):
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"\*/(?:src|patterns|scripts)/", code):
                offenders.append(f"{script.name}:{number}")
    assert not offenders, f"anchored globs remain: {offenders}"


def test_unanchored_glob_overmatches_and_fails_closed() -> None:
    """H-5's literal form matches `foosrc/secrev/`, which is not this project.

    Recorded rather than silently improved. `src/secrev/*.py|*/src/secrev/*.py`
    would satisfy H-5's stated rationale without the over-match, but H-5 gives
    the mechanism verbatim and STACK.md wins on mechanism -- so the deviation
    is raised in the ledger, not taken here. The over-match refuses a write to
    a path this repository does not contain, which is the safe direction.
    """
    for path in ("foosrc/secrev/x.py", "/home/u/transcripts/notes.py", "/tmp/descripts/a.py"):
        rc, _, _ = run_hook(
            "self-application-guard.sh", write_payload(path, "x = eval('1')\n")
        )
        assert rc == BLOCK, f"the over-match is expected; if {path} stops, H-5 changed"
    # Not everything is swept up: the suffix still has to be there.
    for path in ("/opt/mypatterns/r.yaml", "/home/u/docs/x.py"):
        rc, _, _ = run_hook(
            "self-application-guard.sh", write_payload(path, "x = eval('1')\n")
        )
        assert rc == PASS_THROUGH, f"{path} should not match any protected glob"


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
    offenders = sorted(
        script.name for script in HOOKS.glob("*.sh") if invokes_jq(script)
    )
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
        ["sh", str(HOOKS / "scope-guard.sh")],
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
        ["sh", str(HOOKS / "spec-guard.sh")],
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


def test_known_open_bash_bypass_is_unwired() -> None:
    """TASK-004 inverts this. BRIEF_M0.md §1, the highest-severity item."""
    settings = json.loads((REPO / ".claude" / "settings.json").read_text("utf-8"))
    matchers = [
        entry.get("matcher", "")
        for entry in settings.get("hooks", {}).get("PreToolUse", [])
    ]
    assert not any("Bash" in m for m in matchers), (
        "A Bash matcher now exists -- the bypass is closed. Invert this test."
    )


def test_gate_runs_the_attack_driver() -> None:
    """The instrument has to be wired to the gate, or it is a check nobody sees.

    Reads scripts/check.sh rather than running it: the gate invokes this file,
    so executing it here would recurse. The claim that the wiring actually
    fires is verified by defeating a guard and watching the gate go red -- a
    text check cannot establish that, and does not pretend to.
    """
    gate = (REPO / "scripts" / "check.sh").read_text(encoding="utf-8")
    assert "tests/harness/attack.py" in gate, (
        "scripts/check.sh does not run the guard assertions"
    )


# ------------------------------------------------------------------- runner


def main() -> int:
    tests = sorted(
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
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
