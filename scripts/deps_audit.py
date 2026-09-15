"""Known-vulnerability audit of the declared dependency set.

STACK.md §2.2. The analogue of `pnpm audit` in the project this gate was
compared against — a check that the packages this repository declares are not
carrying published advisories.

Two audits, because they answer different questions:

  1. `pip-audit .` — the dependencies this project declares in pyproject.toml.
     Resolved the way an installer would resolve them, so it sees the version
     a fresh install gets rather than the version this machine happens to hold.
  2. `pip-audit --no-deps -r …` — the two pinned toolchains, `dev.txt` and
     `audit.txt`. Pinned exactly, so no resolution is needed or wanted; these
     are the versions CI will install.

What this deliberately does not audit: the interpreter's own bootstrap
`pip`/`setuptools` inside a venv. They are not declared anywhere in this
repository, they differ per runner, and an advisory against them is fixed by
upgrading an environment rather than by changing a file here. That is a real
gap and is stated rather than left to be discovered — `python -m pip install
--upgrade pip` is the answer when one appears.

Needs the network: it queries OSV. That is why the stage runs at push and in
CI, and not in `check.sh --fast`, which is what the pre-commit hook runs. A
push has a network by definition; a commit does not.

Exit: 0 no known vulnerabilities · 1 at least one · 2 the audit could not run.
A network failure is the third of those, never the first (STACK.md §8 H-1).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIP_AUDIT = ROOT / ".venv-audit" / "bin" / "pip-audit"
REQUIREMENTS = (
    ROOT / ".github" / "requirements" / "dev.txt",
    ROOT / ".github" / "requirements" / "audit.txt",
)

SETUP = (
    "python3 -m venv .venv-audit && .venv-audit/bin/pip install -r .github/requirements/audit.txt"
)


class CannotCheck(Exception):
    """The audit did not produce an answer. Distinct from producing a bad one."""


def _audit(label: str, args: list[str]) -> list[str]:
    """Run one pip-audit invocation. Returns the findings; raises if it could not run."""
    with tempfile.TemporaryDirectory(prefix="secrev-audit-") as tmp:
        report = Path(tmp) / "audit.json"
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                str(PIP_AUDIT),
                *args,
                "--format",
                "json",
                "--output",
                str(report),
                "--progress-spinner",
                "off",
            ],
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        stderr = proc.stderr.decode("utf-8", errors="replace")

        # The report file is what separates the two failures. pip-audit exits
        # non-zero both when it finds vulnerabilities and when it cannot reach
        # OSV; only the first produces a report. Reading the exit code alone
        # would report a dropped connection as a security finding, and a
        # `|| true` here would report it as a clean bill of health.
        if not report.is_file():
            raise CannotCheck(
                f"{label}: pip-audit exited {proc.returncode} without a report\n{stderr}"
            )
        try:
            parsed = json.loads(report.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise CannotCheck(f"{label}: report is not JSON — {exc}") from exc

    findings: list[str] = []
    for dep in parsed.get("dependencies", []):
        name = dep.get("name", "?")
        version = dep.get("version", "?")
        if dep.get("skip_reason"):
            # Not a pass. A dependency that could not be audited is reported as
            # such; pyproject's own package is the usual, and only, case.
            print(f"  skipped  {name} {version}: {dep['skip_reason']}")
            continue
        for vuln in dep.get("vulns", []):
            fixes = ", ".join(vuln.get("fix_versions", [])) or "no fixed version published"
            findings.append(f"{name} {version}  {vuln.get('id', '?')}  fix: {fixes}")
    return findings


def main() -> int:
    if not PIP_AUDIT.is_file():
        sys.stderr.write(f"pip-audit is not installed — cannot check.\nRun: {SETUP}\n")
        return 2

    jobs = [("declared dependencies (pyproject.toml)", ["."])]
    pinned = [str(path) for path in REQUIREMENTS if path.is_file()]
    if pinned:
        args = ["--no-deps"]
        for path in pinned:
            args += ["--requirement", path]
        jobs.append(("pinned toolchains (dev.txt, audit.txt)", args))

    findings: list[str] = []
    for label, args in jobs:
        print(f"  auditing {label}")
        try:
            findings.extend(f"{label}: {line}" for line in _audit(label, args))
        except CannotCheck as exc:
            sys.stderr.write(f"{exc}\n")
            sys.stderr.write(
                "\nThis is 'could not check', not 'nothing found'. Usual cause: no\n"
                "network, or the OSV service is unreachable. Re-run when it is.\n"
            )
            return 2

    if findings:
        sys.stderr.write("known vulnerabilities in declared dependencies (STACK.md §2.2):\n")
        for line in sorted(findings):
            sys.stderr.write(f"  {line}\n")
        sys.stderr.write(
            "\nBump the pin and record it, or state why the advisory does not apply.\n"
            "Suppressing one silently is the failure this project exists to notice.\n"
        )
        return 1

    print("no known vulnerabilities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
