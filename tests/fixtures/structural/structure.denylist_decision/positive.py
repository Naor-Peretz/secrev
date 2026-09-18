"""Positive fixture: a gate that names what is refused.

Everything the author did not think of returns True. `/etc/../etc/passwd`,
`/proc/self/environ`, a symlink to any of them — none of them are listed, so all
of them are allowed. That is P3's argument in five lines.

The collection is written inline rather than held in a module constant, because
the rule asks about a literal collection in the body: a name bound elsewhere is
a value this milestone cannot follow (FR-3.7).
"""


def is_allowed_path(candidate):
    if candidate in ("/etc/passwd", "/etc/shadow", "/root/.ssh/id_rsa"):
        return False
    return True
