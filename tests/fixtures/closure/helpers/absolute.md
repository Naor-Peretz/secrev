# absolute and home-relative references

Three shapes the bare-token pattern cannot see at all, because its left guard
blocks a token preceded by `/` and no token may begin with `~`. Each leaves the
target by definition, so each is an escaping reference rather than a file the
tree is missing: the finding is that the artifact reads something outside
itself, and where that something lives is the reviewer's next question.

The host configuration this artifact expects is at ~/.claude/settings.json.
That is the agent-config shape, and the one an agentic artifact is likeliest to
name — a write to it is a finding class of its own.

Machine-wide configuration is read from /etc/app/config.yaml, which is the
absolute shape with a suffix.

A key with no extension at all: ~/.ssh/id_rsa. A suffix requirement would have
recognised the two above and missed this one, which is why this shape carries
none — and it is the shape whose consequences are worst, since nothing about
the filename says it is a file.

Four more spellings of the same thing, each rooted somewhere other than this
tree. A shell variable: $HOME/.claude/settings.json. A braced one:
${XDG_CONFIG_HOME}/app/conf.toml. A Windows environment variable:
%APPDATA%\Claude\config.json. And a Windows drive: C:\Users\me\notes.md.

The two Windows forms are here for a reason worth keeping: they carry no forward
slash, so the absolute shape cannot see them, and the bare-token pattern used to
match their *last segment* — after which the artifact claimed this target was
missing a file by that name. A missing record is a gap; that one was false.
(Naming the segment here would have produced exactly the record this paragraph
describes, which is the second time a negative case in this file has needed
rewording to stop demonstrating the opposite of its point.)

Two negatives, in this file so they are demonstrated rather than described. A
permission glob such as **/.env is not an absolute path and must not be read as
a reference to the dot-env file at the filesystem root. (That second phrasing is
deliberate: an earlier draft of this paragraph spelled the path out, and the
extractor was right to read it as a reference — a negative case whose own
explanation is a positive case demonstrates nothing.) And a URL already claims
its own path, so https://example.invalid/etc/app/config.yaml is one reference
and not two.
