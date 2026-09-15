# Resolve first, then confine. The check runs against the path that
# will actually be opened rather than against the string that was
# handed in, which is the difference the rule's question asks about.
candidate = (BASE / name).resolve()
if not candidate.is_relative_to(BASE):
    raise ValueError("escapes the base directory")
text = candidate.read_text(encoding="utf-8")
