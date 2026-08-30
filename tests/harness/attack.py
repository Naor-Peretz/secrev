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


def milestone_tree(value: str) -> tempfile.TemporaryDirectory[str]:
    """A throwaway project dir holding nothing but .claude/MILESTONE."""
    tmp = tempfile.TemporaryDirectory()
    claude = Path(tmp.name) / ".claude"
    claude.mkdir(parents=True)
    (claude / "MILESTONE").write_text(value + "\n", encoding="utf-8")
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
    rc, out, _ = run_hook(
        "scope-guard.sh",
        write_payload(str(REPO / "src" / "secrev" / "sweep.py"), "severity = 'high'\n"),
    )
    assert rc == PASS_THROUGH, f"scope-guard asks, never blocks, got rc={rc}"
    assert asks(out), "assigning a severity in M1 must reach the human"


def test_scope_guard_permits_in_scope_write() -> None:
    rc, out, _ = run_hook(
        "scope-guard.sh",
        write_payload(
            str(REPO / "src" / "secrev" / "sweep.py"), "line_no = idx + 1\n"
        ),
    )
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


def test_known_open_scripts_dir_is_unguarded() -> None:
    """TASK-008 inverts this. self_check.py:18 scans src/secrev only, so the
    gate does not catch this either: the new coverage is the only control."""
    rc, _, _ = run_hook(
        "self-application-guard.sh",
        write_payload(str(REPO / "scripts" / "self_check.py"), "x = eval('1')\n"),
    )
    assert rc == PASS_THROUGH, "scripts/ is now guarded -- invert this test."


def test_known_open_relative_path_escapes_guard() -> None:
    """TASK-009 inverts this. The glob `*/src/secrev/*.py` needs a leading
    directory, so a relative path misses it entirely (H-5)."""
    rc, _, _ = run_hook(
        "self-application-guard.sh", write_payload("src/secrev/cli.py", "x = eval('1')\n")
    )
    assert rc == PASS_THROUGH, "relative paths now match -- invert this test."


def test_known_open_scope_guard_exits_silently_off_m1() -> None:
    """TASK-010 inverts this. H-6: a guard with no rules for the current state
    refuses. Today it returns 0, and scope enforcement vanishes with no signal."""
    with milestone_tree("M9") as tmp:
        rc, out, _ = run_hook(
            "scope-guard.sh",
            write_payload(str(Path(tmp) / "src" / "secrev" / "sweep.py"), "severity = 1\n"),
            project_dir=Path(tmp),
        )
    assert rc == PASS_THROUGH and not asks(out), (
        "scope-guard now reacts off-M1 -- invert this test."
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
