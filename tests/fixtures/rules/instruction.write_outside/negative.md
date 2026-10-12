# setup, the version that stays inside

Everything this skill writes goes under the workspace the host hands it, and
the path is reported before the first write.

Nothing is placed in a shell startup file or a client configuration directory.
Persisting past the session is a capability, not a convenience.

If the workspace cannot be created, stop and say which path failed.
