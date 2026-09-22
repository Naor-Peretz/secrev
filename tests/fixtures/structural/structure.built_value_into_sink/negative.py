"""Negative fixture: the same sink, with a value nobody builds.

The call is identical and the argument is a literal, so nothing outside this
file decides any part of it. The rule asks whether a value was *built*, and the
answer here is no — which is why the fixture keeps `os.system`: a negative that
also removed the sink would pass without the interpolation test ever running.
"""

import os


def run_report():
    os.system("generate --target default")
