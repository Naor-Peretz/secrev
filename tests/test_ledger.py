"""G-3 redaction, as a regression rather than as a claim.

`ledger.py` had no test module of its own until a second external review found
four credential shapes still reaching `match_excerpt`. It was exercised only
through the sweep and CLI goldens, which is coverage of the *path* rather than
of the rule: a golden asserts that today's bytes equal yesterday's, so a shape
the redactor never caught is a shape the golden happily pins as correct.

Each case below leaked when it was written. The controls beside them are the
M3.5 shapes, kept so that widening the rule cannot quietly narrow it.
"""

from __future__ import annotations

from secrev.ledger import WINDOW_RADIUS, excerpt, redact, window

# Not credential-shaped, deliberately. `gitleaks dir` reads the working tree and
# exempts only `tests/fixtures/`, so a realistic-looking secret here would fail
# the gate — and `.gitleaks.toml` is not widened to make a test pass
# (`CLAUDE.md`, "Working against the guards").
VALUE = "placeholder-not-a-real-value"


def test_a_password_in_url_userinfo_is_redacted() -> None:
    """`scheme://user:password@host`, and the one shape neither existing rule
    could see.

    There is no credential word anywhere in it, so the key rule never matched,
    and a password is almost never 32 characters, so the long-opaque rule's
    floor was never reached. Connection strings are among the commonest places
    a live credential is written down, which is what makes the gap expensive.
    """
    out = redact(f"conn = postgres://admin:{VALUE}@db/app")
    assert VALUE not in out
    assert "[REDACTED]" in out
    # The account name survives. It is not the secret, and an excerpt with both
    # halves gone stops telling a reviewer which account was involved.
    assert "admin" in out


def test_keys_that_name_a_credential_without_saying_password() -> None:
    """`PGPASS` and `private_key` name a credential and matched no alternative.

    The key rule was a list of words, and these two were not on it.
    """
    for line in (f"PGPASS={VALUE}", f"private_key = {VALUE}"):
        assert VALUE not in redact(line), line


def test_the_abbreviated_password_keys_are_redacted() -> None:
    """`pwd` and `pw`, and the reason this test names them literally.

    A previous commit message claimed both were fixed. They were not: `pwd` had
    been added only to the command-line flag rule (`--pwd X`), and `pw` not at
    all, so `pwd="..."` and `MYSQL_ROOT_PW=...` went through untouched.

    **The probe that cleared them failed the way this module already documents.**
    It used a 28-character value, and `=` is inside the long-opaque alphabet, so
    `pwd=<28 chars>` reached exactly 32 and the *generic* rule caught it — the
    same coincidence the test directly below was written to pin. A claim in a
    commit message is exactly as good as the check behind it, and that check was
    green for a reason unrelated to its subject.

    The two strings are the ones that message cited, verbatim, with a value
    short enough that the generic rule cannot reach them.
    """
    short = "abc12345"
    assert len(f"MYSQL_ROOT_PW={short}") < 32
    for line in (f'pwd="{short}"', f"MYSQL_ROOT_PW={short}", f"pw={short}"):
        assert short not in redact(line), line


def test_an_abbreviated_key_without_a_separator_is_left_alone() -> None:
    """The polarity control for the line above.

    `pwd` is also an ordinary shell command, and `pw` is two characters. Both
    sit inside `[A-Za-z0-9_.-]*`, so the guard against eating prose is the
    separator: a key names a credential only when something is being assigned
    to it.
    """
    line = "the pwd command prints a directory"
    assert redact(line) == line


def test_a_short_passphrase_is_redacted_by_the_key_rule_not_by_luck() -> None:
    """The case that *appeared* to pass, which is worse than one that failed.

    `passphrase=correct-horse-battery` was redacted before this change — but by
    the long-opaque rule, because `=` is inside its alphabet and the whole
    string happened to reach exactly 32 characters. One character shorter and
    it leaked. A short value is the control that tells the two rules apart.
    """
    short = "abcd1234"
    assert len(f"passphrase={short}") < 32
    assert short not in redact(f"passphrase={short}")


def test_a_quoted_value_is_redacted_to_its_closing_quote() -> None:
    """A space does not end a quoted value, and the value shape said it did.

    `[^\\s"',)]` stopped at the first space, so `password='hunter2 with space'`
    redacted the first word and printed the rest of the credential.
    """
    out = redact("password='first second third'")
    assert "second" not in out
    assert "third" not in out


def test_the_m35_shapes_still_redact() -> None:
    """The controls. Widening a rule is exactly when it can quietly narrow, and
    these four are the shapes the previous review paid for."""
    for line in (
        f"token={VALUE}",
        f"DB_PASSWORD={VALUE}",
        f'"api_key": "{VALUE}"',
        f"Authorization: Bearer {VALUE}",
    ):
        assert VALUE not in redact(line), line


def test_ordinary_text_is_not_mangled() -> None:
    """The polarity control. Over-redaction is the cheaper error and is chosen
    deliberately, but a rule that redacts prose is one people route around."""
    line = "the password policy is documented in SECURITY.md"
    assert redact(line) == line


def test_the_window_is_not_redacted() -> None:
    """FR-4.6, and the reason redaction may be tuned at all.

    `window_sha256` is taken over the window, and the window is hashed
    unredacted. If redaction reached it, every candidate id would depend on the
    redaction rules — so widening them, as this change does, would re-identify
    candidates whose content never changed and expire verifications that are
    still good.
    """
    lines = [f"token={VALUE}"] * (WINDOW_RADIUS + 2)
    assert VALUE in window(lines, 0)


def test_redaction_runs_before_truncation() -> None:
    """M3.5 B2, kept because the widened rule re-enters the same code path.

    The excerpt is cut twice — a ±24 margin and a 200-character cap — and the
    long-opaque rule keys on length, so redacting after either cut measures a
    credential that has already been shortened out of its own floor.
    """
    secret = "A" * 40
    line = f"x = {secret}"
    assert secret not in excerpt(line, 4, 4 + len(secret))
