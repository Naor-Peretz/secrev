# M0 receipts

One line per completed task: id | commit | what was actually asserted.

TASK-000 | fcd52ee | commits=1, worktree clean, gate exit 0 (no test file — baseline snapshot, no behaviour to test)
TASK-001 | dc46a54 | 16/16 green on unmodified harness; 2 fail + exit 1 when a guard block is defeated; guard restored byte-identical
TASK-002 | 67b8d94 | 18/18 green; malformed payload now refuses (was rc=5, undefined); exit 1 when the new H-1 path is defeated; guard restored byte-identical
TASK-002B | b94156e | 19/19 green; gate reports the stage; defeating a guard gives GATE exit 1 (was 0); guard restored byte-identical
TASK-003 | pending | 34/34 green; brief §1 heredoc case refused with reason; cat/grep/head/git-diff of same path permitted; no false positives on transcripts|descriptions|mysrc
