"""No shipped rule takes superlinear time on a line the target chose.

This replaces a single-pattern check that passed for two reasons unrelated to
its claim, and both are worth keeping written down.

**It measured one pattern.** `log.sensitive` was the one the M3.5 review had
demonstrated, so it was the one that got a `{0,400}` bound and the one the test
covered. Three others had the identical shape — an unbounded `[^x]*` reachable
from a start position the target can repeat — and stayed quadratic behind a
green check. The fix was applied to the example rather than to the class.

**It used `re.search`.** That returns at the first match, so for a pattern that
matches early it measures one scan. `sweep.py:78` uses `finditer`, because D-6
requires that two hits on one line stay two hits, and `finditer` pays the retry
cost at every start position. Under `search`, `deser.unsafe` measured 0.000 s
and looked linear; under `finditer` the same line took 0.692 s and scaled 4.1x.
A probe that models the cheap call answers a question nobody asked.

So: every pattern in the catalog and every surface kind, under `finditer`, on a
line built to maximise start positions.

The bound is absolute rather than a ratio. A ratio is the sharper instrument in
principle, but these timings are noise-dominated once a rule is linear — the
same run measured 0.1x to 2.2x across the fast patterns — so a ratio assertion
would flake without ever being wrong about anything. An absolute ceiling on a
large line separates cleanly instead: measured after the bounds, the slowest
rule here is about 0.3 s, while any of the four quadratic ones would have taken
roughly 15 s on this input.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from secrev.catalog import load
from secrev.kinds import load_file
from secrev.sweep import sweep

ROOT = Path(__file__).resolve().parent.parent
PACKS = sorted((ROOT / "patterns").glob("*.yaml"))
KINDS_FILE = ROOT / "surfaces" / "_surfaces.yaml"

# Roughly 200 KB on one line. Large enough that a quadratic rule is unmistakable
# and small enough that the whole module stays under a second.
LINE_BYTES = 200_000

# Generous by design. This asserts the absence of a quadratic blowup, not a
# performance target; a tight bound fails on a loaded CI runner and teaches
# people to delete the test rather than read it.
CEILING_SECONDS = 2.0

# One adversarial seed per rule: a token the rule can *begin* matching at,
# repeated. The cost being measured is the outer scan retrying from every one of
# those positions, so a seed that offers only one start measures nothing.
#
# Hand-written rather than derived, and the coverage test below makes that safe:
# a rule added without a seed turns this module red instead of silently going
# unmeasured. That is the shape `test_every_pattern_has_a_fixture_directory`
# already uses, and the reason is the same — the check that matters is the one
# that fails when something is *added*.
SEEDS = {
    # Catalog
    "net.bind_all": "0.0.0.0 ",
    "net.fetch_exec": "curl ",
    "log.sensitive": "print(",
    "fs.agent_config_write": " .claude",
    "exec.shell_true": "subprocess.run(",
    "exec.dynamic": "eval(",
    "deser.unsafe": "yaml.load(",
    "tls.verify_off": "verify=False ",
    "path.traversal": "Path(",
    # Surface kinds. Most are `^`-anchored, which allows one start per line and
    # so is linear by construction — measured anyway rather than reasoned about,
    # because "anchored so it must be fine" is the argument that let four
    # patterns through, and an unanchored kind added later is exactly what this
    # is here to catch.
    "surface.mcp_tool": "@a.tool ",
    "surface.mcp_tool_listing": "@a.list_tools ",
    "surface.mcp_server": '"command":',
    "surface.hook_binding": '"Pre": [',
    "surface.cli_command": 'a = "m:f" ',
    "surface.public_export": "__all__ = ",
    "surface.skill_activation": "description: x",
}


def rules() -> list[tuple[str, object]]:
    """Every shipped rule that matches text: catalog patterns and surface kinds.

    Both, in one list, because they are two halves of one claim. The kinds are
    as capable of hanging a run as the patterns are — `surfaces.py` applies them
    to every line of every file a kind's globs select — and a timing check that
    covered only `patterns/` would leave `surfaces/` in exactly the state the
    catalog was in before this milestone.
    """
    out: list[tuple[str, object]] = [(p.id, p.regex) for p in load(PACKS).patterns]
    out += [(k.id, k.declaration) for k in load_file(KINDS_FILE).kinds]
    return out


def rule_ids() -> list[str]:
    return [rule_id for rule_id, _ in rules()]


def test_every_shipped_rule_has_an_adversarial_seed() -> None:
    """The assertion that makes the parametrised check honest.

    Without it, a pattern or kind added later is simply absent from `SEEDS` and
    therefore absent from the timing check, and nothing says so. A rule nobody
    measured is an assumption, which is H-8 applied to performance.
    """
    missing = [rule_id for rule_id in rule_ids() if rule_id not in SEEDS]
    assert not missing, f"rules with no timing seed: {missing}"

    known = set(rule_ids())
    orphans = sorted(set(SEEDS) - known)
    assert not orphans, f"seeds naming no rule: {orphans}"


@pytest.mark.parametrize("rule_id", rule_ids())
def test_no_rule_goes_superlinear_on_a_crafted_line(rule_id: str) -> None:
    regex = next(rx for name, rx in rules() if name == rule_id)
    seed = SEEDS[rule_id]
    line = seed * (LINE_BYTES // len(seed))

    start = time.perf_counter()
    # Consumed, not just created: `finditer` is lazy, and timing the generator's
    # construction would measure nothing at all — a third way for this check to
    # be green without having run.
    sum(1 for _ in regex.finditer(line))  # type: ignore[attr-defined]
    elapsed = time.perf_counter() - start

    assert elapsed < CEILING_SECONDS, (
        f"{rule_id}: {len(line)} characters took {elapsed:.2f}s — "
        f"bound an unbounded quantifier rather than raising this ceiling"
    )


def test_a_full_sweep_is_linear_in_the_length_of_a_crafted_line(tmp_path: Path) -> None:
    """The level above the rules, which the tests above structurally cannot see.

    Every rule was linear and `secrev sweep` was still quadratic. The cost had
    moved out of the catalog and into identity: each candidate's window is ±20
    lines, which on a file that is one enormous line is approximately the whole
    line, and that window was rebuilt once per match and then hashed twice.
    K candidates times N characters — quadratic again, with nothing in
    `patterns/` to blame.

    Measured before the fix: 0.37 s, 1.17 s, 4.06 s at 40/80/160 KB — a ratio of
    about 3.5x for each doubling. After it: 0.13 s, 0.25 s, 0.50 s, a flat 2.0x.

    So this asserts the *shape*, not a duration. A ceiling in seconds would pass
    on a fast runner while the curve was still quadratic, which is how the
    previous check stayed green through exactly this defect; the ratio is what
    distinguishes the two. The bound is loose because timing on a shared runner
    is noisy, and 3.0 still separates 2.0 from 3.5 with room on both sides.
    """
    catalog = load(PACKS)
    seed = "yaml.load("

    def elapsed_for(size: int) -> float:
        target = tmp_path / f"t{size}"
        target.mkdir()
        (target / "big.py").write_text(seed * (size // len(seed)) + "\n", encoding="utf-8")
        start = time.perf_counter()
        hits = sweep(target, catalog)
        taken = time.perf_counter() - start
        assert hits, "the crafted line produced no candidates — the probe measures nothing"
        return taken

    small = elapsed_for(40_000)
    large = elapsed_for(80_000)

    # A floor, because dividing two sub-millisecond numbers measures the clock.
    if small < 0.01:  # pragma: no cover - only on an implausibly fast machine
        pytest.skip(f"baseline too small to compare: {small:.4f}s")

    ratio = large / small
    assert ratio < 3.0, (
        f"doubling the line multiplied the sweep by {ratio:.1f}x "
        f"({small:.2f}s then {large:.2f}s) — linear is ~2x. "
        "The rules are timed above; this is the pipeline around them."
    )
