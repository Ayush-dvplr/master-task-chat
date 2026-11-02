# STACKING_CHECK: match-replay-desync-audit (Harden P9 v2 r1)

Tool: `master_chat_tasks/tools/stacking_check.py` (raw output in `stacking_check_tool.txt`); every row below confirmed by reading `tests/test_output.py`. Reflex = real agent program (`agent_program/optimize.py`) and its adapted copy (`agent_program/adapted/optimize.py`), scored with the real `tests/test_output.py` through a local rewardkit stub (oracle 157/157, negatives silent).

## (a) Test map

| test | w | observable | decisive logic | levers | reflex (agent / adapted) |
|---|---|---|---|---|---|
| format_program_delivered | 1 | optimize.py parses (shipped) | ast.parse of delivered program | - | PASS / PASS |
| record_derivation_matches | 1 | bottleneck_analysis.json (shipped) | record_derivation_ok: values, rejected order, falsifiers, calibration table | - | PASS / PASS |
| instance_scenario_visible | 1 | scenario_visible.json (shipped) | _match_shipped whole doc | - | PASS / PASS |
| instance_perf_report | 1 | perf_report.json (shipped) | _match_shipped whole doc | - | PASS / PASS |
| instance_recommendations | 1 | recommendations.json (shipped) | _match_shipped whole doc | - | PASS / PASS |
| instance_data_quality | 1 | data_quality.json (shipped) | _match_shipped whole doc | - | PASS / PASS |
| instance_report_serialization | 1 | four shipped reports, text | json.dumps indent 2 + newline byte compare | - | PASS / PASS |
| general_scenario_peak | 5 | scenario_peak.json on fresh corpus cadence-peak | _held_out + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_scenario_steady | 5 | scenario_steady.json on fresh corpus cadence-steady | _held_out + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_scenario_latency | 5 | scenario_latency.json on fresh corpus cadence-latency | _held_out + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_sealed_inverse | 5 | scenario_visible.json on fresh corpus trap-sealed (only the sealed bit live) | _trap_only(sealed) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_chained_inverse | 5 | scenario_visible.json on fresh corpus trap-chained (only the chained bit live) | _trap_only(chained) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_stepped_inverse | 5 | scenario_visible.json on fresh corpus trap-stepped (only the stepped bit live) | _trap_only(stepped) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_drifted_inverse | 5 | perf_report.json on fresh corpus trap-drifted (only the drifted bit live) | _trap_only(drifted) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_woven_inverse | 5 | scenario_visible.json on fresh corpus trap-woven (only the woven bit live) | _trap_only(woven) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_echoed_inverse | 5 | scenario_visible.json on fresh corpus trap-echoed (only the echoed bit live) | _trap_only(echoed) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_flipped_inverse | 5 | data_quality.json on fresh corpus trap-flipped (only the flipped bit live) | _trap_only(flipped) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_padded_inverse | 5 | scenario_visible.json on fresh corpus trap-padded (only the padded bit live) | _trap_only(padded) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_shadowed_inverse | 5 | scenario_visible.json on fresh corpus trap-shadowed (only the shadowed bit live) | _trap_only(shadowed) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_spun_inverse | 5 | perf_report.json on fresh corpus trap-spun (only the spun bit live) | _trap_only(spun) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_aliased_inverse | 5 | scenario_visible.json on fresh corpus trap-aliased (only the aliased bit live) | _trap_only(aliased) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| trap_warded_inverse | 5 | data_quality.json on fresh corpus trap-warded (only the warded bit live) | _trap_only(warded) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_deep_identity_chain | 5 | scenario_visible.json on fresh corpus deepchain | _mutant(deepchain) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_charter_cap_surplus | 5 | data_quality.json on fresh corpus cap | _mutant(cap) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_empty_charter | 5 | perf_report.json on fresh corpus emptycharter | _mutant(emptycharter) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_window_boundary_shift | 5 | scenario_visible.json on fresh corpus boundary | _mutant(boundary) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_degenerate_window_live | 5 | scenario_visible.json on fresh corpus degenerate | _mutant(degenerate) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_dead_window | 5 | data_quality.json on fresh corpus deadwindow | _mutant(deadwindow) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_reversal_density | 5 | perf_report.json on fresh corpus reversalflip | _mutant(reversalflip) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_population_scale | 5 | scenario_visible.json on fresh corpus population | _mutant(population) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_baseline_scale | 5 | recommendations.json on fresh corpus scale | _mutant(scale) + _compare whole doc | - (bench report is allowance independent; scale corpus never binds) | PASS / PASS |
| general_reversal_tiebreak | 5 | perf_report.json on fresh corpus tiebreak | _mutant(tiebreak) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_cadence_partition | 5 | scenario_burst.json on fresh corpus partition | _mutant(partition) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_fixpoint_new_unit | 5 | perf_report.json on fresh corpus newunit | _mutant(newunit) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| general_donor_table_rotation | 5 | scenario_visible.json on fresh corpus donorretire | _mutant(donorretire) + _compare whole doc | L1 L3 L4 | FAIL / FAIL |
| mutation_cadence_modulus_moves_only_classes | 5 | cadence marks of scenario_visible, base vs cadence_modulus=7 | _mutation_pair; produced class per unit equals expected on both | L1 (control-side family alone) | PASS / PASS |
| mutation_window_split_moves_only_amounts | 5 | perf_report.json, base vs split window | _mutation_pair; whole perf_report on both; precondition tick marks equal | L3 L4 | FAIL / FAIL |
| negative_hardcoded_sample_answers | -5 | program source literals | shipped settled figures baked in | act: hardcoding | silent / silent |
| negative_filename_dependent_behaviour | -5 | output under renamed corpus dir | output differs by directory name | act: file names | silent / silent |
| negative_reads_supplied_answer_data_at_runtime | -5 | program source | fixed /app/out report path literal | act: reads beyond argument | silent / silent |
| negative_rebinds_verifier_dependencies | -5 | program source | names /tests, test_output, /logs/verifier | act: grader machinery | silent / silent |

TS-26: the tool groups tests that share a document name and the `_compare` helper. They are not duplicates: each stages its own corpus (distinct tag, seed `corpus_seed(tag)` and tweak or single live transform bit), so each reads a different observable (one document of one distinct fresh input) and fails for a different decode or engine reason before the allowance layer. TS-13: one `_compare` per test; the two mutation tests assert one property each (one family moves, read on base and moved corpora).

## (b) Penalty groups by act (AL-28)

| act | tests | judge | sum |
|---|---|---|---|
| hardcoding shipped answers | negative_hardcoded_sample_answers -5 | - | 5 |
| output depends on file names | negative_filename_dependent_behaviour -5 | - | 5 |
| reads graded reports beyond its argument | negative_reads_supplied_answer_data_at_runtime -5 | - | 5 |
| reaches into grader machinery | negative_rebinds_verifier_dependencies -5 | - | 5 |
| edits outside its scope | - | R6 -3 | 3 |
| false claim a control reproduced (honesty) | - | R10 -5 | 5 |

Every act <= 5. No negative grades a lever reading (removed: nondeterministic output, judge hardcoding duplicate R15, cancellation-claim R17).

## (c) Shares and caps

- Positive test weight 157: whole-document on fresh inputs 140 (89.2%, >= 50%), isolated + mutation 10 (6.4%, <= 30%), shipped-only 7 (4.5%, <= 5%), format on hidden 0.
- Tests 41 (cap 70; QC WARN above 35, kept: 12 transform traps and 13 engine generalisations each stage a distinct corpus), criteria 11 (cap 70). Weight-1 checks are the seven shipped-only checks, none core.
- Judge batched; J1 hints none; J2 conduct criteria R7, R8, R9 (one per lever); J3 honesty R10; J4 code shape R11.

## (d) Reflex replay and single-lever table

| program | tests channel | positive checks failed |
|---|---|---|
| real agent program (final optimize.py) | 17/157 = 0.1083 | 28 |
| adapted copy (`!= 1` -> `< 1`) | 17/157 = 0.1083 | 28 |
| oracle with per-entry cap (L3 reflex, pre-harden rule) | 17/157 = 0.1083 | 28 |
| oracle with one allowance for the whole walk (L4 reflex) | 17/157 = 0.1083 | 28 |
| oracle drawing on the opening charter (L3 variant) | 22/157 = 0.1401 | 27 |
| oracle letting cancelled entries draw (L3 ordering variant) | 22/157 = 0.1401 | 27 |

Oracle 157/157 = 1.0000. Shipped reports of every variant are byte-equal to the oracle's (W5: shipped data does not separate). Reflex gate <= 0.20: PASS at 0.1083 (first try).

STACKING PASS
