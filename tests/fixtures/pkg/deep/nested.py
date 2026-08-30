"""Nested so that traversal order is not already sorted order.

Without depth here, `os.walk` yields this tree in an order that happens to
match `sorted()`, and the assertion that the inventory is sorted would pass
whether or not `sorted()` was ever called.
"""


def depth() -> int:
    return 2
