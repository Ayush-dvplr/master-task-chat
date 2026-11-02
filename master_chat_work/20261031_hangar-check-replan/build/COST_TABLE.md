# COST_TABLE (G10), hangar-check-replan

Scores are tests-only (129 positive points, 35 checks). Measured in Docker on `hangar-tests` with the built `tests/test_output.py` (log `_runs/20261101/hangar-check-replan/wrong2-20261101T1215/logs/wrong.log`). Each mutant is `solution/solve.py` with exactly one reading changed (`WORK/wrong/make_wrong.py`); every mutant is exact on what the slip does not touch. Predicted final = (tests % + judge mid 44 %) / 2. Loss kind: every non-zero loss below is WRONG (rc 0, outputs written, fields differ); no TIMEOUT, no CRASH.

| row | lever | slip | tests | lost % | kind | checks failed | predicted final |
|---|---|---|---|---|---|---|---|
| oracle | none | none | 129/129 | 0 | none | 0 | 72.0 |
| s_cap_not_subtracted | L1 S2 | settled cost = gross | 30/129 | 76.7 | WRONG | 21 | 33.7 |
| s_per_base_cap | L1 S2 | each base pays only from its own grant | 36/129 | 72.1 | WRONG | 19 | 36.0 |
| s_unordered | L1 S1 | allowance paid in request_id order | 51/129 | 60.5 | WRONG | 16 | 41.8 |
| s_whole_only | L1 S2 | a check that does not fit whole takes nothing | 51/129 | 60.5 | WRONG | 16 | 41.8 |
| s_granted_not_used | L1 S2 | group credit from grants, not use | 58/129 | 55.0 | WRONG | 17 | 44.5 |
| s_start_key | L1 S1 | start day in place of due_date in the order | 79/129 | 38.8 | WRONG | 10 | 52.6 |
| p_pool_per_base | R1 | pool split per base | 4/129 | 96.9 | WRONG | 31 | 23.6 |
| p_no_revised | N | notice availability ignored | 14/129 | 89.1 | WRONG | 27 | 27.5 |
| p_defer_no_slot_only | R3 | defer only when no slot exists | 36/129 | 72.1 | WRONG | 21 | 36.0 |
| p_first_found_tie | R2/S3 | first plan found wins a tie | 75/129 | 41.9 | WRONG | 12 | 51.1 |
| p_earliest_only | R2 | earliest start only (published start never kept late) | 76/129 | 41.1 | WRONG | 13 | 51.5 |
| u_from_records | U | bases and segments taken from the records seen | 88/129 | 31.8 | WRONG | 11 | 56.1 |
| x_ids_from_ignored | X1 | ignored rows count as earlier rows for duplicates | 103/129 | 20.2 | WRONG | 6 | 61.9 |
| e8e9c82 (design blind, adapted names) | X1 | same as x_ids_from_ignored | 103/129 | 20.2 | WRONG | 6 (h3 x4, h5 x2) | 61.9 |

## Lever alone and all-but-one
- Settlement lever L1 alone (one settlement slip, all else right): loses 38.8 to 76.7 % (mean of the six rows 60.6 %); every row loses at least 25 %.
- All-but-one (every rule right but one slip): highest final 61.9 (X1 slip, and e8e9c82), below the 70 cap.
- One fact wrong: the smallest single slip measured (X1) costs 26 of 129 points.

## Honest prediction for the paid run
Both route-1 design blinds were literal readers of the docs. e8e9c82 keeps every rule and loses only the X1 held-out fixture: predicted final 61.9. A program right on every rule scores 72 (tests 100 + judge mid 44). Bar (a) (<= 35) holds only for a run that makes one of the settlement S2 slips, the pool slip, the notice slip or the deferral slip. Per route 1 this is recorded, not a blocker; the paid run decides the harden.
