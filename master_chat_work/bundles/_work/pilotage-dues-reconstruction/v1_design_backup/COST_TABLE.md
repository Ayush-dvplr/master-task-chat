# COST_TABLE (design v2-go, prototype, 26 Oct 22:05 IST)

Measured with `proto/score_proto.py`, which implements the v2-go test plan (DESIGN.md section 12,
34 checks, P = 112). Each wrong reading is a flag of `proto/solve_proto.py --reflex`, run on the
shipped corpus (seed 482617) and hidden seeds 1101-1104; every other rule is the stated reading.
Mutation checks (6 points) are counted as passed for every variant (deterministic programs that
read only `--data`), so the losses below are lower bounds. Judge mid for the final column: 35 %
of positive judge weight (blind read estimate 12-15 of 39). Final = 0.5 tests + 0.5 judge.

## Levers alone

| reading | rule | tests | lost | share lost | final (judge 35 %) |
|---|---|---|---|---|---|
| first fit of the joint projection | LV-1 R-FIT | 66/112 | 46 | 41.1 % | 47.0 |
| each period fitted alone, no join (v1 and blind structure) | LV-1 R-FIT v2 | 66/112 | 46 | 41.1 % | 47.0 |
| period by invoice_date | LV-2 R-CHANGE | 36/112 | 76 | 67.9 % | 33.6 |
| notice day kept in the old period | LV-2 R-CHANGE | 36/112 | 76 | 67.9 % | 33.6 |
| allowance per vessel, not per certificate | LV-3 R-EXEMPT | 36/112 | 76 | 67.9 % | 33.6 |
| only invoiced visits draw | LV-3 R-EXEMPT | 36/112 | 76 | 67.9 % | 33.6 |
| tie broken by log line order | LV-3 R-EXEMPT | 66/112 | 46 | 41.1 % | 47.0 |
| allowance cap ignored | LV-3 R-EXEMPT | 36/112 | 76 | 67.9 % | 33.6 |
| expiry date itself covered | LV-3 R-EXEMPT | 36/112 | 76 | 67.9 % | 33.6 |

Every lever alone is at least 41 % of tests (Shape D floor 25 %). LV-2 and LV-3 slips also move
paid plants at the X station, its joint fit drops to zero, and the quiet rows (all at X) follow
through the COUPLING sentence; that is one wrong reading changing several documents, not a
second charge for a different act.

## Quiet rules alone

| reading | rule (file) | tests | lost | share lost |
|---|---|---|---|---|
| ` assist=` suffix read as a layout break | Q1 (circular s1, s2) | 103/112 | 9 | 8.0 % |
| `draft_m=` read as a layout break | Q2 (circular s1) | 103/112 | 9 | 8.0 % |
| Sunday holiday not kept on Monday | Q3 (circular s2) | 103/112 | 9 | 8.0 % |
| CANCEL line read as a layout break | Q4 (station_notices.md) | 103/112 | 9 | 8.0 % |
| minimum due not applied | Q5 (station_notices.md) | 103/112 | 9 | 8.0 % |
| first register row always in force | Q6 (exemption_policy.md) | 103/112 | 9 | 8.0 % |
| public row without certificate rejected | Q7 (exemption_policy.md) | 103/112 | 9 | 8.0 % |
| `supersedes` ignored | Q8 (output_contract.md) | 103/112 | 9 | 8.0 % |
| `<cents>c` billed read as a layout break | Q9 (circular s6) | 103/112 | 9 | 8.0 % |
| `all` key of holidays.json ignored | Q10 (circular s2) | 103/112 | 9 | 8.0 % |

Each quiet rule alone costs its owned check (3), the whole-document summary of corpus 1 (3) and
the whole segment documents of corpus 2 (3): 9/112 = 8.04 %. All-but-one = 103/112 = 91.96
(at the 92 line; the 3-8 % band and the <= 92 line meet only at P = 112.5).

## Combined

| program | tests | final (judge 35 %) | line |
|---|---|---|---|
| every rule right except one quiet rule | 91.96 | 63.5 | all-but-one <= 92: met |
| every rule on the shipped month, all ten quiet branches skipped | 67.9 | 51.4 | <= 70: met |
| first write: per-period first fit, period by invoice date, per-vessel allowance, only invoiced visits draw, no quiet branch | 32.1 | 33.6 | |
| first write, variant 2: first fit, notice day old period, cap ignored, expiry date covered, no quiet branch | 32.1 | 33.6 | |
| levers wrong, quiet right | 32.1 | 33.6 | |
| first fit with the no-fit plant kept (master change 1 report) | 58.9 | 47.0 | |

LV-1 without the no-fit plant: the first-fit program already returns no combination for the W
station (no fit), the same as the stated rule, so the whole LV-1 loss (46 points) comes from the
multi-fit station-periods Y1, Y2 and Z; removing the no-fit plant changes no LV-1 cost.

## Lessons for the master
- quiet-rule cost and all-but-one lines pin P to 112.5 with 3+3+3 ownership | no change: recorded in COST_TABLE header.
- LV-2/LV-3 slips cascade into the quiet rows at X; keep quiet plants at one station only if that cascade is wanted | no change: design choice noted above.
