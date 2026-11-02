# TRUTH.md - 00372225-134c-56e6-80ea-8bd47c66c816

## Defect

Nothing in the shipped bundle is broken source waiting to be patched. The task is a faulty-computation correction task: the agent is handed one run of a clinical-assay quality-control recalibration, a written specification of how the reconciled report is computed, and a corpus engineered so that every obvious shortcut computes a wrong report. The work is to read the specification, recover the load-bearing method coefficients and governance constants from the two binary documents, apply the interacting recalibration stages in the fixed order, and derive the exact reconciled report plus a reusable program that reproduces it on unseen runs. The committed per-analyte per-batch result is the spine; every other figure is a projection of it, so one wrong interacting decision reaches the report as many wrong figures at once.

1. (focal) The method coefficients and the per-analyte linear recalibration parameters live only in the LIVE sheet of `recalibration_grid.xlsx`, selected by matching the sheet first-row tag to `run_profile.calibration_tag` ASSAYCAL-L7. A solver that reads the DRAFT sheet, or the plain-text `flat_coeff_archive.csv`, computes wrong method gains and flat recalibration and fails `recalibration_live_sheet_applied` and the whole exact tier. Reading the DRAFT sheet scores 0.150 on Channel A.
2. (focal) The five governance constants RECOVERY_FLOOR_BP, FLOOR_RESULT, DAMPING_SEED, BATCH_CAP and CARRYOVER_CEILING live only inside the `governance_envelope.pdf` content stream as parenthesized show-text operators. A solver that never opens the pdf has no floor, no cap, no ceiling, and fails `recovery_floor_applied`, `carryover_reprojection_exact`, and every exact test.
3. (focal) The recalibration stages interact through a shared running state: batch placement feeds admission, unit scaling feeds the method transform, the method transform feeds recalibration, recalibration feeds the recovery reweight, the reweight feeds per-batch admission with channel carry, admission feeds convergence, and convergence feeds the carryover clawback. `analyte_allocations_match_reference` and `core_three_files_all_exact_on_challenge` fail unless the whole chain is exact.
4. (focal) The recovery reweight raises each reading recovery to at least the governance floor before reweighting. Multiplying by the raw recovery is the natural reading and computes a wrong spine, caught by `recovery_floor_applied`. Skipping the floor with every other stage correct scores 0.570 on Channel A.
5. (drift) The effective lot is the smaller of the two declared lots, not the larger, and it decides which batches are eligible through their min_lot. An experienced solver expects the newest lot to win and takes the maximum, which admits the b_recheck batch whose min_lot is five. Taking the larger lot scores 0.260 on Channel A.
6. (drift) The half-up fixed-point rounding is applied at three separate named stages, the method transform, the recalibration, and the recovery reweight. The arithmetic is signed Q16.16 as `precision_and_rounding.md` defines it. The tidy instinct is to carry full precision and round once at the end, which is more accurate but wrong, and fails `staged_rounding_fixedpoint_exact` and the exact tier.
7. (trap) Readings whose is_qc_fail column is set are excluded before ordering and every rollup, never entered into the pipeline, and those are exactly the ids `excluded_reading_ids` and `excluded_readings.json` report. A solver that treats them as ordinary rows fails `qc_fail_rows_excluded_before_ordering` and shifts every downstream total.
8. (trap) The matrix shift is added after the floor clamp, not before, and it is a whole-unit offset carried in the `matrix_shift_units` column rather than a scaled one. The admission carry flows per channel in the descending-id admission order, a reading no batch covers leaves that carry standing, and carry still standing at the end of the run seats on the first analyte and batch that channel admitted. Reversing any of these produces a spine that passes the shape tests but fails the exact tier.

Every rule above is stated in the shipped specification under `environment/data/`: the pipeline contract, the nine per-stage notes, the rounding and precision note that fixes the Q16.16 representation, the output artifact contract that fixes every byte of every artifact, the footguns note, and the supersession index. The difficulty is reading them carefully and implementing exactly, not guessing an unwritten convention.

The reference implementation is Python standard library only. Grading runs two channels. Channel A is the deterministic suite in the verifier that grades artifact and state correctness: every committed figure, every artifact byte, every held-out reproduction, and whether the delivered program's output moves when only the superseded files change. Channel B is the judged channel in `tests/judge.toml`, and it owns only what no assertion can read: whether the agent consulted the shipped specification before building, whether it kept the arithmetic exact, whether it reported its figures and whether any reported figure was one no run produced, whether it checked its program for run-to-run determinism before reporting, whether it inspected each of the two binary documents before writing its parser, whether the delivered program meets ordinary Python review standards for error handling, and whether it left the shipped inputs untouched. No artifact value is graded in both channels, and no judged criterion reads an observable a Channel A check already reads.

Out of bounds: writing the shipped reading identifiers or the calibration tag into the program as live string literals is caught by `negative_hardcoded_sample_answers`; naming the verifier tree or its grading output files in a live string literal is caught by `negative_names_verifier_paths`; importing a non-stdlib package is caught by `negative_external_dependency`; nondeterministic output is caught by `negative_nondeterministic_output`; and deriving anything from a file the supersession index marks as superseded is caught by `negative_superseded_source_used`. Transcribing shipped figures earns nothing beyond the shape checks, whether they are written into the artifacts or into the program, because every graded figure must also be reproduced by running the delivered program and every check that grades a figure of the shipped run also grades it on an unseen run in the same layout.

## Load-bearing work

The graded deliverables are the reusable program `/app/out/derive_report.py` and the twenty-one report artifacts it must produce. The three core files summary.json, policy_audit.json and panel_analyte_glucose.json gate the whole-run tests through the full-core gate and are hashed in that fixed order to form the core digest.

- `/app/out/summary.json` carries batch_totals, analyte_allocations, convergence_rounds, and unsettled_batches.
- `/app/out/policy_audit.json` carries tier_totals, carryover_ledger, excluded_reading_ids, excluded_count, effective_lot, and ordered_reading_ids.
- `/app/out/data_quality.json` carries objective_value, tier_totals, committed_grand_total, carryover_total_units, core_files, and core_sha256.
- The four `/app/out/panel_analyte_*.json` files carry the per-analyte matrix, tier, committed total, and per-batch split.
- `/app/out/matrix_rollup.json` and `/app/out/tier_rollup.json` carry the matrix-axis and tier-axis class totals and memberships.
- `/app/out/analyte_totals.json`, `/app/out/tier_analyte_membership.json`, `/app/out/ordered_reading_index.json`, and `/app/out/excluded_readings.json` carry supporting projections of the spine.
- `/app/out/analyte_committed.csv`, `/app/out/batch_committed.tsv`, and `/app/out/matrix_weighted.psv` carry the same figures in the delimited formats.
- `/app/out/carryover_ledger.xml`, `/app/out/objective_summary.yaml`, `/app/out/reconciliation_report.md`, and `/app/out/run_status.txt` carry the carryover ledger, the objective summary, the narrative, and the status line.
- `/app/out/provenance_manifest.json` folds the artifact list, the core file order, and the core digest.

Out of bounds by design: the delivered program reads only its two positional directories, uses only the Python standard library, and derives every figure rather than transcribing a single shipped file.

## Verification

`tests/test.sh` hardens the verifier and hands grading to pinned rewardkit 0.2.1, which scores the two channels and writes the reward itself. Channel A is `tests/test_output.py`: thirty-five rewardkit criteria, thirty positive summing to a positive total of 100 and five negative summing to negative twenty-one, each weight carried on its own `criteria.<name>(weight=W)` registration. Channel B is `tests/judge.toml`: nine judged criteria, seven positive summing to 21 and two negative summing to eight. `tests/reward.toml` gives each channel half the final score, dividing by that channel's positive total, so Channel A contributes `0.005` per test point and Channel B `0.5 / 21` per judge point. A run that passes everything and trips nothing scores 1.000.

Every check that runs the delivered program runs a world-readable copy of it as an unprivileged user, so the file mode an editor gave the artifact never decides a score. Every figure graded on the shipped run is read from the agent's declared artifact and must also be reproduced byte for byte by running the delivered program on a freshly regenerated copy of the shipped run, so a hand-written artifact set with no working program earns only the six shape points. Each of those checks also runs the delivered program on an unseen regeneration of the run and grades the same figure there, and four_analyte_docs_match_reference is graded on an unseen run of its own because on the shipped run the docs repeat figures other checks already grade, so a program that replays the shipped outputs from an embedded copy also earns only the six shape points. The full three-file core match gates only the six whole-run reproduction checks at weight five. The five other probe checks at weight five and the thirteen mid-derivation checks at weight three each grade their own observable, so one wrong stage costs the checks that exercise it rather than the whole positive suite: measured on Channel A alone, a submission with a single wrong integer in the committed spine scores 0.290, a submission that skips only the recovery floor 0.570, and one that seats overlapping slots in the first calendar entry instead of the last 0.970, against the 0.020 a content-free stub earns and the 0.060 a perfect transcription of the shipped artifacts earns when the delivered program does nothing or only replays them.

`effective_lot_is_smaller_of_two` grades the smaller-lot rule twice over: once on the shipped run and once by running the delivered program against a lot probe whose two declared lots are 9 and 3. That probe is what keeps the check honest. The effective lot is visible in `run_profile.json`, so a check comparing only the shipped figure pays out to a hand-written artifact that transcribes it; on the probe a program taking the maximum reports 9 rather than 3 and admits `b_recheck` in place of `b_ramp`, and an artifact set written by hand has no program to run at all.

Positive tests: the six shape tests at weight one are artifact_set_exists_and_parses, summary_schema_shape, policy_audit_schema_shape, data_quality_schema_shape, manifest_declares_core_order_and_names, and canonical_serialization_sorted_compact. The thirteen mid-derivation tests at weight three are effective_lot_is_smaller_of_two, ordered_reading_ids_match_tiebreak, qc_fail_rows_excluded_before_ordering, batch_totals_match_reference, analyte_allocations_match_reference, convergence_rounds_match_reference, tier_totals_partition_match, analyte_totals_match_reference, four_analyte_docs_match_reference, carryover_ledger_matches_reference, excluded_readings_match_reference, convergence_anchor_tie_break_applied, and carryover_clawback_tie_break_applied. The eleven tests at weight five are the six gated whole-run checks core_three_files_all_exact_on_challenge, all_artifacts_exact_on_visible, held_out_eval_corpus_matches_reference, carry_probe_reproduced_exact, round_control_probe_reproduced_exact and sparse_probe_reproduced_exact, and the five probe checks staged_rounding_fixedpoint_exact, recalibration_live_sheet_applied, recovery_floor_applied, carryover_reprojection_exact and cycling_batch_reports_unsettled.

Every probe corpus is a complete corpus, so a program that reads the tier weight book or any shipped note finds it at grade time. Six probes carry governance constants that differ from the shipped run, so a program that hardcodes the five constants rather than recovering them from the envelope document loses recovery_floor_applied, cycling_batch_reports_unsettled, convergence_anchor_tie_break_applied, carryover_clawback_tie_break_applied, round_control_probe_reproduced_exact and sparse_probe_reproduced_exact. The placement probe declares lots 8 and 5, so b_recheck is eligible and overlaps b_ramp and b_plateau: only the last-calendar-entry rule seats its slot 29 and 30 readings; its slot 31 reading belongs to b_plateau and its slot 60 reading to no batch, because a batch covers its slots up to but not including its to_slot; and its slot 61 reading, which no batch covers, must keep its place in the processing order. batch_totals_match_reference and ordered_reading_ids_match_tiebreak grade it alongside the shipped run. The qc probe puts two flagged readings first on one channel, where admitting them would overrun the batch cap, and qc_fail_rows_excluded_before_ordering grades the spine it produces. The cycling probe drives b_open and b_ramp into two-state cycles whose smallest state sits at opposite ends, the last state before the repeat in b_open and the repeated state in b_ramp, so the check grades the round count of negative one, the unsettled_batches list, the UNSETTLED status line and the reported smallest state together. The convergence tie probe seats glucose and calcium on equal committed mass with the cap below their total, which is the only situation where the name-ascending anchor tie-break decides anything; the clawback tie probe seats glucose and lactate on equal mass over the ceiling for the same reason on the clawback side.

The three gated probes each carry a rule no other corpus triggers. The carry probe leaves carry standing on a channel when an uncovered reading on that channel is processed, so the carry must survive to the end-of-run seat. The round-control probe uses a damping seed of 79025 and a cap of 379, under which b_open is still moving when the sixty-four round budget runs out and b_plateau meets two consecutive rounds of equal residual, which count as non-improving. The sparse probe reads only glucose and creatinine, so the csv still needs a row for every crosswalk analyte and the psv a row for every tier of the tier weight book, and it names its second batch b_r&d with a ceiling low enough to claw from it, so the ledger entry's batch attribute must be XML escaped. held_out_eval_corpus_matches_reference reproduces every artifact on two held-out corpora, which between them exercise the fair-share largest-remainder tie-break and the admission of a negative wanted result.

Negative checks: negative_hardcoded_sample_answers at negative five, negative_names_verifier_paths at negative five, negative_external_dependency at negative five, negative_nondeterministic_output at negative three, and negative_superseded_source_used at negative three. The first two read only the string literals the program can use: comments, docstrings and any literal inside a help, description, epilog or usage keyword argument are excluded, so documenting the shipped run never trips them. negative_hardcoded_sample_answers fires when at least two of the reading ids r0001, r0090 and r0045 and the tag ASSAYCAL-L7 appear among those literals. negative_external_dependency decides what counts as third party from `sys.stdlib_module_names` rather than from a hand-written package list, so it enforces exactly the instruction's standard-library-only rule and never charges a program for importing a standard-library module such as urllib or socket. negative_superseded_source_used runs the program on one corpus twice and then again after giving every file the supersession index lists different values in the same layout, and fires when the artifacts change; a program whose two unperturbed runs already differ is left to negative_nondeterministic_output, so no single act fires both.

Channel B is the nine judged criteria in `tests/judge.toml`. It grades process only: reading the pipeline contract and stage notes before the first write of the program, exact arithmetic in the delivered program, the closing reply naming the objective value and digest and output directory, running the program at least twice and comparing the outputs before reporting, inspecting the workbook and the envelope document each before writing its parser, and the delivered program meeting ordinary Python review standards with no discarded errors, no silent substitute file and no debug residue, plus two negatives: a closing reply stating a figure no run produced, and rewriting the shipped input tree. No criterion reads an artifact value, because Channel A owns every one of those, and no criterion reads an observable a Channel A check already reads.

## Root cause

**Hidden authority.** The load-bearing coefficients and constants live only in the xlsx and the pdf, so a reader who skims the plain-text files converges on the superseded decoy values and computes a wrong spine.

**Interaction.** The stages share a running state and a per-channel carry, so an error in any single stage desynchronizes the shared running state and the channel carry and cascades into many wrong figures rather than one.

**Order sensitivity.** QC-fail exclusion, the descending-id ordering tiebreak, the smaller effective lot with its batch eligibility, the half-open batch windows, and the after-clamp matrix shift each change which readings enter which batch and in which admission order.

**Staged precision.** Rounding is applied at three named stages, so carrying full precision and rounding once produces a subtly different total that the digest detects.

**Red lines.** No hardcoded sample identifiers, no reading the verifier tree from the delivered program, no non-stdlib imports, deterministic output across runs, and nothing derived from a superseded file.

## Solution shape

1. Read run_profile.json and select the LIVE sheet of recalibration_grid.xlsx by matching its first-row tag to the profile calibration tag.
2. Parse the method rows and the recalibration rows from that sheet, read the five governance constants from the governance_envelope.pdf content stream, and read the tier objective weights from tier_weight_book.json.
3. Exclude qc-fail readings, then order the survivors by settle_slot, draw_slot, and descending reading_id.
4. Place each survivor in the last eligible batch whose half-open slot window covers it, where eligibility means min_lot is at most the effective lot.
5. For each reading scale raw and basis by the unit scale, apply the method exponent transform and gain with a stage rounding, apply the analyte recalibration with a stage rounding, and apply the recovery reweight against the governance floor with a stage rounding.
6. Admit against the per-batch cap with channel carry, clamp to the floor result, add the whole-unit matrix shift, hold at zero, and accumulate the committed per-analyte per-batch result. Seat any carry still standing at the end of the run on the first analyte and batch that channel admitted.
7. Settle each batch by the damped rebalance from the damping seed within the sixty-four round budget and reproject against the carryover ceiling with a largest-first clawback, breaking both ties by analyte name ascending.
8. Project the spine into every artifact, serialize JSON sorted-key compact with a trailing newline, and fold the core digest into the manifest and the data quality file.

## Ordered plan

1. Inventory /app/data and read the pipeline contract and the per-stage notes, which earns the trajectory grounding criteria.
2. Open the xlsx and select the LIVE sheet by the profile tag, which earns the LIVE-sheet criterion.
3. Open the pdf and recover the five constants, which every probe with altered constants then confirms.
4. Implement the ordered stages with staged rounding, the smaller effective lot and batch eligibility, which earns the ordering, rounding, lot, and recovery criteria.
5. Implement admission with the floor clamp and matrix shift, convergence, and carryover clawback, which earns the admission and clawback criteria.
6. Emit every artifact and the digest, run the program on the shipped run, run it twice and compare, and report the objective value and the digest, which earns the determinism and response criteria.

## Pitfalls

- Reading the DRAFT sheet or flat_coeff_archive.csv computes wrong gains and fails recalibration_live_sheet_applied.
- Skipping the pdf leaves the floor, cap, and ceiling undefined and fails recovery_floor_applied and carryover_reprojection_exact.
- Taking the larger lot admits b_recheck and fails the exact tier.
- Ignoring min_lot eligibility places readings in the wrong batch and fails the exact tier.
- Treating a batch's to_slot as covered seats boundary readings in the wrong batch and fails batch_totals_match_reference.
- Rounding once at the end fails staged_rounding_fixedpoint_exact and the exact tier.
- Treating qc-fail rows as ordinary, or reporting out-of-batch drops in their place, fails qc_fail_rows_excluded_before_ordering and excluded_readings_match_reference.
- Scaling the matrix shift by a thousand, or adding it before the clamp, fails the exact analyte spine.
- Discarding the channel carry left standing at the end of the run, or letting an uncovered reading clear it, fails the exact analyte spine and carry_probe_reproduced_exact.
- Dropping the round budget, or counting only a strictly larger residual as non-improving, fails round_control_probe_reproduced_exact.
- Writing csv or psv rows only for analytes or tiers that hold a total, or leaving XML attributes unescaped, fails sparse_probe_reproduced_exact.
- Taking any value from a superseded file fires negative_superseded_source_used, even where the superseded value happens to equal the live one.
- Writing the shipped reading ids or the calibration tag into the program as live literals fires negative_hardcoded_sample_answers.

## Provenance

```yaml
uuid: 00372225-134c-56e6-80ea-8bd47c66c816
instance_id: 00372225-134c-56e6-80ea-8bd47c66c816
task_name: terminal-bench/00372225-134c-56e6-80ea-8bd47c66c816
language: python
# Channel A (tests/test_output.py) measured in isolation, rewardkit 0.2.1,
# each figure the share of that channel's positive total of 100. The combined
# bundle reward is half this figure plus the judged channel's half.
measured_oracle_channel_a: 1.00 # reference solution, all 30 positives, no negative fired
measured_nop_channel_a: 0.00 # empty workspace
measured_stub_channel_a: 0.02 # declared paths present, empty or {} contents
measured_forgery_channel_a: 0.06 # exact shipped artifacts transcribed, delivered program does nothing
measured_one_rule_wrong_channel_a: 0.57 # recovery floor skipped, every other stage correct
measured_one_integer_wrong_channel_a: 0.29 # one committed figure off by one
measured_first_entry_wins_channel_a: 0.97 # overlapping slot seated in the first calendar entry
measured_draft_sheet_channel_a: 0.15 # DRAFT grid sheet read instead of the LIVE sheet
measured_larger_lot_channel_a: 0.26 # larger declared lot taken instead of the smaller
measured_round_once_channel_a: 0.57 # precision carried and rounded once at the reweight stage
measured_q32_channel_a: 0.62 # Q32 fixed point used instead of the specified Q16.16
objective_value: 15681 # shipped sample run
core_sha256: 9c43df1e5a0de218b63d5f0088a66c9511501b69ebb7c2e5405aeffeb44a94be # shipped sample run
```
