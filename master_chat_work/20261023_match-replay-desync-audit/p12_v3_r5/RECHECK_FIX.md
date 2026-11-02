# P12 v3 r5 recheck and fix: match-replay-desync-audit (board 57e415c)

QC report: `QC/reports/match-replay-desync-audit/v5.md` (board d6af3da, kit 976c1666). Tree sha at issue 1cd9fe77061b; after **765e3d04ab89**.
Always 13: the QC copy `QC/copies/d6af3da/match-replay-desync-audit` is byte-identical to the pre-fix bundle (`diff -rq` on tests/solution/environment prints nothing); the cited lines read as quoted (test_output.py:463 `_plant_divergence(plan)`, 553 `def _plant_divergence`, 2083-2084 postcondition, TRUTH.md:224 `| ... latest entry ... | 1 |`). No NOISE row.

## Findings

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever (L1 / L3 / L4) | files changed |
|---|---|---|---|---|---|---|---|
| F1 CL-4 (v5.md:37, 220) | REAL | `05_Alignment_Integrity_QC.md:77` "CL-4 one wrong fact costs about one fact: one-fact-wrong score computed, no almost-right answer scoring as entirely wrong"; checks.json discretion "One wrong fact should cost about one fact's worth of reward." Severity fail (05:115). | `solution/TRUTH.md:224` "\| reversal cancels the latest entry of its kind \| 1 \|"; `tests/test_output.py:463` `_plant_divergence(plan)` on every corpus; L2083-2084 "the two cancellation orders never part; plant a divergence". Measured BEFORE: var_lifo 1/172. | FIX (partition, with deviation below) | CL-4 DO "Partition: ... each settlement rule keeps its own hidden tests; report one-fact-wrong per rule ... Re-run every one-rule variant after the partition (LEVER_RULES G10)"; NEVER column avoided (no corpus lightened until a lever has no separating test; levers untouched) | L1 none (ctrl rows 169/160 unchanged); L3 none to slightly easier on one variant (opening charter 97 -> 102, loss 75 -> 70, 93.3% kept); L4 none (97 / 162 unchanged) | tests/test_output.py, solution/TRUTH.md; WORK DESIGN.md, COST_TABLE.md, RULE_COVERAGE.md, XREF.md |
| W1 A3 / TS-23 (v5.md:39, 88) | REAL (warn) | `03_Tests_QC.md:62` "TS-23 Counts and balance: at least 10 checks (fail), at most 35 (warn)"; tests_qc.py:48 "A3 10..35 checks (fail below 10, warn above 35)." | `tests/test_output.py` 46 checks registered (now L3072-3117 after the +30 line shift); tests_qc prints `WARN [A3] 46 checks; cap is 35 (warn)` | KEEP | TS-23: KEEP as warn with count and kit line 03:62 (no cap); precedent district-heat v4:47, QC_RULINGS TS-23 row | none on all | none (OUT/PL_NOTE.md) |

Totals: REAL 2, FALSE_POSITIVE 0, UNSURE 0; fixed 1, kept 1.

## Test-logic diff summary (tests/test_output.py BEFORE `WORK/trap/before_v3r5` vs AFTER)

Only the corpus selection for `_plant_divergence` and its postcondition changed, plus one named repair that keeps non-grading sets order-neutral:
- L463-464: `_plant_divergence(plan)` now runs only `if _grades_order(plan):`.
- L475-476: `if not _grades_order(plan): _settle_one_order(plan)` after the fits (and after the split refit), before `_check_unbound`.
- L556-558: new `_grades_order(plan)`: `plan["seed"] == CHALLENGE_SEED or plan["tweak"] in ("reversalflip", "tiebreak")` (shipped set, general_reversal_density, general_reversal_tiebreak).
- L561-578: new `_settle_one_order(plan)`: while the two orders part, the first parting reversal is turned, at its root echo slot, into a plain entry of the kind it names; echoes and fits re-run.
- L2111-2114: postcondition "never part" guarded by `_grades_order(plan)`; new mirror postcondition "the two cancellation orders part outside the sets that grade them".
Weights (L3072-3117), every check body, every other generator step unchanged. solve.py untouched (TRUTH sha line matches). Shipped corpus re-emitted by `_write_corpus` is byte-identical to `environment/data`.

## One-fact-wrong rows (tests channel, earned of 172; local_score.py on the bundle data)

| case (variant) | before (r4 tests) | after | move |
|---|---|---|---|
| oracle | 172 | 172 | 0 |
| allowance per entry (var_perentry) | 97 | 97 | 0 |
| allowance never renewed (var_norenew) | 97 | 97 | 0 |
| allowance from opening charter (var_opening) | 97 | 102 | +5: `general_cadence_partition` now passes; its corpus no longer carries the planted reversal unit that made the opening charter visible there |
| cancelled entry draws (var_cancelled_draw) | 97 | 97 | 0 |
| renewal strictly before (var_renew_strict) | 162 | 162 | 0 |
| precedence off window before retired (var_precedence) | 161 | 161 | 0 |
| tie-break ordinal before capture (var_tiebreak) | 167 | 162 | -5: `general_population_scale` now also fails; its settled corpus places tied entries where order matters (harder, not easier) |
| reversal latest entry (var_lifo) | 1 | **157** | +156: fails the five shipped instance checks (program stops at CTRL-J on the shipped set) plus general_reversal_density and general_reversal_tiebreak (15 points) |
| one ctrl note rule (mut_zero / mut_carry / mut_stepped / mut_index) | 169 each | 169 each | 0 |
| all four ctrl rules (var_ctrl_all_old) | 160 | 160 | 0 |
| constants (var_carry_eleven) | 12 | 12 | 0 |

Master checks: (a) latest-entry reading still fails reversal_density and reversal_tiebreak: yes. (b) reversal_lifo 157, inside 100-165; the two other moves of 5 points are explained above. (c) oracle 172/172, so every corpus builds and passes. (d) RULE_COVERAGE reversal row: var_lifo fails 7 tests; Rules uncovered: 0.

Natural corpora: with `_plant_divergence` removed from every corpus, **50 of 50** natural seeds (tweak None, EVAL_SEED+1000+i*7919) part on cancellation order by themselves (reversals are about a quarter of all entries). So the rule is not exercised only by planted corpora; it is exercised by nearly every corpus. With planting removed everywhere and nothing else changed, var_lifo scored 6/172.

## Trap survival (playbook section 3; loss = points lost by the lever's variants)

| lever | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| L1 green control (mut_* / var_ctrl_all_old) | 3 / 12 | 3 / 12 | 100% | all damage tests | PASS |
| L3 running charter allowance (var_perentry / var_opening / var_cancelled_draw) | 75 / 75 / 75 | 75 / 70 / 75 | 100% / 93.3% / 100% | 15 / 14 / 15 | PASS (>= 90%) |
| L4 renewal at window openings (var_norenew / var_renew_strict) | 75 / 10 | 75 / 10 | 100% | all | PASS |

G10 cost table rows re-run on the AFTER bundle: L3 worst 97/172, L4 97/172, L1 172/172 tests channel; overall at rubric 90 = 73.20; same as r4, no gate change.

## Side effects

FIX_SIDE_EFFECTS.md has no CL-4 row; general ids re-checked by hand:
- DS-22: TRUTH.md table rows (opening 102, tie-break 162, latest 157) and the paragraph below it match the measured run; no TRUTH line claims divergence is planted on every corpus (grep `plant|diverg` hits only L145 damage tests). PASS.
- TS-19: engine-rules.md:87 "cancels the earliest still uncancelled entry" is still graded (shipped instance checks, general_reversal_density, general_reversal_tiebreak). PASS.
- AL-27: the grading sets construct the situation: `_plant_divergence` still seats the parting unit there and var_lifo fails both reversal generalisation tests. PASS.
- TS-26 / TS-13 / TS-25: no test body, observable or weight changed; stacking_check groups are the same 7 hand-checked groups as r4 (different hidden inputs). PASS.
- Author-only `pins` mode (not a test, never run by the verifier): over 20 alternative seeds 18/20 pass `assert_postconditions` after the fix (20/20 before); seeds 130822 and 210012 trip the shipped-only share postcondition "charter sable gives away the whole". Shipped seed unaffected. Noted, not fixed (out of scope).

Gates: xref_check `33 entries, 0 findings`; precheck last line `PRECHECK CLEAN`; kit structure_qc / instruction_qc / tests_qc / judge_qc exit 0,0,0,0 (tests_qc VERDICT WARN for A3 only; outputs OUT/kit_*.txt); stacking_check PASS after hand correction (OUT/STACKING_CHECK.md); no `__pycache__`.

## Docker block

Copies by live kit `exe_copy.py` (plain, `--owner-only`, `--stub`) in `/tmp/opencode-logs/match-replay-desync-audit-p12v3r5-20261024T224735-ff1f`; warm verifier image first (warm rc=0), one nohup chain ending `ALL_DONE Sat Oct 24 22:52:20 IST 2026`. Chain and log: `docker_block/chain.sh`, `docker_block/runs.log`.

| run | reward |
|---|---|
| oracle-1 / -2 / -3 | 1.0 / 1.0 / 1.0 |
| owner-only-1 | 1.0 |
| nop-1 | 0.0 |
| stub-1 | 0.0058 (format_program_delivered only, 1/172 of P) |

## QC_RULINGS rows

- TS-23 (existing row, district-heat v4:47 WARN): applied, W1 kept.
- CL-4: no row. Proposed: "CL-4 | a rule-forcing repair applied to every hidden corpus makes one misread cost every test | partition: force it only in the sets that grade the rule, keep the rest order-neutral by a named repair | match-replay 57e415c".

## Deviations from master directions

The direction was to call `_plant_divergence` only for the reversal_density, reversal_tiebreak and shipped corpora and leave every other corpus without planted divergence. Phase 1 measured that this alone cannot meet (b): 50/50 natural corpora already part on cancellation order, and with no planting anywhere var_lifo still scored 6/172. To land the latest-entry reading at 157 (inside 100-165) I kept the master's selection and added one named repair, `_settle_one_order`, that makes every other corpus order-neutral, plus the mirror postcondition. This is the playbook CL-4 DO partition ("each settlement rule keeps its own hidden tests"); weights and check logic unchanged.

## Lessons for the master

- A "remove the forcing repair" direction assumes the rule is rare naturally; measure the natural rate first (here 50/50) | template_change: master_chat_tasks/prompts/templates/P12_recheck_fix_v3.md:42, add "for a CL-4 fix that removes a forcing repair, count the natural trigger rate over 50 seeds first"
- CL-4 verdict flipped between v4 and v5 on unchanged code | no change: recorded in PL_NOTE for Ayush; v5 treated as the rule
- Order-neutral repairs can trip author-only postconditions on non-shipped seeds | no change: author mode only, noted in Side effects
