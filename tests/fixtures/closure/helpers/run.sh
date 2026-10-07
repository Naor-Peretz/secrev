#!/bin/sh
# FR-1.2's bundled script. It does nothing on purpose: the closure asks what an
# artifact can pull in, not what a script does once it runs — that is the
# pattern and structural sources' question, and they are peers (P11).
set -eu
echo "would unpack payload.bin" >&2
