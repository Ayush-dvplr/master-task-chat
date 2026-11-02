# COST_TABLE (LEVER_RULES G10), P12 v3 r3, AFTER tests (P = 172, 46 checks)

Method: each wrong reading injected alone into the AFTER oracle (`single_lever.py` anchors on solution/solve.py
after F1; `rule_cov/make_mutants.py` for the four CTRL note rules), scored with `local_score.py` on the AFTER
tests and shipped data (tests channel, hidden corpora included). Scores: `trap/scores_after_v3r3/*.txt`.
BEFORE (P = 160): `trap/scores_before_v3r3/*.txt` and QC v3.md:268 for the four rows QC measured.
Overall = 0.5 x tests share + 0.5 x rubric share (reward.toml), judge negatives taken as 0. Previous table:
COST_TABLE_P12v3r2.md.

| lever | wrong reading | tests lost / P | share |
|---|---|---|---|
| L3 running charter allowance | per-entry cap, never drawn down (var_perentry) | 75 / 172 | 0.436 |
| L3 running charter allowance | draw on the opening charter (var_opening) | 75 / 172 | 0.436 |
| L3 running charter allowance | cancelled entries draw before the skip (var_cancelled_draw) | 75 / 172 | 0.436 |
| L4 renewal at live-window openings | one allowance for the whole walk (var_norenew) | 75 / 172 | 0.436 |
| L4 renewal at live-window openings | renewal only after the opening tick, strict `<` (var_renew_strict) | 10 / 172 | 0.058 |
| L1 green control | "every control reproduces, so settlement is right" (no code edit of its own) | 0 / 172 | 0.000 |
| CTRL note rules as a group (CTRL-C zero fill, CTRL-G carry reset, CTRL-H none as 0, CTRL-H index modulo) | all four read the old way (var_ctrl_all_old) | 12 / 172 | 0.070 |
| CTRL-C zero fill | broken payload read as none (mut_zero) | 3 / 172 | 0.017 |
| CTRL-G carry reset | carry kept across a none (mut_carry) | 3 / 172 | 0.017 |
| CTRL-H stepped none | stepped series stops at a none (mut_stepped) | 3 / 172 | 0.017 |
| CTRL-H index modulo | out-of-range index read as none (mut_index) | 3 / 172 | 0.017 |
| reversal order | latest uncancelled entry, LIFO (var_lifo) | 171 / 172 | 0.994 |
| walk order | tie broken by ordinal before capture (var_tiebreak) | 5 / 172 | 0.029 |
| drop precedence | off-window checked before retired (var_precedence) | 11 / 172 | 0.064 |
| F-03 (not a lever) | eleven quantities carried in source (var_carry_eleven) | 160 / 172 | 0.930 |

LIFO costs everything because the program cannot pass its own CTRL-J control under that reading (the control
figure reads settled tick totals), so it stops; this is a calibration property, not a test cascade.

## One fact wrong (CL-4)

| case | tests earned / P | share | tests lost |
|---|---|---|---|
| one CTRL rule wrong (any of the four) | 169 / 172 | 0.983 | its own damage test |
| one settlement rule wrong: precedence swap | 161 / 172 | 0.936 | instance_data_quality, general_charter_cap_surplus, general_dead_window |
| one settlement rule wrong: renewal strict `<` | 162 / 172 | 0.942 | general_scenario_latency, mutation_window_split_moves_only_amounts |
| one settlement rule wrong: walk tie-break | 167 / 172 | 0.971 | general_reversal_tiebreak |
| one settlement rule wrong: allowance per entry / opening charter / cancelled draw / no renewal | 97 / 172 | 0.564 | the 15 heavy general and mutation tests where an allowance binds |
| one settlement rule wrong: reversal LIFO | 1 / 172 | 0.006 | all but format_program_delivered (program stops at CTRL-J) |

## All levers right but one (G10 rows)

| wrong lever | tests earned / P | overall at rubric 90 | overall at rubric 97.67 (v0) |
|---|---|---|---|
| L3 only (worst of three readings) | 97 / 172 | 73.20 | 77.03 |
| L4 only (no renewal) | 97 / 172 | 73.20 | 77.03 |
| L1 only | 172 / 172 | 95.00 | 98.84 |

## G10 verdict: FAIL on L1 (as before) and now on L3 and L4 at rubric 90

- L3 and L4 still cost 43.6% of P alone (gate >= 25%: PASS), but after F4 their single-wrong rows sit at 73.20
  overall at rubric 90 (gate < 70: FAIL). This is the approved effect of F4: the twelve trap tests no longer
  pay for an allowance slip. Not changed further this round (no new levers, no data change).
- L1 is an amplifier: alone it costs 0 points.

## Probe program after (probe run 1 optimize.py on AFTER tests)

| program | tests earned / 172 | tests % | overall at rubric 17.65 | overall at rubric 90 |
|---|---|---|---|---|
| probe run 1 agent | 75 | 43.60 | 30.63 | 66.80 |

Lost: 16 trap and damage tests (exit -9 at 120 s, branch explosion in its calibration), 5 general/mutation tests (calibration failed at CTRL-J). Gate tests < 100 and overall < 70: PASS. Kill rule (probe tests >= 95): not hit.
