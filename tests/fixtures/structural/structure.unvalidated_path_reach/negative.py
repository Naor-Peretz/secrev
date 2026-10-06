"""Negative fixture: the validator is called, in the argument itself.

Written as one expression rather than as `safe = ensure_within(...)` followed by
`open(safe)` on purpose. The two-line form would also be quiet, but for a
weaker reason — `safe` is not a parameter, so the rule would skip it without
ever consulting the validator list. This form puts both parameters inside the
call, so the candidate is suppressed by the validating call and by nothing else,
which is the branch A2 asks to see exercised.

`ensure_within` is a claim, not a proof: the rule suppresses on the name, and a
record it suppresses is one the tool is admitting it cannot judge. The dataflow
that would settle it is FR-3.7's, in v2.
"""


def load_config(name, root):
    with open(ensure_within(root, name)) as handle:
        return handle.read()
