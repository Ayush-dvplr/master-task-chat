# BRANCH_FIRE hangar-check-replan (proto, Docker)

Source: proto/branch.py, log _runs/20261031/hangar-check-replan/timing-20261031T2301/logs/timing2.log.
Shipped proto: n=5 per base, seeds 1-8. Hidden proto: n=8 per base, seeds 2, 4, 7.
Chosen shipped seed: 1 (all branches 0). Seed 4 rejected (plan_trade 1); the shipped generator
rejects any seed where a hard branch fires.

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| R1 shared overtime pool | pool binds (base-optimal overtime sum > K) | 0 | 2, 4, 7 |
| R1 shared overtime pool | non-convex trade (best fleet split differs from marginal share-out) | 0 | 2, 4, 7 |
| R2 four-term order | tie on three terms broken by start-day vector | 0 | 2, 4, 7 |
| R2 four-term order | earliest feasible start differs from optimal start (published start kept later) | 0 | 2, 4, 7 |
| R2 four-term order | published start kept although an earlier day is free (count per corpus) | 0 | 8, 11, 10 rows |
| R3 deferral | plan_trade deferral | 0 | 2, 4, 7 |
| R3 deferral | no_slot deferral (plain late availability) | 1 (stated, ordinary) | every hidden seed |
| R3 deferral | no_slot behind a season-end closure (planted, own RNG stream) | 0 | hidden 1:1, 2:1..6:1, 1:0..6:0 (12/12) |
| universe | base with no eligible request gets zero region file and summary row | 0 | h1 (1:1, South), h2 (3:1, North); 6/6 empty seeds |
| universe | empty segment (public) gets zero segment file and summary row | 0 | h1, h2; 6/6 empty seeds |
| S3 coupling | fleet plan differs from per-base plans with pool shared out | 0 | 2, 4, 7 (same as non-convex) |

Raw rows:
```
BF shipped 5 1..3,5..8 binds 0 nonconvex 0 tie 0 asap_differs 0 ps_kept_late 0 plan_trade 0 no_slot 0
BF shipped 5 4 ... plan_trade 1 (rejected)
BF hidden 8 2 binds 1 nonconvex 1 tie 1 asap_differs 1 ps_kept_late 8 plan_trade 1 no_slot 0
BF hidden 8 4 binds 1 nonconvex 1 tie 1 asap_differs 1 ps_kept_late 11 plan_trade 1 no_slot 0
BF hidden 8 7 binds 1 nonconvex 1 tie 1 asap_differs 1 ps_kept_late 10 plan_trade 1 no_slot 0
```

Open item for Phase 1: the hidden generator plants one no_slot request per corpus on its own RNG
stream (a D check at a base whose calendar closes for the last stretch of the season, available_from
late enough that p - c days do not fit before season end), and asserts every row above fires on every
hidden seed over 300 seeds (G12).

## Phase 0b (bf0b and bf3 logs, 31 Oct 23:37-23:44)
Prototype corpora for the design blind: shipped seed 1 (n=5), h1 = hidden 1 empty, h2 = hidden 3 empty,
h3 = hidden 1 normal (n=8). Branch rows (proto/branch0b.py):
```
BF0b shipped 5 0 seeds 1,2,3,5,6,7: binds 0 ps_kept_late 0 plan_trade 0 no_slot 1 no_slot_closure 0 empty 0/0, every split/exact variant exact
BF0b hidden 8 1 1 binds=1 ps_kept_late=11 plan_trade=1 no_slot=1 no_slot_closure=1 empty_base=1 empty_segment=1 all 7 variants wrong
BF0b hidden 8 1 3 binds=1 ps_kept_late=14 plan_trade=1 no_slot=1 no_slot_closure=1 empty_base=1 empty_segment=1 all 7 variants wrong
BF0b hidden 8 0 1 binds=1 ps_kept_late=6 plan_trade=1 no_slot=1 no_slot_closure=1 empty 0/0 all 7 variants wrong
```
Seeds 1:2 (plan_trade 0, defer_noslot exact) and 0:2 (split_marginal exact) would be rejected by the
hidden seed filter. Phase 1 still asserts every row over 300 seeds.
