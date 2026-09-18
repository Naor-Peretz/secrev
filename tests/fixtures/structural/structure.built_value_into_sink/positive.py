"""Positive fixture: a command built by concatenation, executed as a string.

`name` is joined into the command text, so whatever `name` contains is part of
the command. A semicolon in it is a second command.
"""

import os


def run_report(name):
    os.system("generate --target " + name)
