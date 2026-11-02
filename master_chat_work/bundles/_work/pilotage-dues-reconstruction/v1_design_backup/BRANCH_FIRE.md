# BRANCH_FIRE 44635de pilotage-dues-reconstruction (Shape D, measured on the 0b prototype)

Measured with `WORK/proto/solve_proto.py --fire` on the shipped instance (seed 482617, scale 1.0) and
hidden seeds 1101-1106 (scale 0.34) from `WORK/proto/gen_proto.py --hidden`. Counts are accepted
disputed rows that take the branch (per corpus: shipped, 1101, 1102, 1103, 1104, 1105, 1106). Rare
plants (LV-2, LV-3) come from their own RNG stream `random.Random(seed * 7919 + 17)`.

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| LV-1 R-FIT | station-period with exactly one listed combination (resolved) | 5 periods | 1101-1106: 3 periods each (X before, X after, Y after) |
| LV-1 R-FIT | 2 combinations fit (Z: excess draft = 15 x tugs on every paid visit) | 0 | 1101-1106: 1 period each; disputed rows 255-314 per seed incl. Y |
| LV-1 R-FIT | 3 or more combinations fit (Y before: one coefficient never exercised by paid) | 0 | 1101-1106: 1 period each (3 or 4 fits; free coefficient per_tug 1101/1102/1105, draft_per_dm 1103/1106, night_factor 1104) |
| LV-1 R-FIT | no combination fits (W: 3 paid visits billed at draft 3.25) | 0 | 1101-1106: 1 period each; disputed rows 175-199 |
| LV-1 R-FIT | multi-fit disputed row whose first-fit verdict differs from `cannot_recompute` | 0 | 1101-1106: every multi-fit row (generator asserts >=1 per multi-fit period) |
| LV-2 R-CHANGE | visit boarding on the notice date (strict `>` puts it before) | 0 | 0,2,2,2,2,2,2 |
| LV-2 R-CHANGE | visit boarding before the notice date, invoiced on or after it | 0 | 0,2,3,3,3,2,2 |
| LV-2 R-CHANGE | visit boarding on the eve, released after 00:00 on the notice date | 0 | 0,2,2,2,2,2,2 |
| LV-3 R-EXEMPT | public visit across 00:00 on the expiry date (pro-rated per line) | 0 | 0,2,2,2,2,2,2 |
| LV-3 R-EXEMPT | public visit wholly on the expiry date (billed in full) | 0 | 0,2,2,2,2,2,2 |
| LV-3 R-EXEMPT | public visit released at or before 00:00 on the expiry date, adjacent to it (0.00) | 0 | 0,4,2,2,2,3,2 |
| R7/R8/R9 plain | night; station holiday; night on a holiday (one surcharge) | 666; 43; 23 | 257/25/6, 242/19/7, 233/20/8, 232/15/4, 228/20/10, 255/17/7 |
| R10/R11 plain | public visit 0 billed far from expiry; public visit after expiry, full | 131; 102 | 42-77; 33-45 |
| R20-R23 plain | malformed_record, duplicate_invoice, unknown_visit, station_mismatch (all files) | 150, 36, 30, 12 | about 50, 12, 10, 4 each |
| R25 plain | missing declared file stops the run | 0 (shipped complete) | mutation_missing_source |

Degenerate-shipped-instance check: each sharp rule's hard branches fire 0 times on shipped and at least
twice on every hidden seed (LV-1 multi-fit hundreds of rows; LV-2 and LV-3 each 6 or more rows across
three branches). Shipped guards are generator asserts: every shipped station-period has exactly one
fit; no boarding at a notice station in [notice - 6 days, notice + 1 day); no public visit on board in
[expiry - 1 day 12:00, expiry + 1 day 00:00).

Shipped document scan (master change 2): no file in `environment/data/` shows a multi-fit tariff, a
notice-day boarding or an expiry-midnight split. The only worked example (circular section 2, lines
47-50) is the plain due and half-even rounding on invented values. `cannot_recompute` and "more than
one" appear only in circular section 6 lines 88-92.

Reflex readings measured with `WORK/proto/compare_proto.py` (docs differing of 9, audit rows differing):

| reading | shipped | 1101 | 1103 | 1104 |
|---|---|---|---|---|
| first fit (no-fit handled as stated) | exact | 6/9, 276 | 6/9, 314 | 6/9, 254 |
| period by invoice_date | exact | 5/9, 136 | 5/9, 118 | 5/9, 92 |
| notice day in old period (strict) | exact | 5/9, 76 | 5/9, 79 | 5/9, 87 |
| exemption all-or-nothing by boarding | exact | 6/9, 207 | 6/9, 161 | 6/9, 188 |
| expiry date itself covered | exact | 6/9, 341 | 6/9, 276 | 6/9, 277 |
| pro-rate the summed due once | exact | 5/9, 133 | 6/9, 161 | 6/9, 86 |
| first-write program (first fit + invoice date + all-or-nothing) | exact | 7/9, 545 | 7/9, 516 | 7/9, 531 |
| release instant for period and surcharge (plain, visible) | 8/9, 2098 | 7/9, 617 | 7/9, 590 | 7/9, 531 |

LV-2 and LV-3 errors amplify through the COUPLING sentence: a misplaced paid plant leaves its period with
no fit, so every disputed row of that period becomes `cannot_recompute`.

## v2 planned (after the blind read; measured again in the v2 prototype before Phase 2)
The v1 table above stays as the record that the blind program was exact on every branch. v2 branches:

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| LV-1 v2 | period with >= 3 fits alone and 1 jointly (Y before) | 0 | every seed, 1 period, >= 2 disputed rows differing under first fit and per-period fit |
| LV-1 v2 | period with >= 3 fits jointly (Y after, named coefficient unexercised) | 0 | every seed, 1 period, >= 2 disputed rows differing under first fit |
| LV-1 v2 | exactly 2 fits, no notice (Z) | 0 | every seed, 1 period, >= 2 disputed rows differing under first fit |
| LV-1 v2 | 1 fit per period alone, 0 jointly (W, both periods) | 0 | every seed, 2 periods |
| LV-2 v2 | notice naming fewer than four coefficients | 0 (North names all four) | every seed, 3 stations (X, Y, W) |
| LV-2 | notice-day, eve released after 00:00, boarded before and invoiced after | 0, 0, 0 | every seed, 3 each at X |
| LV-3 v2 | certificate shared by 2 or more vessels with draws from more than one | 0 (one vessel per certificate) | every seed, >= 2 certificates |
| LV-3 v2 | allowance exhausted inside a visit (partial, no midnight) | 0 | every seed, >= 2 visits |
| LV-3 v2 | visit wholly before expiry billed in full because the allowance is gone | 0 | every seed, >= 2 visits |
| LV-3 v2 | uninvoiced or other-station visit drawing before an invoiced one | 0 | every seed, >= 2 draws |
| LV-3 | across 00:00 on the expiry date; wholly on the expiry date | 0, 0 | every seed, >= 2 each |

Shipped guards add: one vessel per certificate; every certificate's allowance exceeds its vessel's
covered minutes; the North notice names all four coefficients. Plain rows R7-R25 unchanged.

## v2 measured (26 Oct 22:05, solve_proto.py v2 `--fire`, corpora /tmp/pilot-0b2)
Counts are accepted disputed rows unless stated. Columns: shipped (seed 482617), hidden 1101..1106.

| rule | branch | fires on shipped (count) | fires on hidden (seeds 1101, 1102, 1103, 1104, 1105, 1106) |
|---|---|---|---|
| LV-1 | rows in multi-fit periods (Y1 alone >= 3 joint 1, Y2 joint >= 3, Z 2) | 0 | 393, 394, 325, 279, 358, 307 |
| LV-1 | rows in no-fit periods (W1, W2 joint 0) | 0 | 222, 233, 235, 224, 233, 229 |
| LV-1 | Y1 rows wrong under first fit alone | 0 | 58, 55, 76, 32, 60, 63 |
| LV-2 | boarded before notice, invoiced after (plus 2 paid plants) | 0 | 1, 2, 1, 2, 2, 2 |
| LV-2 | boarded on notice day (plus 2 paid plants) | 0 | 1 each |
| LV-2 | eve boarding released after 00:00 (plus 2 paid plants) | 0 | 1 each |
| LV-3 | allowance exhausted inside or before a visit (cap hit) | 0 | 5 each |
| LV-3 | partial billing | 0 | 3 each |
| LV-3 | certificate shared by more than one drawing vessel | 0 | 3 each |
| LV-3 | uninvoiced or other-station visit draws | 37 (ordinary certificates, allowance never reached: no output depends on it) | 11, 13, 13, 12, 18, 15 |
| Q1 | assist suffix | 0 | 3 each |
| Q2 | draft_m rounded up | 0 | 3 each |
| Q3 | Monday after a Sunday holiday | 0 | 3 each |
| Q4 | cancelled booking | 0 | 3 each |
| Q5 | minimum due raised | 0 | 3 each |
| Q6 | re-measured vessel row in force | 0 | 3 each |
| Q7 | public vessel without certificate | 0 | 3 each |
| Q8 | superseded invoice | 0 | 2 each |
| Q9 | billed in whole cents with `c` | 0 | 3 each |
| Q10 | holiday of every station (`all`) | 0 | 3 each |

Every lever and every quiet rule: 0 effect-bearing fires on shipped, at least 2 on every hidden
corpus. LV-2 disputed plants are 1 per kind, but the 2 paid plants per kind move the joint fit, so
a wrong period reading costs the whole X station (COST_TABLE.md: pinv and pstrict lose 76 of 112).
Fits (alone / joint) match the generator meta on all 7 corpora; solve dues equal the generator's
`expect_due` on every disputed row checked (xcheck_proto.py, 0 mismatches).

Shipped document scan: no worked case of a multi-fit tariff, a notice-day boarding, an
expiry-midnight split, a shared certificate or an exhausted allowance; toy examples exist only for
the plain and quiet rules (circular :17-19, :39-41, :46-48, :96; exemption_policy :14-15, :31-32;
output_contract superseded example; station_notices fee example).

## Lessons for the master
- Role shuffle put Z at South in 5 of 6 seeds; the Phase 2 generator draws roles per seed from a shuffled list and asserts every station takes every role over 6 seeds | no change: generator fix only
- Measure reflex readings per branch in 0b, not only per lever | no change: already in LEVER_RULES W5
