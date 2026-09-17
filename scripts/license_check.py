"""License allowlist over the installed dependency set.

STACK.md §2.2. Every dependency arrives with terms attached, and the terms are
a property nobody re-reads once the package is installed. This is the check
that reads them.

Allowlist, not denylist (P3): a licence nobody has considered fails, and the
message names it so that a person decides. The failure mode of the other
polarity is a package with an unusual licence sliding in because it was not on
a list of the bad ones.

Runs `pip-licenses` from `.venv-audit` against `.venv` — the audit tooling
inspects the project environment from outside it, so its own 29 transitive
packages never enter the environment the gate types-checks and tests against
(.github/requirements/audit.txt).

Exit: 0 every licence allowed · 1 a licence outside the allowlist · 2 the
check could not run. Never collapse the last two — "I did not check" and
"I checked and it is fine" are different states (STACK.md §8 H-1).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
PIP_LICENSES = ROOT / ".venv-audit" / "bin" / "pip-licenses"

SETUP = (
    "python3 -m venv .venv-audit && .venv-audit/bin/pip install -r .github/requirements/audit.txt"
)

# SPDX identifiers, with the reason for anything that is not a plain permissive
# licence. Adding an entry is a decision; make it deliberately.
ALLOWED = {
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
    "Python-2.0",
    "PSF-2.0",  # typing_extensions
    # MPL-2.0 (pathspec, via mypy) is weak copyleft at file granularity: it
    # reaches modified copies of the licensed files themselves and no further.
    # secrev imports it and does not modify it, so nothing here is affected.
    # It is allowed knowingly rather than by omission.
    "MPL-2.0",
}

# pip-licenses reports whatever string the distribution's metadata carries, and
# that is a mix of SPDX identifiers and legacy trove classifiers. Normalising
# is the whole difficulty of this check: the alternative is an allowlist that
# silently misses "MIT License" because it holds "MIT".
ALIASES = {
    "mit license": "MIT",
    "mit": "MIT",
    # The trove classifier does not say which BSD. Read as the 3-clause form,
    # which is the stricter of the two common ones.
    "bsd license": "BSD-3-Clause",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "isc license (iscl)": "ISC",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "python software foundation license": "PSF-2.0",
    "the unlicense (unlicense)": "Unlicense",
}

# The project itself, which an editable install reports twice. It is skipped
# because this allowlist governs what may be *depended on*, and secrev's own
# terms are a different question with a different answer (STACK.md §10:
# PolyForm Noncommercial 1.0.0, which is deliberately not in ALLOWED — nothing
# here may depend on a noncommercial package). Skipped, but named in the
# output: silence about it would be the wrong kind.
SELF = "secrev"


def _normalise(raw: str) -> list[list[str]]:
    """Licence groups that must *each* be satisfied, each a list of
    alternatives of which *one* must be allowed.

    `;` and `,` separate licences that all apply — they are how `pip-licenses`
    joins multiple trove classifiers. `" OR "` offers a choice, and the
    licensee takes it.

    Until M3.5 all three were split identically into one flat list, and the
    caller accepted when *any* entry was allowed. So `"MIT, GPL-3.0"` passed on
    the strength of MIT alone: a check admitting exactly what it exists to
    refuse, with every gate run green. `"MIT License; BSD License"` is two
    groups of one; `"MIT OR Apache-2.0"` is one group of two.
    """
    groups = [raw.strip()]
    for separator in (";", ","):
        expanded: list[str] = []
        for group in groups:
            expanded.extend(group.split(separator))
        groups = expanded

    out: list[list[str]] = []
    for group in groups:
        alternatives = [
            ALIASES.get(part.strip().lower(), part.strip())
            for part in group.split(" OR ")
            if part.strip()
        ]
        if alternatives:
            out.append(alternatives)
    return out


def is_allowed(raw: str) -> bool:
    """Whether a licence expression is acceptable under `ALLOWED`.

    Extracted from `main` in M3.5-013 so the decision can be tested at all: it
    was inline in a function that shells out to `pip-licenses`, so nothing could
    reach it without the audit venv installed.

    Every group must be satisfied and one alternative within a group suffices,
    which is what `;`/`,` and `" OR "` actually mean. This accepted when *any*
    candidate anywhere was allowed until M3.5, so `"MIT, GPL-3.0"` passed on
    MIT alone.

    **The empty case is guarded explicitly, and that is not decoration.** The
    old rule was `any(...)`, and `any([])` is `False`, so a package declaring no
    licence was refused for free. The new rule is `all(...)`, and `all([])` is
    `True` — so without this line, tightening the check would have silently
    turned "no licence stated" into "acceptable".
    """
    groups = _normalise(raw)
    if not groups:
        return False
    return all(any(candidate in ALLOWED for candidate in group) for group in groups)


def _collect() -> list[dict[str, str]] | None:
    if not PIP_LICENSES.is_file():
        sys.stderr.write(f"pip-licenses is not installed — cannot check.\nRun: {SETUP}\n")
        return None
    if not VENV_PY.is_file():
        sys.stderr.write(
            ".venv does not exist, so there is no dependency set to read licences from.\n"
            "Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'\n"
        )
        return None

    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [str(PIP_LICENSES), "--python", str(VENV_PY), "--format=json"],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"pip-licenses exited {proc.returncode} — cannot check.\n")
        sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))
        return None
    try:
        parsed = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"pip-licenses produced output that is not JSON — cannot check: {exc}\n")
        return None
    if not isinstance(parsed, list):
        sys.stderr.write("pip-licenses produced JSON that is not a list — cannot check.\n")
        return None
    return parsed


def main() -> int:
    packages = _collect()
    if packages is None:
        return 2

    disallowed: list[str] = []
    checked = 0
    for entry in packages:
        name = str(entry.get("Name", "?"))
        raw = str(entry.get("License", "UNKNOWN"))
        if name == SELF:
            continue
        checked += 1
        if not is_allowed(raw):
            disallowed.append(f"{name} {entry.get('Version', '?')}: {raw}")

    if disallowed:
        sys.stderr.write("licences outside the allowlist (STACK.md §2.2):\n")
        for line in sorted(disallowed):
            sys.stderr.write(f"  {line}\n")
        sys.stderr.write(
            "\nEither the dependency goes, or the licence is added to ALLOWED in\n"
            "scripts/license_check.py with the reason it is acceptable. Do not add\n"
            "one without reading it.\n"
        )
        return 1

    print(
        f"{checked} dependencies, every licence allowed "
        f"({SELF} skipped — its own terms are STACK.md §10)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
