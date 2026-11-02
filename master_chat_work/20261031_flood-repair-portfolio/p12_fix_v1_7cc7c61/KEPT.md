# KEPT: flood-repair-portfolio (carry-over for QC v2, from P12 fix v1 7cc7c61)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TS-11 ⚠️ | tests/test_output.py:37 `BOOK_SECONDS = 20`, :1143 `timeout=BOOK_SECONDS`; environment/data/contract.md:15 "within 20 seconds of wall time" | KEEP: Ayush exception 31 Oct 11:45 "flood-only time-out exception (losses by time-out may be the whole lever, like outage)"; the bound is stated to the agent | Input_Bundle_QC/03_Tests_QC.md:41 (TS-11 elapsed-time bounds) |
| Oracle x3 (ack) | QC v1 Step 10 oracle 1.000 x3; fixgate-20261031T121057-69b5 oracle 1.0 x3 | KEEP: Ayush acknowledgement, three oracle runs instead of five | Input_Bundle_QC/Final_checklist.md:390 |

No REBUT rows (no false positives in v1).
