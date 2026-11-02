# COST_TABLE (harden r2, bddb388; measured 2026-11-01 14:30-15:10 IST)

Docker python:3.12-slim, --memory 4g --cpus 2, container h2final2, final BUNDLE tests (110 positive).
Logs: _runs/20261101/slipway-overhaul-replan-repair/harden2-114714/{final2.log,f2_solve.log,kill5_*.log,score5.log,vt2_*.json}.

## Tests-only verifier (rewardkit over the final tests/, judge left out)

| delivered program | wall s | limit s | share of limit | tests channel |
|---|---|---|---|---|
| oracle (solve.sh output) | 127 | 5400 | 2.4% | 0.5 of 0.5 = 110/110 |
| a3 paid-run artifacts | 115 | 5400 | 2.1% | 0.2273 of 0.5 = 50/110 |

## Kill table on final tests (15 rounds: 4 old seeds, 11 held-out)

| program | tests | lever kept | rounds lost | loss kind | corpus max s | reference max s | program max s | loop wall s |
|---|---|---|---|---|---|---|---|---|
| a3_program (paid run) | 50/110 = 45.45% | 0/60 | 11 | WRONG | 14.41 | 0.23 | 0.67 | 124 |
| oracle_fixed | 110/110 = 100.00% | 60/60 | 0 | none | 12.67 | 0.16 | 0.66 | 123 |
| oracle_program (first-write, catalogued faults only) | 35/110 = 31.82% | 0/60 | 15 | WRONG, CRASH on 4 (KeyError on a legacy id or on a group left with one member) | 12.59 | 0.22 | 0.87 | 124 |
| engine_orig (shipped, blind) | 2/110 = 1.82% | 0/60 | 15 | WRONG, CRASH on 4 (KeyError on a legacy id or on a group left with one member) | 12.24 | 0.2 | 0.9 | 127 |
| a3_groups | 65/110 = 59.09% | 15/60 | 8 | WRONG | 12.08 | 0.19 | 0.92 | 115 |
| a3_rules | 65/110 = 59.09% | 15/60 | 8 | WRONG | 16.56 | 0.18 | 1.53 | 128 |
| a3_amendments | 65/110 = 59.09% | 15/60 | 9 | WRONG | 12.05 | 0.21 | 1.27 | 132 |
| oracle_less_groups (all-but-one) | 80/110 = 72.73% | 30/60 | 6 | WRONG, CRASH on 2 (KeyError on a legacy id or on a group left with one member) | 15.29 | 0.22 | 0.88 | 142 |
| oracle_less_rules (all-but-one) | 80/110 = 72.73% | 30/60 | 6 | WRONG | 15.46 | 0.23 | 0.81 | 138 |
| oracle_less_amendments (all-but-one) | 80/110 = 72.73% | 30/60 | 5 | WRONG, CRASH on 3 (KeyError on a legacy id or on a group left with one member) | 13.76 | 0.2 | 0.67 | 122 |
| a3_careful (careful enumerator, recorded) | 110/110 = 100.00% | 60/60 | 0 | none | 15.87 | 0.21 | 1.44 | 142 |

Reference cost per round at most 0.23 s against a 300 s per-drive cap; verifier worst 127 s of
5400 s (2.4%), well inside 90%. The a3 program never crashes: all its losses are WRONG bytes.
