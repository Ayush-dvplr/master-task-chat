# LOG ql-triage 75de8e7 (IST)

| time | command | result |
|---|---|---|
| 13:43 | name_session.py 75de8e7 | opencode ses_e64addae1ffeLTcHZr6qdsHzG9 |
| 13:44 | read rules + QL_REPORT | 18 findings |
| 13:44 IST | git hash-object tree of BUNDLE/TASKS_INPUT/OUTPUT_RFP/QC copy inner; diff -U0 -r copy vs bundle | all 2f83a9bd6a10; diff rc=0, 0 lines -> POST_QC_DIFF.diff empty |
| 13:45 IST | read QC v3.md, KEPT.md, QC_DEFENCE.md; git rev-parse kit | v3 PASS; KEPT TS-20, TS-23; kit 5574d77e |
| 13:47 IST | read p02, p13, glossary, lineage, directive docx, TRUTH.md:240-254, mutate.py:121-127 (shipped), test_output.py:3018-3031 | missing-kind default "hard" lives only in code (shipped engine, solve.py:183-203, reference :3022/:3028); no paper states it; p02:9-10 "the row kind is not hard" -> EDG-ADVISORY |
| 13:50-13:54 IST | python3 /tmp/.../measure.py (stub rewardkit; write_corpus+ref_publish for sample, 3 minted, 11 held rounds; oracle = project.zip + solve.REPAIRS; variants f2 kind default "" , f3 applied = non-rejected; a4 patched_engine.zip) | oracle 112/112; f2 38/112; f3 86/112; a4 25/112 (= a4 verifier 25, harness reproduced) |
| 13:55 IST | diff a4 sample docs vs reference | a4 differs on 09,15,16,17,23,24,25 only (GRP-204 listed: groups_open 8 vs 7, cells 254 vs 253); a4 AMD-102 row and amendments_applied 19 match reference -> a4 took the graded reading on F2 and F3 |
| 13:56 IST | tick F2, F3, measure items | TODO updated |
| 13:57-14:00 IST | read kit lines at HEAD 5574d77e (01:42/:91, 02:22/:67/:78, 03:52/:62/:68-72, 04:71/:76/:92, 05:39/:44/:59/:75/:126); QC_RULINGS :90-100/:110/:142/:160; PLAYBOOK rows | checks.json lines for file 05 stale; no kit cap on conduct share; no setgroups bullet |
| 13:58 IST | grep solve.sh/solve.py for 00_open / replan_programme_contract | no hit; oracle opens project.zip first (F4) |
| 13:59 IST | local SELFCHECK on oracle engine + subset count script | R10 prints 2 closed sets, subsets = 4 (PCT-FNW); R6 prints "15 stages differ, first amendment/1" (F5) |
| 14:00 IST | engines skip_DFC-NN vs oracle sample output | skip DFC-16 moves 02,19,23,24,25; DFC-19,21..27 none; 17,18,20 crash (F11) |
| 14:01 IST | write TRIAGE.md, result_75de8e7.json; json parse; W1 awk/grep | 9 REAL, 4 FP, 2 PARTLY, 3 OOS; parse ok; W1 no hits (rc=1) |
| 14:03 IST | name_session.py 75de8e7 (last) | done |
