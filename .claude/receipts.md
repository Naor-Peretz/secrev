# M0 receipts

One line per completed task: id | commit | what was actually asserted.

TASK-000 | fcd52ee | commits=1, worktree clean, gate exit 0 (no test file — baseline snapshot, no behaviour to test)
TASK-001 | dc46a54 | 16/16 green on unmodified harness; 2 fail + exit 1 when a guard block is defeated; guard restored byte-identical
TASK-002 | 67b8d94 | 18/18 green; malformed payload now refuses (was rc=5, undefined); exit 1 when the new H-1 path is defeated; guard restored byte-identical
TASK-002B | b94156e | 19/19 green; gate reports the stage; defeating a guard gives GATE exit 1 (was 0); guard restored byte-identical
TASK-003 | 65241ae | 34/34 green; brief §1 heredoc case refused with reason; cat/grep/head/git-diff of same path permitted; no false positives on transcripts|descriptions|mysrc
TASK-007 | 88d3ed0 | 42/42 green; 0 hooks invoke jq (6 mention it in comments); scope+spec malformed payload now exits 2 (was 5); defeating either H-1 path turns the gate red
TASK-008 | 0e222d6 | 47/47 green; eval into scripts/self_check.py blocked; patterns/ correctly exempt from self-application, covered by scope; removing scripts/ from paths.sh turns the gate red
TASK-009 | bfbaef4 | 52/52 green; relative src/secrev and scripts paths now guarded; over-match measured (transcripts, descripts, foosrc all refused; mypatterns and docs not); re-anchoring turns the gate red
TASK-010 | 3b48c25 | 57/57 green; M9+src exits 2, M9+README untouched, missing MILESTONE exits 2, M1 unchanged; both the refusal and the ordering fail the gate when defeated
TASK-011 | 74404f1 | 62/62 green; session-start reports M0 + BRIEF_M0.md; M0 permits scripts/ refuses src+patterns; M9 and missing marker still refuse; M0 fall-through turns the gate red
TASK-012 | pending | 64/64 green; no live agent restates STACK.md; removed copy was stale on 3 counts (claimed mypy as a recorded dep, predated §8 H-1..H-8, predated the jq decision); restating one line turns the gate red
