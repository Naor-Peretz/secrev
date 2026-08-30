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
TASK-012 | f9e3882 | 64/64 green; no live agent restates STACK.md; removed copy was stale on 3 counts (claimed mypy as a recorded dep, predated §8 H-1..H-8, predated the jq decision); restating one line turns the gate red
TASK-013 | 3a779cd | 68/68 green; CLAUDE.md status table + hook table current, README hook count mechanical (11 == 11); 8 stale claims asserted absent; re-adding one, or adding a 12th hook, turns the gate red
TASK-014 | c6a9414 | 69/69 green; §8 now H-1..H-9; mypy in §2; uv no longer default and 3 remedy sites updated + asserted; one assertion retired because TASK-014 made its pinned claim true
TASK-005 | c460af4 | 72/72 green; gate now runs ruff+format+pytest for real (69 collected); 15 lint findings fixed not suppressed; pyproject dev deps unreachable by pip until moved; restoring the PATH fallback turns the gate red
TASK-009B | 3f2fe31 | 74/74 green; transcripts/descripts/foosrc no longer refused, relative+absolute still are; found and fixed 2 `cmd | head` status losses (async-check reported [ok] under a failing pytest; determinism-guard would have announced byte-identical over a failure)
TASK-004 | e528258 | 81/81 green; sh/python3 <script> permitted, bash and extension mismatch refused, -c refused; ; && || | newline substitution all refuse beside a protected path; read-only pipeline now refused (asserted cost); relaxing OPERATOR_CHARS turns the gate red
TASK-004B | pending | 85/85 green; sed -i/rm/redirect into .claude refused, cat/grep/ls/sh of it permitted, Write untouched; removing .claude from PROTECTED turns the gate red (defeat verified by asserted anchor after a first attempt silently no-opped)
