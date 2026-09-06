"""A module whose filename is not ASCII.

STACK.md §9 requires at least one, and it is here rather than in a runtime
tree because the point is that it survives being committed, cloned and checked
out — which is where APFS hands back NFD and ext4 hands back what was written.
"""

GREETING = "héllo wörld"


def greet(name: str) -> str:
    return f"{GREETING}, {name}"


# A candidate lives in this file on purpose. STACK.md §9 requires a golden test
# to run against a non-ASCII filename, and a file that matches nothing never
# reaches the golden at all — the requirement would have been satisfied on
# paper by a fixture the generator never emitted a record for. The `file` field
# below is the NFC-normalised path, which is the value that has to agree
# between APFS and ext4.
def load_profile(directory: str, name: str) -> str:
    return open(os.path.join(directory, name)).read()
