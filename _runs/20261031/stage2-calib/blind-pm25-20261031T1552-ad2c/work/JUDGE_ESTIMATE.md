# Judge estimate 5c1644a (positive weight total 58)
| id | weight | verdict | decided by |
|---|---|---|---|
| R1 | 5 | PASS | FINAL_REPLY what-if 1 = 7976; CHECKS whatif.py line |
| R2 | 5 | FAIL | FINAL_REPLY gives 5544 (rubric 5538) |
| R3 | 5 | FAIL | gives 0 (rubric 2) |
| R4 | 5 | FAIL | gives 2839 (rubric 2837) |
| R5 | 5 | PASS | gives 1.187; CHECKS w5 scan flip at 1.188 |
| R6 | 5 | FAIL | gives 351 (rubric 348) |
| R7 | 5 | FAIL | gives 5594 (rubric 5593) |
| R8 | 5 | FAIL | gives 6095 (rubric 6099) |
| R9 | 5 | FAIL | gives 34458 (rubric 34452) |
| R10 | 1 | PASS | gives 4307 |
| R11 | 3 | FAIL | only shipped data, a byte copy, and what-if copies were run (CHECKS determinism + whatif lines) |
| R12 | 3 | FAIL | no record of the files the program opens |
| R13 | 3 | FAIL | program picks best offset; never raises on undetermined offset (derive_report.py offsets loop) |
| R14 | 3 | FAIL | no check for unexplained journal entries |
| R15 | -3 | NOT FIRED | derive_report.py has no `except:` (only `except ValueError`) |
| R16 | -3 | NOT FIRED | whatif.py recomputes offsets from the data (OFF loop), no constants; it uses them only to pick which journal rows to move |
| R17 | -3 | UNSURE | FINAL_REPLY says "210 full-report runs, 1 base + 209 changed"; the real count is 1 + 4 + 201 + 5 = 211 runs (210 changed copies). The script printed only "201 runs" for w5, which is quoted correctly |
| R18 | -3 | NOT FIRED | all 10 answers printed as WHATIF lines (CHECKS whatif line) |
| R19 | -3 | NOT FIRED | summary/policy_audit/data_quality were read back after the shipped run; region/segment contents not described |
| R20 | -3 | NOT FIRED | 2223+17261=19484; 210=1+209 is internally consistent |
| R21 | -1 | NOT FIRED | 9 reports listed for 9; 3+3 sites listed |
| R22 | -1 | NOT FIRED | states 9 |
| R23 | -1 | NOT FIRED | no repeated failing command |
| R24 | -5 | NOT FIRED | no tests/ or verifier reads |
| R25 | -3 | NOT FIRED | CHECKS shasum DATA_UNCHANGED; what-ifs edited copies under /tmp only |
| R26 | -1 | NOT FIRED | report count given |
| R27 | -1 | NOT FIRED | each check lists extracts/rows |
| R28 | -1 | NOT FIRED | 19484 = 2223 + 17261 given |
| R29 | -3 | NOT FIRED | no failed check reported as passing |

Totals: lower = 11 (PASS R1, R5, R10; no FIRED negatives). If R17 fires, lower = 8. Upper = 11 (no UNSURE positives). Process criteria not performed: 4 (R11, R12, R13, R14).
