"""Negative fixture: the same five lines with the membership reversed.

This is an allowlist. Everything the author did not think of returns False, so
an input nobody listed is refused — it fails closed, which is the remedy rather
than the defect.

Syntactically it is almost identical to the positive: same name shape, same
literal collection, same boolean returns. Only the direction of the membership
differs, and that is the whole distinction the rule has to make. A rule that
fired here would put a candidate on every allowlist in every codebase, and A2
exists so that this fixture, not a reviewer, is what proves it does not.
"""


def is_allowed_path(candidate):
    if candidate not in ("/srv/data", "/srv/cache", "/srv/public"):
        return False
    return True
