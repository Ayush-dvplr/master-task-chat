# LOG ql-triage 17a1c2f
| IST | command | result |
|---|---|---|
| 03:58 | name_session.py 17a1c2f | opencode ses_e7b5eb84dffe7NVGbFoqLdwxV8 |
| 03:59 | git rev-parse --short=8 HEAD (Input_Bundle_QC) | 5574d77e |
| 03:59 | tree sha BUNDLE / TASKS_INPUT / OUTPUT_RFP (excl trajectories) / LAST_QC_COPY | all e9d91966ed25 |
| 03:59 | diff -U0 -r QC copy 3f737e9 vs BUNDLE > POST_QC_DIFF.diff | exit 0, 0 bytes (no post-QC edits) |
| 04:00 | read QL_REPORT.md | 11 findings, QL1-F1..F11 |
| 04:01 | sed/grep QC v9.md L157,162,169,185,208,209,219,224,317 + KEPT.md | v9 PASS 0/0/0; only KEPT = TS-23 (66 checks). v9 rows for TS-16, TS-25, TS-28, JD-5, CL-1, CL-2, AL-2, AL-27 all ✅ |
| 04:03 | python3 checks.json rows + kit grep (HEAD 5574d77e) | live kit lines: 03_Tests_QC.md:47 TS-16, :52 TS-25, :62 TS-23, :73 TS-28, :135 sev; 04_Judge_QC.md:71 JD-5, :146 sev; 05_Alignment_Integrity_QC.md:33 AL-2, :38 AL-27, :52 AL-11, :65 AL-19, :126 sev; Final_checklist.md:488 CL-1, :489 CL-2 (checks.json line nos for 05 are older: AL-2 :22, AL-27 :27) |
| 04:05 | tests_qc.py / judge_qc.py on BUNDLE (read-only) | tests: WARN [A3] 66 checks, 36 pass 1 warn 0 fail; judge: 19 pass, PASS |
| 04:06 | scratch rk: reference on shipped data + empty-list simulation | tie_decisions [] ; `want [] mine [] pass True` (F1) |
| 04:07 | scratch rk/sweep.py, 13 graded extracts | F6 0/13, F7a 0/13, F7b 1/13 (H2, ungraded families only) |
| 04:08 | grep bundle for F2-F5, F8, F10, F11 lines | evidence in TRIAGE.md table |
| 04:12 | wrote TRIAGE.md, result_17a1c2f.json (json.tool parse ok) | 8 REAL, 1 PARTLY, 1 FP, 1 OUT OF SCOPE |
| 04:12 | W1 awk/grep on Reply notes | no hits (rc 1) |
| 04:12 | tree sha BUNDLE recheck | e9d91966ed25 (unchanged) |
