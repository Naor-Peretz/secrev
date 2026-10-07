# telemetry, the version that sends nothing

This skill makes no network call at all. The documentation for the upstream
format lives at https://spec.example.invalid/format, which is a reference and
not a destination.

Credentials are never read. Where one would be needed, the skill stops and
says which operation wanted it.

Everything stays on the machine, and the summary names the files it read.
