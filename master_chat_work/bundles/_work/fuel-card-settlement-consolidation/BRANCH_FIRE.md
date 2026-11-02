# BRANCH_FIRE (measured, Phase 0b prototype, 26 Oct 21:05 IST)

Measured with `proto/solve_proto.py --fire` on the shipped sample (seed 731942, `--shipped`, full size) and on three hidden prototype seeds (11, 22, 33; `--small`, plants Q1 to Q15 all on). Phase 4 re-measures on the partitioned hidden months H1 to H9 (each quiet branch planted on exactly 2 months, DESIGN.md section 8).

## Quiet branches (shipped must be 0)

| rule | branch | fires on shipped (count) | fires on hidden (seeds 11 / 22 / 33) |
|---|---|---|---|
| Q1 R02b | in-period status differs between site-local and UTC date | 0 | 9 / 9 / 9 |
| Q2 R04b | card holder changes inside the month | 0 | 6 / 8 / 8 |
| Q3 R05b | row segment differs from month-end segment | 0 | 6 / 6 / 6 |
| Q4 R09b | tax rate differs from month-start rate | 0 | 40 / 65 / 52 |
| Q5 R14b | tier volume exactly on a floor | 0 | 2 / 2 / 2 |
| Q6 R16 | cap reduced a discount | 0 | 35 / 35 / 35 |
| Q7 R18 | cross-processor reversal settled | 0 | 3 / 3 / 3 |
| Q8 R19b | orphan: original present but rejected | 0 | 2 / 2 / 1 |
| Q9 R21 | account_closed | 0 | 4 / 4 / 4 |
| Q10 R23b | line in a WITHDRAWN-then-REINSTATED batch | 0 | 55 / 57 / 36 |
| Q11 R27 | CNG line settled (2023 s7, 1.52 L/kg) | 0 | 5 / 5 / 5 |
| Q12 R36 | marlow resubmission, named line `replaced` | 0 | 2 / 2 / 2 |
| Q13 R39 | norvik calibration record (`pump_test`) | 0 | 3 / 3 / 3 |
| Q14 R42 | oberon split tender line (tender 2) | 0 | 2 / 2 / 2 |
| Q15 R20b | duplicate whose rejected copy is earlier in the file | 0 | 2 / 2 / 2 |

## Shipped-firing branches (shipped sample counts)

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| R23 | superseded_batch | 1079 | 11 22 33 |
| R23 | withdrawn_batch | 503 | 11 22 33 |
| R29/R32/R35/R40 | pump_test (kestrel type, lumen zero card, marlow test, oberon T) | 333 | 11 22 33 |
| R34 | void_record / voided | 146 / 146 | 11 22 33 |
| R02 | out_of_period (weeks old) | 222 | 11 22 33 |
| R06 | unknown_product (foreign alias, PREM collision) | 109 | 11 22 33 |
| R04 | unknown_card (expired card or unknown number) | 216 | 11 22 33 |
| R20 | duplicate (file order = log order) | 99 | 11 22 33 |
| R19 | orphan_reversal (no such line) | 60 | 11 22 33 |
| R12 | half-even cent tie where half-up differs | 145 | 11 22 33 |
| R14 | accounts earning a tier above base (bronze 313, silver 158, gold 61) | 532 | 11 22 33 |

Degenerate check: every quiet row is 0 on shipped and fires on all three hidden seeds.

## R2 additions (measured 26 Oct 21:58 IST, prototype; hidden seeds 11/22/33 plant every branch; months = H1 to H9 placement)
Counts for U2, U2r, U4, U5 are rows that move when the wrong reading is switched on (seed 11), since the correct reading has no distinct counter.
| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| R43 11.4 | empty-reference reversal, exactly one fit | 133 | 11: 24, 22: 27, 33: 19 |
| U1 11.5 | two fit -> ambiguous_reversal | 0 | 2/2/2; months H2 H5 H8 |
| U2 11.5 | ledger order differs from file order | 0 | 11: 4 rows; months H1 H4 H9 |
| U2r 11.5 | referenced reversal resolved first | 0 | 11: 2 rows; months H3 H6 H7 |
| U3 11.4 | rejected twin (superseded copy, duplicate copy, out_of_period) | 0 | 3/3/3; months H1 H3 H6 |
| U4 11.4 | first candidate outside the window | 0 | 11: 2 rows; months H2 H7 H8 |
| U5 11.5 | U2r across a mid-month card reassignment (tier flip) | 0 | 11: 18 rows; months H4 H5 H9 |
| Q16 11.3 | referenced reversal after a mid-month tax change | 0 | 2/2/2; months H4 H7 H9 |

Every R2 quiet row is 0 on shipped and fires on all three seeds. Shipped output is identical under every wrong reading (COST_TABLE).
