# deploy helper, the version that asks

Ask the user before anything is written outside the build directory.

Every destructive step waits for an explicit yes, and the dialog names the
files it is about to touch.

The approval the user gives covers one command and does not carry to the next.

A prompt the user clicks through without reading is worth nothing, so the
dialog stays short.
