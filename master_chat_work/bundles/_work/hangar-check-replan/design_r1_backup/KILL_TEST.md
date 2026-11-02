# KILL_TEST af5dddf hangar-check-replan

All runs in Docker: `docker run --rm --memory 4g --cpus 2 -v proto:/w:ro python:3.12-slim`, each solver call under `perl -e "alarm 300; exec @ARGV"`, dockfree START=yes before each container.
Prototype: WORK/proto (gen.py, ref.py, wrong.py, kill1.py, killall.sh). Shipped = degenerate mode (pool limit equals the unconstrained optimum's use, no plan_trade gadget, r = published start). Hidden = pool limit 0.5 x unconstrained use, gadgets on, 7 checks per base (28 checks).
Block 1 log: _runs/20261031/hangar-check-replan/kill-20261031T2245/logs/kill_main.log (110 ROW lines, ALL_DONE).
T = [first term, second term, third term] of the stated order. "T equal" = same objective but a different start/finish vector (tie-break lost).

## Lever points kept (hidden, 8 seeds)
Hidden family tests per corpus: audit, regions (4 base files), segments (2 files), summary. A plan whose objective differs changes every family (fleet overtime, totals and per-check rows all move: COUPLING). A plan with an equal objective and a different vector keeps the summary only (1 of 4 family checks).

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| greedy by due date (greedy_edd) | hidden n=7 seeds 2 4 5 7 8 9 10 12 | 0.0 | WRONG 8/8 (T differs 8) | 0% | yes, but WRONG on shipped too (not a lever loss) |
| disrupted-only repair (disrupted_repair) | same | 0.0 | WRONG 8/8 (T differs 8) | 0% | yes, WRONG on shipped too |
| split by base exact + first-come overtime (split_fcfs) | same | 1.2-2.5 | WRONG 8/8 (T differs 8) | 0% | yes, EXACT shipped 1-3 (0.4-0.5 s) |
| split by base exact + pro-rata overtime (split_prorata) | same | 1.1-2.2 | WRONG 8/8 (T differs 8) | 0% | yes, EXACT shipped 1-3 |
| split exact + greedy marginal overtime (split_marginal) | same | 1.2-2.6 | WRONG 8/8 (T differs 6, T equal 2) | 6% | yes, EXACT shipped 1-3 |
| exact merge, first-found tie (exact_first_tie) | same | 1.2-2.9 | WRONG 6/8, EXACT 2/8 (seeds 4, 5) | 44% | yes, EXACT shipped 1-3 |
| exact merge, reversed vector tie (exact_rev_tie) | same | 3.0-6.3 | WRONG 8/8 (T equal 8) | 25% | yes, EXACT shipped 1-3 |
| exact merge, earliest start only (exact_asap_only) | same | 1.0-1.9 | WRONG 8/8 (T differs 8, third term) | 0% | yes, EXACT shipped 1-3 |
| exact merge, defer only no_slot (exact_defer_noslot) | same | 0.6-1.8 | WRONG 8/8 (T differs 8) | 0% | yes on shipped 1-2; WRONG on proto shipped seed 3 (plan_trade fired; shipped generator must reject such seeds) |
| exact merge over every start day, all readings right (exact_all_starts) | same | 49-95 | EXACT 8/8 | 100% at n=7 | 25-33 s at shipped n=6 |

## Raw rows (block 1)
| solver | instance | seconds | verdict | objective |
|---|---|---|---|---|
| greedy_edd | shipped seed 1 | 0.0 (ref 0.5) | WRONG | [126, 13460, 7] vs ref [96, 12810, 5]; T differs; first diff Q10276 |
| disrupted_repair | shipped seed 1 | 0.0 (ref 0.5) | WRONG | [332, 13460, 3] vs ref [96, 12810, 5]; T differs; first diff Q10276 |
| split_fcfs | shipped seed 1 | 0.5 (ref 0.5) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| split_prorata | shipped seed 1 | 0.5 (ref 0.5) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| split_marginal | shipped seed 1 | 0.5 (ref 0.5) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| exact_first_tie | shipped seed 1 | 0.6 (ref 0.6) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| exact_rev_tie | shipped seed 1 | 0.7 (ref 0.3) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| exact_asap_only | shipped seed 1 | 0.6 (ref 0.4) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| exact_defer_noslot | shipped seed 1 | 0.2 (ref 0.3) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| exact_all_starts | shipped seed 1 | 33.2 (ref 0.4) | EXACT | [96, 12810, 5] vs ref [96, 12810, 5]; -; first diff none |
| greedy_edd | shipped seed 2 | 0.0 (ref 0.3) | WRONG | [222, 9250, 13] vs ref [216, 8830, 13]; T differs; first diff Q17412 |
| disrupted_repair | shipped seed 2 | 0.0 (ref 0.3) | WRONG | [1080, 9120, 7] vs ref [216, 8830, 13]; T differs; first diff Q14683 |
| split_fcfs | shipped seed 2 | 0.4 (ref 0.6) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| split_prorata | shipped seed 2 | 0.3 (ref 0.3) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| split_marginal | shipped seed 2 | 0.5 (ref 0.4) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| exact_first_tie | shipped seed 2 | 0.5 (ref 0.3) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| exact_rev_tie | shipped seed 2 | 1.0 (ref 0.5) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| exact_asap_only | shipped seed 2 | 0.5 (ref 0.4) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| exact_defer_noslot | shipped seed 2 | 0.4 (ref 0.5) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| exact_all_starts | shipped seed 2 | 25.3 (ref 0.4) | EXACT | [216, 8830, 13] vs ref [216, 8830, 13]; -; first diff none |
| greedy_edd | shipped seed 3 | 0.0 (ref 0.3) | WRONG | [76, 8395, 8] vs ref [40, 7980, 6]; T differs; first diff Q11725 |
| disrupted_repair | shipped seed 3 | 0.0 (ref 0.4) | WRONG | [872, 8440, 5] vs ref [40, 7980, 6]; T differs; first diff Q11725 |
| split_fcfs | shipped seed 3 | 0.4 (ref 0.3) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| split_prorata | shipped seed 3 | 0.4 (ref 0.5) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| split_marginal | shipped seed 3 | 0.4 (ref 0.4) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| exact_first_tie | shipped seed 3 | 0.4 (ref 0.4) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| exact_rev_tie | shipped seed 3 | 0.9 (ref 0.4) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| exact_asap_only | shipped seed 3 | 0.5 (ref 0.5) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| exact_defer_noslot | shipped seed 3 | 0.3 (ref 0.4) | WRONG | [46, 8220, 8] vs ref [40, 7980, 6]; T differs; first diff Q58490 |
| exact_all_starts | shipped seed 3 | 30.9 (ref 0.3) | EXACT | [40, 7980, 6] vs ref [40, 7980, 6]; -; first diff none |
| greedy_edd | hidden seed 2 | 0.0 (ref 1.8) | WRONG | [210, 13200, 12] vs ref [150, 12825, 8]; T differs; first diff Q14683 |
| disrupted_repair | hidden seed 2 | 0.0 (ref 2.4) | WRONG | [432, 13450, 4] vs ref [150, 12825, 8]; T differs; first diff Q14683 |
| split_fcfs | hidden seed 2 | 1.7 (ref 1.9) | WRONG | [172, 12695, 10] vs ref [150, 12825, 8]; T differs; first diff Q21124 |
| split_prorata | hidden seed 2 | 1.5 (ref 1.6) | WRONG | [154, 12685, 9] vs ref [150, 12825, 8]; T differs; first diff Q21124 |
| split_marginal | hidden seed 2 | 2.2 (ref 1.9) | WRONG | [150, 12825, 9] vs ref [150, 12825, 8]; T differs; first diff Q21124 |
| exact_first_tie | hidden seed 2 | 2.3 (ref 3.9) | WRONG | [150, 12825, 8] vs ref [150, 12825, 8]; T equal; first diff Q21124 |
| exact_rev_tie | hidden seed 2 | 4.7 (ref 2.4) | WRONG | [150, 12825, 8] vs ref [150, 12825, 8]; T equal; first diff Q21124 |
| exact_asap_only | hidden seed 2 | 1.9 (ref 2.3) | WRONG | [150, 12825, 11] vs ref [150, 12825, 8]; T differs; first diff Q21124 |
| exact_defer_noslot | hidden seed 2 | 0.9 (ref 1.7) | WRONG | [168, 13195, 9] vs ref [150, 12825, 8]; T differs; first diff Q21124 |
| exact_all_starts | hidden seed 2 | 74.0 (ref 1.5) | EXACT | [150, 12825, 8] vs ref [150, 12825, 8]; -; first diff none |
| greedy_edd | hidden seed 4 | 0.0 (ref 1.3) | WRONG | [104, 10530, 21] vs ref [60, 10150, 6]; T differs; first diff Q12597 |
| disrupted_repair | hidden seed 4 | 0.0 (ref 1.3) | WRONG | [338, 10420, 4] vs ref [60, 10150, 6]; T differs; first diff Q18718 |
| split_fcfs | hidden seed 4 | 1.3 (ref 1.3) | WRONG | [78, 9940, 6] vs ref [60, 10150, 6]; T differs; first diff Q17713 |
| split_prorata | hidden seed 4 | 2.2 (ref 1.9) | WRONG | [64, 10150, 6] vs ref [60, 10150, 6]; T differs; first diff Q21809 |
| split_marginal | hidden seed 4 | 2.1 (ref 2.2) | WRONG | [90, 9570, 6] vs ref [60, 10150, 6]; T differs; first diff Q18718 |
| exact_first_tie | hidden seed 4 | 2.9 (ref 2.4) | EXACT | [60, 10150, 6] vs ref [60, 10150, 6]; -; first diff none |
| exact_rev_tie | hidden seed 4 | 6.3 (ref 2.6) | WRONG | [60, 10150, 6] vs ref [60, 10150, 6]; T equal; first diff Q23522 |
| exact_asap_only | hidden seed 4 | 1.9 (ref 2.2) | WRONG | [60, 10150, 17] vs ref [60, 10150, 6]; T differs; first diff Q12597 |
| exact_defer_noslot | hidden seed 4 | 1.8 (ref 2.1) | WRONG | [72, 10410, 6] vs ref [60, 10150, 6]; T differs; first diff Q38101 |
| exact_all_starts | hidden seed 4 | 95.2 (ref 2.1) | EXACT | [60, 10150, 6] vs ref [60, 10150, 6]; -; first diff none |
| greedy_edd | hidden seed 5 | 0.0 (ref 2.7) | WRONG | [94, 11685, 17] vs ref [72, 10950, 9]; T differs; first diff Q13801 |
| disrupted_repair | hidden seed 5 | 0.0 (ref 2.2) | WRONG | [270, 11670, 5] vs ref [72, 10950, 9]; T differs; first diff Q11718 |
| split_fcfs | hidden seed 5 | 2.5 (ref 1.9) | WRONG | [84, 10820, 7] vs ref [72, 10950, 9]; T differs; first diff Q11718 |
| split_prorata | hidden seed 5 | 2.2 (ref 2.6) | WRONG | [108, 10440, 10] vs ref [72, 10950, 9]; T differs; first diff Q11718 |
| split_marginal | hidden seed 5 | 2.6 (ref 2.5) | WRONG | [72, 11010, 9] vs ref [72, 10950, 9]; T differs; first diff Q11718 |
| exact_first_tie | hidden seed 5 | 2.5 (ref 2.5) | EXACT | [72, 10950, 9] vs ref [72, 10950, 9]; -; first diff none |
| exact_rev_tie | hidden seed 5 | 4.7 (ref 2.0) | WRONG | [72, 10950, 9] vs ref [72, 10950, 9]; T equal; first diff Q19428 |
| exact_asap_only | hidden seed 5 | 1.3 (ref 1.6) | WRONG | [72, 10950, 18] vs ref [72, 10950, 9]; T differs; first diff Q19428 |
| exact_defer_noslot | hidden seed 5 | 0.7 (ref 1.5) | WRONG | [78, 11530, 9] vs ref [72, 10950, 9]; T differs; first diff Q28188 |
| exact_all_starts | hidden seed 5 | 59.8 (ref 1.5) | EXACT | [72, 10950, 9] vs ref [72, 10950, 9]; -; first diff none |
| greedy_edd | hidden seed 7 | 0.0 (ref 1.2) | WRONG | [170, 9465, 17] vs ref [146, 9105, 12]; T differs; first diff Q16328 |
| disrupted_repair | hidden seed 7 | 0.0 (ref 1.1) | WRONG | [728, 9660, 6] vs ref [146, 9105, 12]; T differs; first diff Q16328 |
| split_fcfs | hidden seed 7 | 1.4 (ref 1.2) | WRONG | [184, 8380, 10] vs ref [146, 9105, 12]; T differs; first diff Q16328 |
| split_prorata | hidden seed 7 | 1.5 (ref 1.6) | WRONG | [152, 8655, 12] vs ref [146, 9105, 12]; T differs; first diff Q26226 |
| split_marginal | hidden seed 7 | 1.3 (ref 1.3) | WRONG | [150, 8765, 11] vs ref [146, 9105, 12]; T differs; first diff Q16328 |
| exact_first_tie | hidden seed 7 | 1.3 (ref 1.2) | WRONG | [146, 9105, 12] vs ref [146, 9105, 12]; T equal; first diff Q16328 |
| exact_rev_tie | hidden seed 7 | 3.0 (ref 1.2) | WRONG | [146, 9105, 12] vs ref [146, 9105, 12]; T equal; first diff Q16328 |
| exact_asap_only | hidden seed 7 | 1.2 (ref 1.3) | WRONG | [146, 9105, 13] vs ref [146, 9105, 12]; T differs; first diff Q21265 |
| exact_defer_noslot | hidden seed 7 | 0.7 (ref 1.2) | WRONG | [156, 9510, 12] vs ref [146, 9105, 12]; T differs; first diff Q16328 |
| exact_all_starts | hidden seed 7 | 63.9 (ref 1.5) | EXACT | [146, 9105, 12] vs ref [146, 9105, 12]; -; first diff none |
| greedy_edd | hidden seed 8 | 0.0 (ref 1.4) | WRONG | [46, 11210, 8] vs ref [38, 10200, 6]; T differs; first diff Q13970 |
| disrupted_repair | hidden seed 8 | 0.0 (ref 1.3) | WRONG | [254, 11260, 3] vs ref [38, 10200, 6]; T differs; first diff Q13970 |
| split_fcfs | hidden seed 8 | 1.3 (ref 1.1) | WRONG | [38, 10400, 6] vs ref [38, 10200, 6]; T differs; first diff Q35196 |
| split_prorata | hidden seed 8 | 1.1 (ref 1.2) | WRONG | [38, 10270, 6] vs ref [38, 10200, 6]; T differs; first diff Q12620 |
| split_marginal | hidden seed 8 | 1.3 (ref 1.2) | WRONG | [38, 10200, 6] vs ref [38, 10200, 6]; T equal; first diff Q35196 |
| exact_first_tie | hidden seed 8 | 1.4 (ref 1.5) | WRONG | [38, 10200, 6] vs ref [38, 10200, 6]; T equal; first diff Q76369 |
| exact_rev_tie | hidden seed 8 | 3.1 (ref 1.3) | WRONG | [38, 10200, 6] vs ref [38, 10200, 6]; T equal; first diff Q35196 |
| exact_asap_only | hidden seed 8 | 1.0 (ref 1.1) | WRONG | [38, 10200, 9] vs ref [38, 10200, 6]; T differs; first diff Q15738 |
| exact_defer_noslot | hidden seed 8 | 0.6 (ref 1.1) | WRONG | [46, 10680, 6] vs ref [38, 10200, 6]; T differs; first diff Q63433 |
| exact_all_starts | hidden seed 8 | 51.5 (ref 1.1) | EXACT | [38, 10200, 6] vs ref [38, 10200, 6]; -; first diff none |
| greedy_edd | hidden seed 9 | 0.0 (ref 1.2) | WRONG | [394, 11265, 17] vs ref [68, 10915, 7]; T differs; first diff Q10843 |
| disrupted_repair | hidden seed 9 | 0.0 (ref 1.2) | WRONG | [400, 11600, 5] vs ref [68, 10915, 7]; T differs; first diff Q10843 |
| split_fcfs | hidden seed 9 | 1.2 (ref 1.2) | WRONG | [236, 10870, 8] vs ref [68, 10915, 7]; T differs; first diff Q16728 |
| split_prorata | hidden seed 9 | 1.2 (ref 1.2) | WRONG | [72, 11030, 8] vs ref [68, 10915, 7]; T differs; first diff Q27357 |
| split_marginal | hidden seed 9 | 1.2 (ref 1.2) | WRONG | [68, 10915, 7] vs ref [68, 10915, 7]; T equal; first diff Q30598 |
| exact_first_tie | hidden seed 9 | 1.5 (ref 1.2) | WRONG | [68, 10915, 7] vs ref [68, 10915, 7]; T equal; first diff Q54345 |
| exact_rev_tie | hidden seed 9 | 3.4 (ref 1.2) | WRONG | [68, 10915, 7] vs ref [68, 10915, 7]; T equal; first diff Q30598 |
| exact_asap_only | hidden seed 9 | 1.2 (ref 1.3) | WRONG | [68, 10915, 13] vs ref [68, 10915, 7]; T differs; first diff Q32076 |
| exact_defer_noslot | hidden seed 9 | 0.7 (ref 1.2) | WRONG | [74, 11495, 7] vs ref [68, 10915, 7]; T differs; first diff Q10843 |
| exact_all_starts | hidden seed 9 | 49.9 (ref 1.4) | EXACT | [68, 10915, 7] vs ref [68, 10915, 7]; -; first diff none |
| greedy_edd | hidden seed 10 | 0.0 (ref 1.2) | WRONG | [44, 12010, 6] vs ref [30, 11090, 1]; T differs; first diff Q11944 |
| disrupted_repair | hidden seed 10 | 0.0 (ref 1.2) | WRONG | [44, 12010, 1] vs ref [30, 11090, 1]; T differs; first diff Q11944 |
| split_fcfs | hidden seed 10 | 1.2 (ref 1.2) | WRONG | [30, 11235, 1] vs ref [30, 11090, 1]; T differs; first diff Q14270 |
| split_prorata | hidden seed 10 | 1.2 (ref 1.2) | WRONG | [30, 11190, 1] vs ref [30, 11090, 1]; T differs; first diff Q31001 |
| split_marginal | hidden seed 10 | 1.2 (ref 1.2) | WRONG | [30, 11120, 1] vs ref [30, 11090, 1]; T differs; first diff Q14270 |
| exact_first_tie | hidden seed 10 | 1.4 (ref 1.4) | WRONG | [30, 11090, 1] vs ref [30, 11090, 1]; T equal; first diff Q66215 |
| exact_rev_tie | hidden seed 10 | 3.1 (ref 1.2) | WRONG | [30, 11090, 1] vs ref [30, 11090, 1]; T equal; first diff Q11944 |
| exact_asap_only | hidden seed 10 | 1.0 (ref 1.2) | WRONG | [30, 11090, 6] vs ref [30, 11090, 1]; T differs; first diff Q11944 |
| exact_defer_noslot | hidden seed 10 | 0.7 (ref 1.2) | WRONG | [44, 11540, 1] vs ref [30, 11090, 1]; T differs; first diff Q44382 |
| exact_all_starts | hidden seed 10 | 59.9 (ref 1.2) | EXACT | [30, 11090, 1] vs ref [30, 11090, 1]; -; first diff none |
| greedy_edd | hidden seed 12 | 0.0 (ref 1.1) | WRONG | [314, 14240, 16] vs ref [254, 13750, 9]; T differs; first diff Q10218 |
| disrupted_repair | hidden seed 12 | 0.0 (ref 1.1) | WRONG | [954, 14400, 5] vs ref [254, 13750, 9]; T differs; first diff Q10218 |
| split_fcfs | hidden seed 12 | 1.5 (ref 1.1) | WRONG | [302, 13450, 9] vs ref [254, 13750, 9]; T differs; first diff Q10218 |
| split_prorata | hidden seed 12 | 1.2 (ref 1.2) | WRONG | [278, 13155, 7] vs ref [254, 13750, 9]; T differs; first diff Q28690 |
| split_marginal | hidden seed 12 | 1.4 (ref 1.7) | WRONG | [258, 13635, 9] vs ref [254, 13750, 9]; T differs; first diff Q29045 |
| exact_first_tie | hidden seed 12 | 1.2 (ref 1.3) | WRONG | [254, 13750, 9] vs ref [254, 13750, 9]; T equal; first diff Q11423 |
| exact_rev_tie | hidden seed 12 | 3.2 (ref 1.3) | WRONG | [254, 13750, 9] vs ref [254, 13750, 9]; T equal; first diff Q11423 |
| exact_asap_only | hidden seed 12 | 1.1 (ref 1.2) | WRONG | [254, 13750, 14] vs ref [254, 13750, 9]; T differs; first diff Q11423 |
| exact_defer_noslot | hidden seed 12 | 0.6 (ref 1.2) | WRONG | [284, 14215, 10] vs ref [254, 13750, 9]; T differs; first diff Q11423 |
| exact_all_starts | hidden seed 12 | 49.2 (ref 1.2) | EXACT | [254, 13750, 9] vs ref [254, 13750, 9]; -; first diff none |

## Timing at hidden scale n=8 per base (Docker --memory 4g --cpus 2)

Log: _runs/20261031/hangar-check-replan/timing-20261031T2301/logs/timing.log and timing2.log.

| solver | instance | seconds | result | note |
|---|---|---|---|---|
| exact_all_starts | shipped n=5 seed 1 | 7.0 (ref 0.1) | EXACT | shipped fast |
| exact_all_starts | shipped n=5 seed 2 | 5.6 (ref 0.0) | EXACT | shipped fast |
| exact_all_starts | shipped n=5 seed 3 | 5.8 (ref 0.0) | EXACT | shipped fast |
| exact_all_starts | hidden n=8 seed 2 | 119.6 (ref 3.5) | EXACT, over 60 s | TIMEOUT under stated 60 s |
| exact_all_starts | hidden n=8 seed 4 | 142.5 (ref 3.3) | EXACT, over 60 s | TIMEOUT under stated 60 s |
| exact_all_starts | hidden n=8 seed 7 | 121.0 (ref 3.2) | EXACT, over 60 s | TIMEOUT under stated 60 s |
| exact_all_starts | hidden n=8 one seed (block 1) | >300 | alarm | TIMEOUT |
| joint_exact | hidden n=7 seed 2 | >180 | alarm | TIMEOUT |

## Verdict

- Decision: hidden scale n=8 checks per base (32 per corpus); shipped n=5 per base; stated per-run limit 60 s.
- Reference 3.2-3.5 s at n=8, under 1/4 of 60 s (15 s). Reference is 34x to 43x faster than the best plain exact solver.
- Every fast plain solver (greedy, disrupted repair, three split rules, exact with first-found tie, exact with revenue tie, exact earliest-start only, exact with no_slot-only deferral) loses by WRONG on hidden corpora; the exact variants are EXACT on shipped (defer_noslot only on a shipped seed with no plan_trade, which the chosen shipped seed guarantees).
- exact_all_starts with every reading right is EXACT but loses by TIMEOUT at hidden scale; it is EXACT and fast on shipped (v3.5: no shipped slowness, limit stated in instruction).
- Timeout share across the kill table: WRONG lever points lost 825 (9 solvers), TIMEOUT 100 (1 solver), share 10.8% of lost points. Per solver, exact_all_starts loses 100% by TIMEOUT; flagged as RISK in DESIGN_SUMMARY.

## Phase 0b row (master m0127): universe from records
| solver | instance | seconds | result | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| reference except bases and segments derived from the records seen | shipped 1, h3 (1:0) | 0.3, 5.0 | EXACT | n/a | yes |
| same | h1 (1:1, South empty), h2 (3:1, North empty), public empty in both | 4.6, 4.1 | WRONG: region_south / region_north, segment_public and the empty summary rows absent | 80 of 86 (93%) | yes |
Loss kind WRONG; it stacks on every other row (a split or reflex solver that also derives axes loses these 6 too).

## Design blind row (24bff4e, scored 00:00; log _runs/20261031/hangar-check-replan/score-24bff4e/logs/score.log)
| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| design blind 24bff4e (per-base memo + dominance starts + exact pool merge + tie vector) | shipped s1, h1 1:1, h2 3:1, h3 1:0, h4 3:0, h5 5:0 | 0.15-0.81 | EXACT 6/6 (all families, all fields) | 100% | yes |
Verdict: the blind is the reference. NO CORE under G-8; one redesign is the master's call.

## Redesign 1: Office package current-text lever (kill r1g, 01 Nov 00:47, Docker 4g / 2 cpu)
Run: _runs/20261031/hangar-check-replan/killr1g-20261101T0047 (scratch + logs/kill.log). Same optimisation
reference for every row; only the reader of `disruption_notice.docx` and `planning_limits.docx` changes.
Corpora: shipped seed 2 (n=5/base, plain packages); hidden h1=1:1:F1+F2+F3+F4, h2=3:1:F1+F2+F3+F4,
h3=1:0:F1+F2+F3, h4=3:0:F2+F3+F4, h5=5:0:F1+F3+F4, h6=6:0:F1+F2+F4 (n=8/base; each family on 5 of 6).
Lever points per hidden corpus 20 (audit, regions, segments, summary, w5 each); 120 in all.

| solver (reader slip) | shipped | h1 | h2 | h3 | h4 | h5 | h6 | lever kept | loss |
|---|---|---|---|---|---|---|---|---|---|
| reference (ref reader) | EXACT 0.37 s | EXACT 4.9 s | EXACT 4.8 s | EXACT 5.7 s | EXACT 5.4 s | EXACT 3.8 s | EXACT 4.4 s | 100% | none |
| join every w:t (Choice, Fallback, moveFrom all read) | EXACT | 3 | 1 | 0 | 0 | 0 | 20 | 20% | WRONG |
| main part by default name word/document.xml | EXACT | 1 | 1 | 0 | 20 | 0 | 0 | 18% | WRONG |
| always mc:Fallback | EXACT | 3 | 3 | 0 | 0 | 20 | 0 | 22% | WRONG |
| first mc:Choice regardless of Requires | EXACT | 3 | 3 | 0 | 0 | 20 | 0 | 22% | WRONG |
| deletions read (w:delText kept) | EXACT | 1 | 1 | 20 | 0 | 0 | 0 | 18% | WRONG |
| tracked move read twice (moveFrom kept) | EXACT | 3 | 1 | 0 | 0 | 0 | 20 | 20% | WRONG |
| mc:AlternateContent dropped | EXACT | 3 | 3 | 0 | 0 | 20 | 0 | 22% | WRONG |
| direct w:r/w:t children only (python-docx-like) | EXACT | 1 | 1 | 0 | 0 | 0 | 0 | 2% | WRONG |
| naive stdlib (default name + regex over every w:t) | EXACT | 1 | 1 | 0 | 0 | 0 | 0 | 2% | WRONG |
| design blind 24bff4e (reads .md/.yaml, pool from toml) | CRASH | CRASH | CRASH | CRASH | CRASH | CRASH | CRASH | 0% | CRASH (rc 1, names fleet_limits.toml) |
Every slip run exits 0 (no CRASH, no TIMEOUT); losses are WRONG figures. Each slip keeps only the one
corpus that lacks its family (20/20) plus 1-3 points elsewhere (a rollup or summary field the trap does
not move). Timeout share of lost lever points in this table: 0%.

Trap cells per corpus (current -> value a slip reads):
| corpus | F1 stale main part | F2 alternatives (fallback slip) | F3 tracked move (move slip) | F4 del/ins (delete slip) |
|---|---|---|---|---|
| shipped | none | none | none | none |
| h1 | both packages | North closure 71 -> 31 | East closure 12 -> 212 | pool 46 -> 446, shift_cost 15 -> 195 |
| h2 | both packages | South closure 74 -> 34 | pool 41 -> 141, shift_cost 15 -> 515 | West closure 18 -> 158 |
| h3 | both packages | South closure 23 -> 13, pool 56 -> 26 | North closure 17 -> 717, East 17 -> 717 | none |
| h4 | none | South closure 21 -> 11 | East closure 14 -> 414, pool 67 -> 767 | North closure 14 -> 164, shift_cost 15 -> 145 |
| h5 | both packages | none | North closure 13 -> 313, pool 49 -> 949 | East closure 13 -> 193, South 16 -> 136 |
| h6 | both packages | South closure 16 -> 6, North 19 -> 9 | none | East closure 19 -> 179, pool 59 -> 519 |
History: r1a-r1f kept 29-69% then 18-37% for single slips; fixes were trap cells that move the plan
(pool limit, in-season closures, not rates), digits split so every slip parses (WRONG not CRASH), two cells
per family, and every in-season hidden closure carried in the notice (r1f h2 had one closure cell only).

## Design blind row, redesign 1 (blind d0dc88d, scored 01 Nov 01:13)
Run: score-d0dc88d (Docker, 4g / 2 cpus, perl alarm 60 s), program WORK/proto/blind_r1/derive_report.py, script proto/score_r1.sh, shipped seed 2 + h1..h6 (layout 11.4) + single-family corpora h7=1:0:F1, h8=3:0:F2, h9=5:0:F3, h10=6:0:F4.

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| design blind d0dc88d | shipped seed 2 | 0.25 (ref 0.35) | EXACT, terms 528/5290/11 | n/a | yes |
| design blind d0dc88d | h1..h6 (every F1-F4 family on 5 corpora) | 5.5-10.4 (ref 3.9-5.2) | EXACT 6/6, every family incl. empty-axis checks and data_quality | 120/120 | yes |
| design blind d0dc88d | h7..h10 (one family each) | 7.9-10.5 | EXACT 4/4 | 80/80 | yes |

Total hidden lever kept 200/200 = 100%; 0 WRONG, 0 TIMEOUT, 0 CRASH. Reader method: officeDocument relationship lookup, skips w:del and w:moveFrom, picks the first mc:Choice whose Requires prefixes all map to the WordprocessingML namespace else mc:Fallback, cell text stripped: the profile sentence implemented literally. Planner = per-base exact DP plus pool knapsack and global start/finish vector tie (same as 24bff4e). Verdict: NO CORE (second).
