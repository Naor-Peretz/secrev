"""Positive fixture: a resource created, then given its permissions later.

Between `mkstemp` and `chmod` the file exists with whatever the process umask
allowed, and the token is already written into it. That window is the question
the rule asks.
"""

import os
import tempfile


def write_token(directory, token):
    handle, path = tempfile.mkstemp(dir=directory)
    os.write(handle, token.encode("utf-8"))
    os.close(handle)
    os.chmod(path, 0o600)
    return path
