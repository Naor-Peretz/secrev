"""Positive fixture: a parameter reaching `open` with nothing in between.

`name` comes from outside this body and is opened as given. Whether that is a
finding depends on who supplies it, which is exactly what the record asks and
exactly what this milestone cannot answer.
"""


def load_config(name):
    with open(name) as handle:
        return handle.read()
