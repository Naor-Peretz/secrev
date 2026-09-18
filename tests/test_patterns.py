"""Every shipped pattern has a positive and a negative fixture, and both do
what they claim. STACK.md §9, BRIEF_M1.md §6.

§9's rule is that "a pattern with no negative fixture will drift into
over-matching and nobody will notice". The test that enforces it has to be the
one that fails when a pattern is *added*, not only when one is edited — so the
coverage assertion below compares the catalog against the fixture directory in
both directions. A pattern with no fixtures fails; a fixture directory naming
no pattern fails too, because that is what an id rename leaves behind.

Matching here is `regex.search` against one line at a time, which is the M1
contract (§4: line-oriented only). `sweep.py` matches the same way; the golden
test covers that path end to end.

This file found a real defect while being written. `net.bind_all` was
`0\\.0\\.0\\.0` with no lookaround, which matches inside `10.0.0.0/8` — a
private range, not a bind to every interface. The negative fixture is what
surfaced it, one commit after the pattern was written and before it had ever
been run against anything real.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from secrev.catalog import Catalog, Pattern, load

ROOT = Path(__file__).resolve().parent.parent
PACKS = sorted((ROOT / "patterns").glob("*.yaml"))
# `fixtures/rules/`, not `fixtures/patterns/`. The harness guard matches the
# protected catalog directory with an unanchored glob (STACK.md §8 H-5), so a
# fixture tree named `patterns` reads to it as the catalog itself. It fails
# closed, which is the right direction, but a denial that names the wrong
# directory costs a reader time — and the fixtures are for rules, so the name
# is better anyway.
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rules"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load(PACKS)


def fixture_file(rule_id: str, kind: str) -> Path:
    matches = sorted((FIXTURES / rule_id).glob(f"{kind}.*"))
    assert len(matches) == 1, f"{rule_id}: expected exactly one {kind} fixture, found {matches}"
    return matches[0]


def hits(pattern: Pattern, text: str) -> list[str]:
    """Lines the pattern matches. Line-oriented, as §4 requires."""
    return [line for line in text.splitlines() if pattern.regex.search(line)]


def pattern_ids() -> list[str]:
    return [pattern.id for pattern in load(PACKS).patterns]


def test_the_shipped_catalog_loads_and_is_the_expected_size() -> None:
    """Nine, not eight — `path.traversal` was added by owner decision because
    §7's last DoD item requires flagging a path-validation region and no
    original seed pattern touched path handling (§6)."""
    loaded = load(PACKS)
    assert len(loaded.patterns) == 9
    # Bumped in M3.5 with `log.sensitive`'s `{0,400}` bound, and again when the
    # four remaining quadratic patterns gained the same bound;
    # `patterns/_base.yaml` carries both reasons. Pinning the literal here is
    # deliberate: a catalog version change expires verifications (FR-4.6), so it
    # should cost an edit to a test rather than pass unnoticed.
    assert loaded.version == "2026.09.3"


def test_every_pattern_has_a_fixture_directory(catalog: Catalog) -> None:
    missing = [pattern.id for pattern in catalog.patterns if not (FIXTURES / pattern.id).is_dir()]
    assert not missing, f"patterns with no fixtures: {missing}"


def test_every_fixture_directory_names_a_real_pattern(catalog: Catalog) -> None:
    """The other direction, which is the one that catches a rename. An orphan
    fixture directory is a pattern whose coverage silently stopped applying."""
    known = {pattern.id for pattern in catalog.patterns}
    orphans = [item.name for item in FIXTURES.iterdir() if item.is_dir() and item.name not in known]
    assert not orphans, f"fixture directories naming no pattern: {orphans}"


@pytest.mark.parametrize("rule_id", pattern_ids())
def test_positive_fixture_matches(rule_id: str, catalog: Catalog) -> None:
    pattern = next(item for item in catalog.patterns if item.id == rule_id)
    text = fixture_file(rule_id, "positive").read_text(encoding="utf-8")
    assert hits(pattern, text), f"{rule_id}: positive fixture produced no match"


@pytest.mark.parametrize("rule_id", pattern_ids())
def test_negative_fixture_does_not_match(rule_id: str, catalog: Catalog) -> None:
    """The assertion that stops over-matching. It reports the offending lines
    rather than just failing, because "the negative fixture matched" without
    saying where sends a reader to re-derive what the test already knew."""
    pattern = next(item for item in catalog.patterns if item.id == rule_id)
    text = fixture_file(rule_id, "negative").read_text(encoding="utf-8")
    matched = hits(pattern, text)
    assert not matched, f"{rule_id}: negative fixture matched on {matched}"


def test_python_patterns_are_scoped_to_python(catalog: Catalog) -> None:
    """§4: a language list reduces false positives, it is not a prerequisite.
    The scoping is what stops `shell=True` in a prose file about subprocess
    entering the ledger as a code-layer candidate."""
    scoped = {pattern.id for pattern in catalog.patterns if pattern.languages == ("python",)}
    assert scoped == {
        "exec.shell_true",
        "exec.dynamic",
        "deser.unsafe",
        "tls.verify_off",
        "path.traversal",
    }


def test_precision_low_is_present_and_is_not_a_defect(catalog: Catalog) -> None:
    """§4 calls `precision: low` first-class and expected. Asserted so that a
    later tidy toward "high precision everywhere" fails loudly — under P4 every
    candidate is resolved anyway, so a false positive costs a paragraph while a
    miss is a silent gap."""
    low = {pattern.id for pattern in catalog.patterns if pattern.precision == "low"}
    assert low == {"log.sensitive", "path.traversal"}


def test_agent_config_rule_is_case_insensitive(catalog: Catalog) -> None:
    """STACK.md §4 makes this a finding class rather than portability: on macOS
    `.CLAUDE` and `.claude` are one directory and on Linux they are two, so a
    case-sensitive rule misses on the platform where the write succeeds."""
    pattern = next(item for item in catalog.patterns if item.id == "fs.agent_config_write")
    assert pattern.regex.search('open(".CLAUDE/settings.json", "w")')
    assert pattern.regex.search('open(".claude/settings.json", "w")')


def test_log_sensitive_still_sees_a_credential_inside_a_nested_call(catalog: Catalog) -> None:
    """The regression two rejected M3.5 fixes would have introduced, and which
    no fixture in this repository could have caught.

    `log.sensitive` was quadratic because `[^)\\n]*` let every `print(` start
    position consume the whole line. The obvious repair — excluding `(` as well
    — is linear, and agrees with all seven shipped fixtures, and silently stops
    matching every nested call. `print(sanitize(password))` is probably the
    most likely real spelling of this finding, because a credential reaching a
    log call has usually been passed through something first.

    The fixtures agreed with the broken candidate, so they were not the control
    here. This is: a future optimisation that reintroduces the bug has to turn
    this red before it can ship.
    """
    rule = next(item for item in catalog.patterns if item.id == "log.sensitive")
    for line in (
        "print(sanitize(password))",
        "logger.info(mask(token))",
        "logger.debug(fmt(str(api_key)))",
        'console.log("ctx", redact(secret))',
    ):
        assert rule.regex.search(line), line


def test_log_sensitive_does_not_go_superlinear_on_a_crafted_line(catalog: Catalog) -> None:
    """DoD C3: a crafted line cannot make the shipped catalog take superlinear
    time, within a stated bound and a generous margin.

    The adversarial shape is not a nested quantifier — `log.sensitive` never
    had one. It is many matching start positions with no `)` to stop
    consumption, since `re.search` retries the whole pattern from every one of
    them: K starts each scanning N characters is O(N*K).

    Measured before the `{0,400}` bound: 185.72 ms at 9,600 bytes, 11.4 s at
    76,800, which extrapolates to roughly 48 minutes on 1 MB. After it, this
    1.2 MB line measures about 1.9 s.

    The margin is deliberately wide. This asserts the absence of a quadratic
    blowup, not a performance target, and a tight bound would fail on a loaded
    CI runner and teach people to delete the test rather than read it.
    """
    rule = next(item for item in catalog.patterns if item.id == "log.sensitive")
    line = "print(" * 200_000

    start = time.perf_counter()
    rule.regex.search(line)
    elapsed = time.perf_counter() - start

    assert elapsed < 10.0, f"a 1.2 MB crafted line took {elapsed:.2f}s"


def test_safe_loader_spellings_do_not_match_deser_unsafe(catalog: Catalog) -> None:
    """The negative lookahead STACK.md §2 records as the reason the third-party
    `regex` package was not needed: this wants lookahead, not the
    variable-length lookbehind an earlier draft claimed."""
    pattern = next(item for item in catalog.patterns if item.id == "deser.unsafe")
    assert not pattern.regex.search("config = yaml.safe_load(text)")
    assert not pattern.regex.search("config = yaml.load(text, Loader=yaml.SafeLoader)")
    assert not pattern.regex.search("config = yaml.load(text, Loader=SafeLoader)")
    assert pattern.regex.search("config = yaml.load(text)")
