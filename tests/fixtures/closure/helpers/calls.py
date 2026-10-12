"""A token followed by `(` is a call, not a path.

Every line below matched the reference extractor until M5 measured three real
targets: `.json`, `.yaml` and `.toml` are all real file suffixes, so an attribute
spelled like one looked exactly like a filename. The negative fixture for that
shape is this file producing no unresolved reference.

The last line is the permit, and it matters as much: a file genuinely named
inside a call's argument is still a reference, because the argument is a separate
token with its own boundaries.
"""


def read(response: object, loader: object) -> object:
    body = response.json()
    config = loader.yaml()
    settings = loader.toml()
    del body, config, settings
    return open("progressive.md").read()
