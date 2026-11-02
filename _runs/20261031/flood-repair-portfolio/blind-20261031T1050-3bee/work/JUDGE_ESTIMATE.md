# Judge estimate dae9563 (written after reading judge.md; app/, out/, FINAL_REPLY.md unchanged)

| id | weight | PASS / FAIL / UNSURE | the CHECKS.md line, step or file that decides it |
|---|---|---|---|
| R1 | 3 | FAIL | CHECKS #13: check.py only re-adds the program's own audit fields (households, segment_rate, risk_uplift, premium); never reads the rate/risk/site tables; no check of portfolio proposal benefits |
| R2 | 3 | FAIL | CHECKS #13: only checks no conflicting PAIR is both selected; sources never rebuilt from crews/permits/exclusions |
| R3 | 3 | FAIL | CHECKS #12: rejected rows printed and counted only; not rebuilt from input files |
| R4 | 3 | FAIL | CHECKS #14: region docs checked for internal sums and total vs summary; not rebuilt per round from site/region tables |
| R5 | 3 | FAIL | CHECKS #14: segment totals printed only; not rebuilt from segment table |
| R6 | 3 | FAIL | CHECKS #7-8: only the two big rounds solved by a prototype; no enumeration of rounds with <= 16 proposals |
| R7 | 3 | FAIL | no run on an altered copy of the data anywhere in CHECKS.md |
| R8 | 3 | PASS | CHECKS #10: `/usr/bin/time -p` real 7.64 s, "38% of the 20 s limit" |
| R9 | 3 | UNSURE | app/derive_report.py: 532 lines, helper functions and an MWIS class, but `main` is one ~345-line function; errors only for missing manifest file |
| R10 | 3 | PASS | FINAL_REPLY.md last line lists all 19 rejected round ids (matches CHECKS #12) |
| R11 | -5 | NOT FIRED | last program edit is CHECKS #9; run #10 and checks #11-15 come after it, and FINAL_REPLY.md claims only those |

Totals over positive weight 30:
- lower (PASS only minus FIRED negatives): 6 / 30 = 0.20
- upper (PASS + UNSURE minus FIRED negatives): 9 / 30 = 0.30
- process criteria not performed: 7 (R1-R7)
