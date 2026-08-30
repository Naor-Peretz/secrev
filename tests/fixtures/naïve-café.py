"""A module whose filename is not ASCII.

STACK.md §9 requires at least one, and it is here rather than in a runtime
tree because the point is that it survives being committed, cloned and checked
out — which is where APFS hands back NFD and ext4 hands back what was written.
"""

GREETING = "héllo wörld"


def greet(name: str) -> str:
    return f"{GREETING}, {name}"
