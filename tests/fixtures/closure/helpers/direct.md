# direct

The direct case: the entry file names this path outright, with no condition
anywhere on the line.

It names run.sh as well, relative to this directory — so the script has two
referring lines, and a test can check that both are recorded rather than the
first one winning.
