"""Negative fixture: the permission is set *at* creation, so there is no window.

The later `chmod` is redundant rather than wrong, and it is here on purpose: the
rule must not fire on a body that contains a permission call, it must fire on a
body where the permission arrived too late. A fixture without the `chmod` would
pass for the wrong reason — there would be nothing for the rule to match at all,
and the fused-keyword branch would never be exercised.
"""

import os


def write_token(path, token):
    handle = os.open(path, os.O_WRONLY | os.O_CREAT, mode=0o600)
    os.write(handle, token.encode("utf-8"))
    os.close(handle)
    os.chmod(path, 0o600)
    return path
