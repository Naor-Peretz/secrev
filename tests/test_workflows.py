"""The CI workflows, checked here because nothing else has ever checked them.

There is no git remote, so these files have never run. Everything they assert
about this project is therefore untested, and so is the project's claim about
*them*: `CLAUDE.md` says "Every action is pinned to a commit SHA, never a tag"
and until now nothing enforced it. A supply-chain control that exists only as a
sentence in a document is the shape this repository distrusts everywhere else.

That claim is the substance here. `@v4` resolves to whatever the maintainer
last pointed it at — a remote code reference, with access to the checkout, that
can change with no diff in this repository to explain it. A SHA cannot.

The rest is the cheap half: YAML that parses, `needs:` that resolve, and
`run:` steps naming scripts that exist. None of it is clever, and all of it is
the class of defect that otherwise surfaces as a red first push for a silly
reason, on the day someone finally adds a remote.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

# `owner/repo@<40 hex>`, optionally with a path. A tag or branch is anything else.
PINNED = re.compile(r"^[^@]+@[0-9a-f]{40}$")

# Local composite actions and Docker refs are not third-party code fetched by
# reference, so the pin rule does not reach them.
LOCAL = ("./", "docker://")


def load(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), f"{path.name}: top level is not a mapping"
    return parsed


def jobs(document: dict[str, Any]) -> dict[str, Any]:
    found = document.get("jobs", {})
    assert isinstance(found, dict)
    return found


def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    found = job.get("steps", [])
    return [step for step in found if isinstance(step, dict)]


def test_there_are_workflows_to_check() -> None:
    """Guards the guard. Every assertion below iterates over this list, so an
    empty one would make the whole file pass while checking nothing (H-1)."""
    assert len(WORKFLOWS) >= 3


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_parses(path: Path) -> None:
    assert jobs(load(path)), f"{path.name}: no jobs"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_sha(path: Path) -> None:
    """`CLAUDE.md`'s claim, now enforced.

    Each `uses:` is third-party code with access to the checkout. A tag is a
    reference the other side can repoint at any time, with nothing in this
    repository changing to record it — which is the same objection STACK.md
    §2.2 makes to installing gitleaks through an action rather than a
    hash-verified tarball.
    """
    unpinned: list[str] = []
    for name, job in jobs(load(path)).items():
        for step in steps(job):
            uses = step.get("uses")
            if not isinstance(uses, str) or uses.startswith(LOCAL):
                continue
            if not PINNED.match(uses):
                unpinned.append(f"{name}: {uses}")
    assert not unpinned, f"{path.name}: actions not pinned to a SHA: {unpinned}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_job_dependencies_resolve(path: Path) -> None:
    """A `needs:` naming a job that does not exist fails the whole run at parse
    time on GitHub, which is a poor way to discover a typo."""
    defined = jobs(load(path))
    for name, job in defined.items():
        needs = job.get("needs", [])
        for dependency in [needs] if isinstance(needs, str) else needs:
            assert dependency in defined, f"{path.name}: {name} needs unknown job {dependency}"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_referenced_scripts_exist(path: Path) -> None:
    """Every `scripts/…` path a `run:` block mentions is really there.

    Renaming a script and missing a workflow is invisible until the run, and
    the failure reads as a broken gate rather than a stale reference.
    """
    text = path.read_text(encoding="utf-8")
    missing = [
        reference
        for reference in sorted(set(re.findall(r"scripts/[A-Za-z0-9_./-]+", text)))
        if not (ROOT / reference).exists()
    ]
    assert not missing, f"{path.name}: references scripts that do not exist: {missing}"
