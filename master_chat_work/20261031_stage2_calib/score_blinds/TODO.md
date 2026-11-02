# Stage-2 Blind Calibration b366e00

Session rename attempted first; name_session.py returned NOT RENAMED (no matching session). No subagents. Sources read-only; all runs in approved scratch.

- [x] billing: record instruction paths, run command, weights, and recorded scores.
- [x] pm25: record instruction paths, run command, weights, and recorded scores.
- [x] pension: record instruction paths, run command, weights, and recorded scores.
- [x] scratch: prepare task copies and blind-only solve scripts.
- [x] billing: run blind and establish unmodified oracle tests score (7/97; oracle 97/97).
- [x] pm25: run blind and establish unmodified oracle tests score (10/110; oracle 110/110).
- [x] pension: run blind and establish unmodified oracle tests score (12/52; oracle 52/52).
- [x] billing: instrument all 18 lost checks and write CHECKS_billing.csv (all report bytes identical to Opus).
- [x] pm25: instrument all 20 lost checks and write CHECKS_pm25.csv (all report bytes identical to Opus).
- [x] pension: instrument all 8 lost checks and write CHECKS_pension.csv (shared metadata roots plus blind-only ACCRUAL ledger rows).
- [x] report: compare judge estimates, root causes, and write FINDINGS.md and result_b366e00.json.
- [x] cleanup: no own containers or scratch files over 10 MiB; owned image removed; final validation PASS for all 46 loss traces.
