# Judge estimate d830ccb

| id | weight | PASS / FAIL / UNSURE | deciding CHECKS.md line/step/file |
|---|---|---|---|
| R1 Q1 = 96860261500 | 5 | FAIL | CHECKS 14: mine 96945842500 |
| R2 Q2 = 76399338500 | 5 | PASS | CHECKS 14: mine 76399338500 |
| R3 Q3 = 66714709500 | 5 | FAIL | CHECKS 14: mine 66678709500 |
| R4 Q4 = 720 | 5 | FAIL | CHECKS 14: mine 840 |
| R5 Q5 = 20295679500 | 5 | FAIL | CHECKS 14: mine 20278774500 |
| R6 Q6 = 34500454500 | 5 | FAIL | CHECKS 14: mine 34371706500 |
| R7 Q7 = 5041886500 | 5 | FAIL | CHECKS 14: mine 5077580500 |
| R8 Q8 = 143114048000 | 5 | FAIL | CHECKS 14: mine 143108240000 |
| R9 states shipped summary net + five region nets | 1 | PASS | CHECKS 11, FINAL_REPLY.md |
| R10 states number of reports | 1 | PASS | CHECKS 11 (13 reports) |
| R11 every check names extracts + closings count | 1 | PASS | CHECKS 1-16 |
| R12 runs program on a differing extract beyond the eight what-ifs | 3 | FAIL | not performed |
| R13 records files the program opens | 3 | FAIL | not performed |
| R14 raises when >1 offset set fits a day's register | 3 | FAIL | app/transform.py tie-break, no raise |
| R15 empty offset fit -> error or widen to all documented offsets | 3 | UNSURE | app/transform.py searches full -19..19 but silently picks 0 |
| R16 no bare except | 3 | PASS | CHECKS 16 |
| R17 enumerates every complete assignment | -5 | NOT FIRED | app/transform.py per-handset scan |
| R18 helper hardcodes offsets | -3 | NOT FIRED | work/whatif.py |
| R19 check size differs from output | -3 | NOT FIRED | CHECKS 11, 14 |
| R20 what-if answer without a run | -3 | NOT FIRED | CHECKS 14 |
| R21 describes a report never read back | -3 | NOT FIRED | CHECKS 11 |
| R22 whole and parts disagree | -3 | NOT FIRED | CHECKS 11, 14 (19 runs x 1536 = 29184) |
| R23 wrong report count | -1 | NOT FIRED | CHECKS 11 |
| R24 repeats a failing command | -1 | NOT FIRED | CHECKS 1-16 |
| R25 reads tests/verifier logs | -5 | NOT FIRED | file list in BLIND_REPORT.md |
| R26 writes into shipped extract | -3 | NOT FIRED | CHECKS 12 |
| R27 reports passing after failed last run | -3 | NOT FIRED | CHECKS 13-16 |

Totals (positive weight 58): lower = 11 (R2, R9, R10, R11, R16; no negatives fired); upper = 14 (adds R15).
Process criteria not performed: 3 (R12, R13, R14); R15 unsure.
