# RECHECK_FIX: match-replay-desync-audit, P12 v3 round 4 (board c958296, QC v4 board 54df6dc)

Kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 (expected, matches). Tree sha at start 7b0bc6233c65 (matches issue).
Levers (WORK/LEVERS.md): L3 running charter allowance, L4 renewal at live-window openings, L1 green control.

## Findings

| ID | label | rule quote (kit file:line via checks.json) | evidence quote (bundle file:line) | decision | playbook row | effect per lever (L3 / L4 / L1) | files changed |
|---|---|---|---|---|---|---|---|
| F1 DS-22 (fail, v4.md:147) | REAL | 02_Data_Solution_QC.md:78 "A TRUTH.md that describes a different task, a superseded solution, or grading that does not exist is worse than none" | solution/TRUTH.md:112-115 "Every graded document is compared whole, except that the flipped and warded trap tests sum the retired and off window drop counts" vs tests/test_output.py:2386-2388 "# Cadence and the capture count are graded by their own checks." / "produced, wanted = _settled_view(produced), _settled_view(wanted)" | FIX: sentence rewritten to the shipped comparisons (see Deviations: master wording adjusted for :2465 and :2665) | DS-22: rewrite TRUTH to shipped code, sha by script last | none / none / none | solution/TRUTH.md |
| M1 IN-16 (minor, v4.md:111-113) | REAL | 01_Instruction_QC.md:46 "IN-16 nothing graded has two defensible readings the contract fails to settle" | tests/test_output.py:852-861 counts retired before `admits(windows, row["tick"])`; solve.py:520-524 same order; environment/data/engine-rules.md:3-5 "which is not the order in which the simulation consults them"; :26-27 and :37 give the two drop rules with no order | FIX in contract: one sentence under `## Windows` of engine-rules.md (and its embedded copy in tests/test_output.py STATIC_NOTE_TEXT); not a lever, states the graded order only, explains no carve-out (LEVER_RULES W1) | IN-16: settle in the governing file, general case | none / none / none | environment/data/engine-rules.md, tests/test_output.py (embedded note text only) |
| M2 TS-14 (minor, v4.md:167) | REAL | 03_Tests_QC.md:45 "the name and the `description` match what the body checks" | tests/test_output.py:2940 "a fresh capture set with a three deep succession chain settles to its whole scenario report." (also :2920, :2925, :2930, :2935, :2955, :2960, :2975, :3000) vs _compare :2386-2388 which sets aside cadence and capture count | FIX: ", cadence and capture count aside" appended to the nine descriptions and to the five general docstrings that said "whole scenario report" (:2592, :2607, :2612, :2627, :2652); the four damage docstrings :2572-2587 already said it | TS-14: narrow the wording to the body | none / none / none | tests/test_output.py (descriptions, docstrings) |
| M3 AL-7 (minor, v4.md:232) | REAL | 05_Alignment_Integrity_QC.md:32 "every number or claim presented as measured (scores, solve rates, \"oracle scores 1.0\", timing ladders) must be plausible and marked for what it is" | solution/TRUTH.md:208-209 "and the overall score at a judge share of 90 percent:" and column `overall at judge 90` (:211-224) | FIX: column and clause deleted; "tests earned" kept, header says test-channel points out of 172 | AL-7 / score labelling: tests-only | none / none / none | solution/TRUTH.md |
| W1 DS-20 (warn, v4.md:142) | REAL | 02_Data_Solution_QC.md:68 "Any divergence between stated rule and oracle behaviour is a fail, even when no current test would catch it." | solution/solve.py:697 `target = values[UPKEEP_QUANTITY] * fitted["total_base"]`, :699 `carried = sum(row["upkeep"] for row ...)` plain ints vs instruction.md:11 "Carry every amount, share, stock and target through the decimal or rational facility of the standard library rather than binary floating point." | FIX the oracle: target and carried built as fractions.Fraction; outputs byte-identical on shipped + 38 hidden corpora | DS-20: fix the oracle, never the contract | none / none / none | solution/solve.py |
| W2 TS-23 / A3 (warn, v4.md:178) | REAL (warn) | 03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)"; tests_qc.py:48 "A3  10..35 checks (fail below 10, warn above 35)." | tests/test_output.py registers 46 checks (tests_qc.py WARN [A3]) | KEEP: no cap on tests (Ayush 24 Oct 12:50); never merge or drop a check to hit a count; recorded in PL_NOTE.md | TS-23: KEEP warn with count and kit line 03:62 | none / none / none | WORK/QC_DEFENCE.md (count 42 -> 46 only) |

Counts: real 6, false positive 0, unsure 0; fixed 5 (F1, M1, M2, M3, W1), kept 1 (W2).

## Test-logic diff summary

`diff WORK/trap/before_v3r4/tests/test_output.py BUNDLE/tests/test_output.py`: `1729a1730,1732` (the new engine-rules.md sentence in the embedded `STATIC_NOTE_TEXT` copy, data text that hidden corpora ship as their note) plus 14 changed lines, all `description=` strings or docstrings gaining ", cadence and capture count aside". No assertion, helper, corpus generator, weight or registration line changed; `tests/reward.toml`, `tests/judge.toml`, `tests/test.sh` and `tests/Dockerfile` are byte-identical. `python3 tests/test_output.py notes` prints `all embedded notes match shipped: True`; `emit` reproduces environment/data byte for byte. solve.py diff: 4 lines (:209, :602, :697, :699), outputs byte-identical on the shipped corpus and all 38 hidden corpora (WORK/trap/outputs_before_v3r4.txt vs outputs_after_v3r4.txt, 389 lines, `cmp` equal).

## One fact wrong before / after

Before = scores_after_v3r3 (result_878a0e4.json); after = WORK/trap/scores_after_v3r4, variants rebuilt on the new solve.py (single_lever.py for var_*, the r3 hand patches reapplied for mut_* and var_ctrl_all_old, all clean). Tests channel points out of 172.

| variant | before | after | failing tests |
|---|---|---|---|
| oracle | 172 | 172 | none |
| var_perentry (L3) | 97 | 97 | same |
| var_opening (L3) | 97 | 97 | same |
| var_cancelled_draw (L3) | 97 | 97 | same |
| var_norenew (L4) | 97 | 97 | same |
| var_renew_strict (L4) | 162 | 162 | same |
| var_precedence | 161 | 161 | same (instance_data_quality, general_charter_cap_surplus, general_dead_window) |
| var_tiebreak | 167 | 167 | same |
| var_lifo | 1 | 1 | same |
| mut_zero / mut_carry / mut_stepped / mut_index | 169 each | 169 each | same (only temp paths in tracebacks differ) |
| var_ctrl_all_old | 160 | 160 | same |
| var_carry_eleven | 12 | 12 | same |

Every one-fact-wrong figure is unchanged; no separating hidden case moved.

## Side effects

- IN-16 -> AL-27: the new engine-rules.md sentence states a rule the graded data reaches (9 shipped entries are both retired and outside every live window; general_charter_cap_surplus and general_dead_window reach it too); its loss under the swapped reading is the existing 11/172 above. PASS, no new rule row needed: the rule was already graded.
- AL-7 -> DS-27: grep TRUTH.md for process narration (round, QC, fixed, reviewer, earlier): only task prose (:100, :240 "fixed" as in a figure pinned by earlier stages; :181, :291 the judge reviewer). PASS.
- DS-22, TS-14, DS-20: no listed side effects. Always 14 rechecked: no em or en dashes, LF only, no TODO/FIXME, no `__pycache__`.
- Citations: the inserted note lines shift engine-rules.md by 3 and test_output.py by 3 below :1729; WORK DESIGN.md, LEVERS.md and QC_DEFENCE.md citations moved and checked against the new lines; XREF.md gained four entries (drop order, settled-view descriptions, TRUTH compare sentence, test-channel scores only).

## Docker block

Copies by live kit `exe_copy.py` (plain, `--owner-only`, `--stub`) in `/tmp/opencode-logs/match-replay-desync-audit-p12v3r4-20261024T211754-b81f`; one nohup chain, warm verifier image first, ends `ALL_DONE Sat Oct 24 21:21:37 IST 2026`. Chain and log: `docker_block/chain.sh`, `docker_block/runs.log`.

| run | reward |
|---|---|
| warm verifier image | rc 0 |
| oracle-1 | 1.000 (agent log prints `check R7 ok`, `check R8 ok`, `check R9 ok`) |
| oracle-2 | 1.000 |
| oracle-3 | 1.000 |
| owner-only-1 | 1.000 |
| nop-1 | 0.000 |
| stub-1 | 0.0058 (format_program_delivered only, 1/172 of the tests channel) |

## Checks after the last edit

Last bundle edit: TRUTH.md `solve_py_sha256` by script (20987612aa54...). After it: xref_check 32 entries, 0 findings; `precheck.sh` last line PRECHECK CLEAN (A3 warn 46 checks only); live kit `structure_qc.py`, `instruction_qc.py`, `tests_qc.py`, `judge_qc.py` exit 0, 0, 0, 0 (tests_qc only `WARN [A3] 46 checks; cap is 35`); `stacking_check.py` PASS (OUT/STACKING_CHECK.md); Docker block above; `find BUNDLE -name __pycache__` empty; tree sha `1cd9fe77061b`.

## QC_RULINGS rows

| rule | bundle | finding | ruling |
|---|---|---|---|
| DS-22 | match-replay-desync-audit v4:147 | TRUTH said every document is compared whole; scenario_visible comparisons on fresh sets drop capture count and cadence | FAIL; rewrite to shipped comparisons |
| IN-16 | match-replay-desync-audit v4:111 | order of the retired and off window drops for an entry that is both, settled only by instruction.md:5 | MINOR; one general sentence under Windows in engine-rules.md |
| TS-14 | match-replay-desync-audit v4:167 | "settles to its whole scenario report" on tests whose body sets cadence and capture count aside | MINOR; narrow the descriptions |
| AL-7 | match-replay-desync-audit v4:232 | TRUTH one-fact-wrong table gave an overall score at an assumed judge share | MINOR; test-channel points only |
| DS-20 | match-replay-desync-audit v4:142 | upkeep target and bench upkeep held as plain ints against instruction.md:11 | WARN; carry them as Fraction in the oracle |
| TS-23 | match-replay-desync-audit v4:178 | 46 checks over 35 | WARN; kept (no cap) |

## Deviations from master directions

- F1: the given sentence ("every scenario_visible comparison sets aside the capture count and each unit's cadence class") is contradicted by `test_instance_scenario_visible` (test_output.py:2468, `_match_shipped`, whole compare including capture count and cadence) and by `test_mutation_cadence_modulus_moves_only_classes` (:2668, compares only each unit's cadence class). I scoped it to "on a fresh capture set each scenario_visible comparison", added the cadence modulus clause, and opened with "Every check that compares a produced document with its settled one" because several checks (format, derivation record, report listing, negatives) compare no settled document. The failing-check clause was kept as its own sentence.
- M1: sentence used word for word; it is also inserted in the embedded copy of engine-rules.md in tests/test_output.py (`STATIC_NOTE_TEXT`), which hidden corpora ship, so the test_output.py diff carries 3 note lines besides descriptions. Playbook row 28 would route a non-lever open case to the generator, but the shipped data already reaches it (9 entries), so the contract sentence the master gave is the only in-scope fix.
- W1: besides :697 and :699, bench upkeep is made a Fraction where it is parsed (:209, so the subset sums in `exact_bench` and `carried` are Fractions) and the same target figure in the upkeep figure report (:602) is built from a Fraction, so no integer target or upkeep remains in the oracle. Outputs byte-identical.

## Lessons for the master

- The DS-22 replacement sentence said "every scenario_visible comparison" but one shipped-instance test and one mutation test compare differently; scope words in a TRUTH rewrite need checking against every caller of the helper | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md:43 add "check every/each in the new sentence against each caller of the helper it describes"
- IN-16 row routes a non-lever open case to the generator, which cannot help when the shipped data reaches the case | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md:28 add "if the shipped data reaches it, one general sentence in the governing note (match-replay v4:111)"
- A note sentence also lives in the tests' embedded note copy and shifts every later citation of that note in WORK | template_change: master_chat_work/20261024_process/qc_reverse/B/FIX_SIDE_EFFECTS.md:22 add "embedded note copy in tests + citation shift" to the IN-16 row
- Making a quantity a Fraction where it is parsed fixes every derived sum in one line and keeps outputs identical | no change: playbook DS-20 row already says fix the oracle
