# COST_TABLE (design stage, prototype, measured 26 Oct 21:58 IST)

Prototype: `proto/solve_proto.py` with one wrong reading switched on through `FC_WRONG`; corpora: shipped month (seed 731942) and proto seeds 11, 22, 33 (each plants every quiet branch, U1 to U5 and Q16). "Families moved" = output families whose documents differ from the correct prototype output. Hidden checks lost = families moved on the months that carry the branch in the H1 to H9 partition (DESIGN 8 and 9, each month graded on 2 families, w5 each, positive total 121). The phase 4 table (real tests, patched solve.py) replaces this one.

| wrong reading | branch | rows moved (seed 11) | shipped | families moved (11/22/33) | months (graded families) | hidden checks lost | tests % lost |
|---|---|---|---|---|---|---|---|
| first fit in file order (no ambiguity) | U1 | 2 | exact | all 6 / all 6 / all 6 | H2 (dq, product), H5 (summary, region), H8 (summary, segment) | 6 | 24.8 |
| file-order streaming (no ledger order) | U2 | 4 | exact | ledger, dq on all 3 | H1 (ledger), H4 (ledger, dq), H9 (dq) | 4 | 16.5 |
| index over every parsed line (rejected included) | U3a/b/c | 3 | exact | all 6 on all 3 | H1 (ledger, summary), H3 (region, segment), H6 (product, segment) | 6 | 24.8 |
| referenced not first | U2r, U5 | 20 (U5 18) | exact | all 6 on all 3 | U2r H3 H6 H7, U5 H4 H5 H9 | 12 | 49.6 |
| no seven-day window | U4 | 2 | exact | all 6 on all 3 | H2, H7, H8 | 6 | 24.8 |
| Q16 recompute tax at reversal date | Q16 | 2 | exact | all but dq on all 3 | H4 (ledger), H7 (ledger, region), H9 (product) | 4 | 16.5 |
| first fit everywhere (all six above) | all | 35 | exact | all 6 on all 3 | all 9 months | 18 | 74.4 |

Every single reading costs at least 16.5% of tests (gate in the master's GO: none under 5%, so no extra placement needed). U2 was moved from H5 to H4 (and U1 from H4 to H5) after the first count showed U2 moves only ledger and data_quality: on the old placement it cost 2 checks (8.3%).

All but one right (design numbers, judge mid 37 from JUDGE_MAP plan): U2 or Q16 alone wrong: tests 83.5, final (83.5 + 37) / 2 = 60.2; any 6-check branch alone wrong: tests 75.2, final 56.1; referenced-not-first: tests 50.4, final 43.7. All under 70.

## Lessons for the master
- A reading that moves only row identity (which reversal takes which line) shows in ledger and data_quality only; place it on months that grade those families | no change: placement rule is task specific.
