"""A package whose public surface is declared, and a reader of it that is not."""

from exports.render import render

__all__ = [
    "render",
]


def names():
    return list(__all__)
