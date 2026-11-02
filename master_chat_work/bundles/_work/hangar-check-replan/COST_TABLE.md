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

## harden_r1 measured (2 Nov 2026, built bundle, 77 checks, positive 230)
Measured in Docker `hangar-tests` (--memory 4g --cpus 2) with the built tests module, every criterion evaluated by `WORK/h1_a1/score_all.py`, weights applied by `WORK/h1_a1/rescore.py`. Logs `_runs/20261102/hangar-check-replan/harden1-20261102T1341/{score0,scoreA,scoreB,extra}.jsonl`. Lever = h7..h15 Word form folders (165 points). Predicted final = (tests % + a1 judge mid 30.8) / 2. Every loss is WRONG (rc 0, nine documents written, fields differ); no CRASH, no TIMEOUT.

| row | kind of program | tests | % | lever kept /165 | predicted final |
|---|---|---|---|---|---|
| solution/solve.py | oracle | 230/230 | 100.0 | 165 | 65.4 |
| a1_program (paid run 1 as delivered) | paid | 65/230 | 28.3 | 0 | 29.5 |
| a1_first_write | first write | 65/230 | 28.3 | 0 | 29.5 |
| solve_current (pre-build oracle reader) | all rules right, plain reader | 65/230 | 28.3 | 0 | 29.5 |
| blind_e8e9c82 | design blind | 108/230 | 47.0 | 55 | 38.9 |
| blind_r2 | design blind | 108/230 | 47.0 | 55 | 38.9 |
| blind_r1 | design blind | 56/230 | 24.3 | 20 | 27.6 |
| careful_reader (lever-aware, recorded only) | careful | 230/230 | 100.0 | 165 | 65.4 |
| solve_no_cxml (one fact wrong: customXml rows) | isolation | 175/230 | 76.1 | 110 | 53.5 |
| w_c_no_clip | all-but-one | 65/230 | 28.3 | 0 | 29.5 |
| w_q_line_from_one | all-but-one | 61/230 | 26.5 | 0 | 28.7 |
| w_s_start_key | all-but-one | 55/230 | 23.9 | 0 | 27.4 |
| w_x_ids_from_ignored | all-but-one | 53/230 | 23.0 | 0 | 26.9 |
| w_s_unordered | all-but-one | 47/230 | 20.4 | 0 | 25.6 |
| w_s_whole_only | all-but-one | 47/230 | 20.4 | 0 | 25.6 |
| w_u_from_records | all-but-one | 46/230 | 20.0 | 0 | 25.4 |
| w_p_first_found_tie | all-but-one | 44/230 | 19.1 | 0 | 25.0 |
| w_s_per_base_cap | all-but-one | 44/230 | 19.1 | 0 | 25.0 |
| w_s_granted_not_used | all-but-one | 42/230 | 18.3 | 0 | 24.5 |
| w_s_cap_not_subtracted | all-but-one | 38/230 | 16.5 | 0 | 23.7 |
| w_p_earliest_only | all-but-one | 34/230 | 14.8 | 0 | 22.8 |
| w_p_defer_no_slot_only | all-but-one | 26/230 | 11.3 | 0 | 21.1 |
| w_p_no_revised | all-but-one | 16/230 | 7.0 | 0 | 18.9 |
| w_p_pool_per_base | all-but-one | 6/230 | 2.6 | 0 | 16.7 |

- Lever alone: a1 loses all 165 lever points (71.7 % of positive weight) and nothing else.
- Blinds keep at most 55/165 (33 %): e8e9c82 and r2 read mc:AlternateContent once but skip sdt and customXml rows.
- One fact wrong (customXml rows only): loses 55 points (h8, h11, h14).
- Highest generic final 38.9 (blinds); careful_reader is lever-aware and recorded only (route1 R0.5: the careful program is the paid program, which keeps 0 %).
- Max program seconds per run 22.5 s (w_*, solve-based DP); a1 under 2.1 s.
