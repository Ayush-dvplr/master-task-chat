# BRANCH_FIRE (prototype, 13:27 IST, Docker run logs/bf1.log ALL_DONE)

Method: a branch fires on an extract when the prototype variant that drops that branch writes at least one of the 10 documents differently from the reference. Counts are differing documents (of 10). Shipped = seed 731905, 400 accounts, 12 months. Hidden = prototype seeds 101 and 202, 20 extracts each (`h_<tier>_<k>`).

| rule | branch (variant that drops it) | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| B2 unique fit | first fitting candidate (`fit=first`) | 0 | every k=1 extract of every tier (quiet account) + PB1, PB1b, PB2 k=0,1; seeds 101, 202 |
| B2 unique fit | best fitting candidate (`fit=best`) | 0 | same 20 extracts per seed as above; 101, 202 |
| B2 evidence = paid only | void invoices used as evidence (`evidence=withvoid`) | 0 | 40/40 extracts; 101, 202 |
| B2 evidence = paid only | void + open used (`evidence=all`) | 0 | 40/40 extracts; 101, 202 |
| B2 per-account anchor | anchor 1 / actual for all (`fit=fixed1`) | 0 | 40/40 extracts; 101, 202 |
| B3 change on cycle start billed in full (PA1) | half-open start (`cstart=halfopen`) | 0 | h_PA1_0, h_PA1_1; 101, 202 |
| K1 lot usable to day before expires_on (PA2) | inclusive expiry (`expiry=inclusive`) | 0 | h_PA2_0/1 both seeds; also h_PS_0 seed 101 |
| K4 transfers before invoices on one date (PA3) | invoices first (`sameday=invoices_first`) | 0 | h_PA3_0, h_PA3_1; 101, 202 |
| K5 cap on replayed balance (PA4) | log `posted=` figure (`cap=posted`) | 0 | h_PA4_0, h_PA4_1; 101, 202 |
| C2 effective-date order (PA5) | arrival order (`order=arrival`) | 0 | h_PA5_0, h_PA5_1; 101, 202 |
| B5 half-even per line (PA6) | half-up (`rounding=half_up`) | 0 | h_PA6_0, h_PA6_1; 101, 202 |
| K3 N from legacy live key (PS) | N fixed 12 (`ncycles=fixed12`) | 0 | h_PS_0, h_PS_1; 101, 202 |

Shape D check: every hard branch has shipped count 0 and fires on every hidden corpus that grades it. The rejection paths (unknown_account, unknown_item, duplicate_id, before_window, different_parent transfers) are not hard branches and fire on shipped by design.

## Phase 0b recheck (14:37 IST, Docker logs/bf2.log ALL_DONE, prototype WORK/proto/solve_proto.py)
Sample = `WORK/design_blind/environment/data` (seed 731905, with the rule docs present). Hidden = `bhid101`, `bhid202`, `bhid303` (gen_proto.py, 20 extracts each).

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| B2 unique fit | `fit=first`, `fit=best` | 0 | every k=1 extract and PB1, PB1b, PB2 k=0,1; 101, 202, 303 |
| B2 paid-only evidence | `evidence=withvoid`, `evidence=all` | 0 | 60/60; 101, 202, 303 |
| B2 per-account anchor | `fit=fixed1` | 0 | 60/60; 101, 202, 303 |
| B3 PA1 | `cstart=halfopen` | 0 | h_PA1_0/1; 101, 202, 303 |
| K1 PA2 | `expiry=inclusive` | 0 | h_PA2_0/1; 101, 202, 303 (also h_PS_0 seed 101) |
| K4 PA3 | `sameday=invoices_first` | 0 | h_PA3_0/1; 101, 202, 303 |
| K5 PA4 | `cap=posted` | 0 | h_PA4_0/1; 101, 202, 303 |
| C2 PA5 | `order=arrival` | 0 | h_PA5_0/1; 101, 202, 303 |
| B5 PA6 | `rounding=half_up` | 0 | h_PA6_0/1; 101, 202, 303 |
| K3 PS | `ncycles=fixed12` | 0 | h_PS_0/1; 101, 202, 303 |

Scorer self-check: `score_blind.py solve_proto.py` on sample + seeds 101, 202: tests kept 100.0% (309/309), lever kept 100.0% (300/300), max 0.4 s per hidden extract.
