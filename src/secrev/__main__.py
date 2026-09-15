"""`python -m secrev`.

Not in `BRIEF_M1.md` §2's deliverable tree, and required regardless: both
`scripts/determinism_check.py` and the `catalog` job in `.github/workflows/ci.yml`
invoke the tool this way rather than through the console script, because
neither can rely on `.venv/bin/secrev` being on `PATH`.

Without this file the CI job greps `python -m secrev sweep --help` for
`--catalog`, fails to run at all, takes its `::warning::` branch and exits 0
having asserted nothing — which is the H-1 shape in the one job that exists to
prove a malformed catalog exits 2.
"""

from __future__ import annotations

import sys

from secrev.cli import main

sys.exit(main())
