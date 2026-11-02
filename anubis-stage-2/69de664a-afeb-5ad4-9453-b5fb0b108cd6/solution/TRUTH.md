# TRUTH.md - 69de664a-afeb-5ad4-9453-b5fb0b108cd6

## Defect

The shipped extract is a four-instrument detector-array flux reconciliation
whose pre-computed pipeline (`legacy_pipeline_output.json`) is deliberately
wrong. The agent is not recovering a lost format; it is diagnosing why the
shipped flux figures are incorrect and recomputing every calibrated flux from
the written contract in `environment/data`. The spine value is
`calibrated_flux_ujy`, an integer micro-jansky per observation; getting the
spine wrong cascades into every rollup, the dead-pixel closure, the anomaly
ledger, the ordering index and the totals. The task is the correction of a
faulty computation.

Classified defects the agent must correct (each states the rule, where it is
written down, and what a naive reading does instead, and each is defeatable
only by reading the shipped materials):

1. (focal) The per-instrument scale factor `factor_micro` is stored x1e6 and
   lives ONLY in `gain_scale_workbook.xlsx`. The naive reading applies it as a
   raw multiplier (or omits it). The correct pipeline divides it by 1e6 before
   applying. Defeats `scale_factor_is_read_and_divided` and every full
   reconciliation test if wrong.
2. (focal) The gain label written on an observation is not always the channel
   that applies: labels were folded across epochs (`channel_lineage_fold.psv`).
   A0 in E2/E3 resolves to A2; B0 in E3 resolves to B3. The naive reading uses
   the written label. Defeats `gain_fold_resolved_before_lookup`.
3. (focal) The three correction documents are listed in a different order than
   they apply (`pipeline_order_note.txt`). The correct order is dark ->
   nonlinearity -> gain -> scale -> drift -> quantize; nonlinearity is applied
   to the dark-subtracted net BEFORE gain. Reading the files top-to-bottom and
   applying in that order is wrong. Defeats the full reconciliation tests.
4. (focal) The dead-pixel redistribution is a least fixed point
   (`relay_closure_rule.json`, `occlusion_relay_graph.xml`): a masked pixel
   distributes its fully-accumulated flux to targets that may themselves be
   masked. A single pass over base flux under-counts multi-hop chains. Defeats
   `deadpixel_closure_is_least_fixed_point`.
5. (drift) The thermal-drift correction is SUBTRACTED, not added
   (`thermal_drift_ppm.yml`). Adding it is the experienced instinct for a
   positive ppm correction and is wrong. Defeats the full reconciliation tests.
6. (drift) Quantization uses banker's rounding (ROUND_HALF_EVEN), not half-up
   (`rounding_primer.txt`). Default `round()` behaviour and ROUND_HALF_UP
   diverge on exact-half values. Defeats the reconciliation tests on tie cases.
7. (trap) The disputed-observation adjudication in `adjudication_dossier.pdf`
   (a real PDF) OVERRIDES the CSV quality flag; a csv `suspect` row is retained
   unless it is also disputed. `partial_dispute_notice.jsonl` is intentionally
   incomplete (omits three disputed ids, per `dispute_notice_readme.txt`), so a
   model that trusts the plain-text notice leaves three disputed observations in
   the rollups. Defeats `disputed_adjudication_overrides_flag` and
   `shipped_dropped_list_exact`.
8. (trap) Epoch resolution uses half-open intervals `[start, end)`
   (`boundary_cases.md`): an mjd equal to `mjd_end` belongs to the next epoch.
   An inclusive reading mis-bins boundary observations. Surfaces only on
   boundary mjds; defeats `epoch_intervals_are_half_open`.
9. (focal) A reading above `full_well_counts(instrument)` is CLIPPED to that
   ceiling before dark subtraction and marked saturated (`full_well_capacity.tsv`,
   the CLIP stage of the contract, E05 in `diagnostic_codes.txt`). Two readings
   are wrong: skipping the clip entirely, and clipping at or after dark
   subtraction, which leaves `net_counts` one dark current too high. A reading
   exactly at the full well is NOT clipped. Defeats
   `saturation_clips_at_full_well`.
10. (trap) Saturation changes eligibility, not liveness: a saturated observation
    keeps its flux in every rollup, ranking and total, but leaves every band
    median sample and is never flagged as an anomaly, and a band whose live rows
    are all saturated carries no median key at all (contract `Saturation`,
    `anomaly_threshold_spec.json`, E06). Treating saturation as a drop
    understates every total; ignoring it entirely poisons the median with
    ceiling values and flags the ceiling as a detection. Defeats
    `saturated_rows_leave_the_band_median`.
11. (focal) The reconciled total is apportioned across the four instruments by
    LARGEST REMAINDER (`exposure_weight_micro.tsv`, contract
    `Exposure attribution`, E07): floor each exact share toward negative
    infinity, then award the leftover one micro-jansky at a time to the largest
    fractional remainders, ties going to the lower instrument name. Rounding
    each share independently is the natural instinct and leaves the parts not
    summing to the pool; awarding the leftover to the largest share rather than
    the largest remainder is the second natural error. Defeats
    `attribution_apportions_the_pool_exactly` and
    `attribution_ties_break_by_instrument_ascending`.
12. (focal) The relay audit reports the FULLY ACCUMULATED amount each masked
    pixel hands on, not its base flux, and names the unmasked pixels the flux
    finally reaches by following masked hops transitively (contract
    `Relay audit`, `relay_closure_rule.json`, E08). A one-pass audit reports
    base flux and direct targets, and both are wrong wherever a chain runs
    longer than one hop, which is the same defect as 4 made observable per hop.
    Defeats `relay_audit_reports_accumulated_amounts` and
    `relay_audit_terminals_follow_masked_hops`.

The reference implementation is Python 3 (`solution/solve.py`), standard library
only, and reads only `/app/data`. Grading is split into two channels with no
overlap: Channel A (`tests/test_output.py`) grades artifact correctness
deterministically; Channel B (`tests/judge.toml`) grades the diagnosis
trajectory and design.

Out of bounds, with the layer that owns each rule named once so no single act is
priced twice: embedding shipped identifiers or figures in the delivered program
is caught by `negative_hardcoded_sample_answers`; reaching for the reward files
or the verifier log directory is caught by `negative_targets_reward_files`,
while searching the verifier sources, the corpus seeds or the reference solution
is left to the judged `r30_seeks_grader_internals` because it shows up in the
trajectory rather than in the delivered text; a non-stdlib dependency is caught
by `negative_third_party_dependency` and a standard-library network module by
`negative_network_access`; a summary that drops the rollup sections is caught by
`summary_schema_is_exact`.

## Load-bearing work

The graded deliverables are the reusable program `/app/out/derive_report.py`
plus 78 report artifacts, which `task.toml` declares as 79 absolute artifact
paths in total.

Twenty-three carry the reconciliation layer: `summary.json`,
`reconciled_flux.json`, `calibration_audit.json`, `data_quality.json`,
`instrument_G1.json` .. `instrument_G4.json`, `epoch_totals.json`,
`deadpixel_closure.json`, `band_rollup.csv`, `epoch_rollup.tsv`,
`instrument_rollup.psv`, `flagged_observations.xml`,
`objective_summary.yaml`, `reconciliation_report.md`, `run_status.txt`,
`provenance_manifest.json`, `anomaly_ledger.json`,
`ordered_flux_index.json`, `dropped_observations.json`,
`flux_attribution.json` and `relay_audit.json`.

Eight carry the settlement layer: `settlement_summary.json`,
`settled_rates.json`, `zero_exposure.json`, `cosmic_ray_rejects.json`,
`near_saturation.json`, `settled_attribution.json`, `band_settlement.csv` and
`settlement_order.json`.

The remaining forty-seven are the three per-dimension rollup families of
`report_schema.md` sections D1 to D3, each with its own serialisation and its
own row order: twenty `cell_<instrument>_<band>.json` files for every
instrument paired with every band, fifteen `grid_<epoch>_<band>.psv` files
pipe-separated with rows in the instrument order G1 to G4, and twelve
`span_<instrument>_<epoch>.tsv` files tab-separated with rows in the
photometric band order u, g, r, i, z. Every family is written in full, so a
pair with no live observation is written with its counts and flux at zero
rather than omitted, and the three families reconcile exactly against one
another and against the headline rollups.

Per-deliverable contract: every calibrated flux is an integer micro-jansky
computed through the full corrected pipeline, which begins with the full-well
clip; `summary.json` carries the total, per-band, per-epoch, per-instrument
flux, channel usage and per-band medians over the eligible sample;
`reconciled_flux.json` carries `effective_counts` and the `saturated` boolean
beside the stage figures; `data_quality.json` carries the saturated count and
ids; `deadpixel_closure.json` carries the fixed-point resolved per-pixel flux
and `relay_audit.json` the same closure hop by hop;
`flux_attribution.json` carries the largest-remainder apportionment whose four
parts sum to the pool exactly; `dropped_observations.json` carries exactly the
PDF-adjudicated disputed ids; `calibration_audit.json` echoes the applied tables
and the fold edges; JSON is serialized with sorted keys and a trailing newline
and is byte-identical across reruns and under shuffled input rows. A JSON object
keyed by band, epoch, instrument or channel omits a key with no contributing
observation rather than zero-filling it, which is the opposite of the delimited
rollups; the two exceptions are the weight-table-keyed objects in
`flux_attribution.json`, where all four instruments are always present.

The settlement layer, contract sections S1 to S8, is where the deliverable's
headline figures now live, and it deliberately refuses the conventions of the
layer beneath it. Four of its rules invert a habit the reconciliation layer
teaches, which is the whole of its difficulty:

- S1 normalises each flux to a rate over its integration time with a FLOOR
  division, `(calibrated_flux_ujy * 1000000) // exposure_ms`. Every other
  quantization in this corpus is banker's rounding, so an agent that reaches for
  `half_even` here is wrong on 88 of the 243 settled rows of the shipped extract.
  A frame whose `shutter_state` reads `aborted` carries `exposure_ms` of 0 and is
  held out of the settlement entirely: 4 such frames ship.
- S2 rejects a cosmic ray hit when a settled rate exceeds
  `median + 6 * MAD` of its own instrument-and-band group, with the median
  absolute deviation used UNSCALED (no 1.4826). Two exemptions are absolute: a
  group of fewer than four settled rows rejects nothing, and a near-saturated row
  is spared. The shipped extract rejects 3; without the near-saturation exemption
  it would reject 4, which is how that exemption is exercised.
- S3 takes the LOWER of the two middle values of an even sample, never their
  mean. This diverges from the band median of the layer above, which keeps
  banker's rounding of the two middles. 11 of the 20 shipped groups have an even
  sample, so the convention is load-bearing rather than decorative.
- S4 orders every settlement artifact by the photometric band order u, g, r, i, z.
  Alphabetical order of the band letters is never correct here.

S5 sums the survivors into `settled_pool_ujy`, S6 re-runs the largest-remainder
apportionment over that pool, S7 takes
`sum(position * rate) mod 1000003` over the rank order whose band tie-break is
the photometric order, and S8 marks a row near saturated by the integer test
`raw_counts * 100 >= full_well_counts * 98` while it stays at or below the
ceiling. The shipped extract settles to `settled_pool_ujy` 379288575 and
`settlement_digest` 893107 over 240 surviving rows, with 2 near-saturated rows.

Out of bounds by design: the delivered program must generalize to unseen and
perturbed extracts; it must not hardcode the shipped numbers.

## Verification

`tests/test.sh` hardens the verifier and hands over to rewardkit, which runs
every criterion in `tests/test_output.py` and `tests/judge.toml`, sums the signed
weights of the criteria that hold, and writes `reward.json` and
`reward-details.json` to `/logs/verifier`. `tests/reward.toml` turns the two
channel sums into the single reward, each channel counting for half: its weights
are `0.5 / 197` for `test_output` and `0.5 / 113` for `judge`. No clamp is applied
anywhere; test.sh writes no reward bytes of its own.

Channel A positive weight total is 197 over 59 positive criteria (seven at
weight 1, thirty five at weight 3 and seventeen at weight 5), against four
negative criteria totalling -16. Each hidden decision owns one criterion on its
own seeded corpus and is compared only on the fields that decision moves, so one
wrong decision costs that decision rather than the whole report. Weights follow
the usual scale: 5 is a core outcome, 3 an important sub-goal or edge case, 1 a
minor detail, an existence check or a formatting rule. The five generalisation
criteria carry weight 5 each, because settling an extract the program has never
seen is the deliverable's primary behaviour; the artifact-existence and
schema-shape criteria carry 1, because they are satisfied without reading a
single figure. The twelve criteria driven off explicit fixtures, which reach the
rules no seeded corpus produces, carry 38 of the 197 positive weight.

Contract S7 breaks a settled-rate tie by the S4 photometric band order, and on
the shipped extract that clause decides nothing: all 240 surviving observations
carry distinct settled rates, so the band term in the S7 sort is never reached
and a solver ranking ties any other way still reproduces the reference.
`BAND_TIE_OBS` supplies the tie the shipped extract lacks. Five observations on
G1 carry the per-band dark current added back to one common net of 14955, so S1
settles all five at 676316 ujy per ks, and each sits alone in its own
instrument-and-band group, so S2's small-cohort exemption retains all five. The
obs_ids run counter to the photometric order, so the correct sequence is bt05,
bt04, bt03, bt02, bt01 while an obs_id fallback emits the exact reverse. The
settlement digest cannot detect the difference, because a positional sum over
equal rates is unchanged when two tied rows swap places; the order artifact is
the only surface on which this rule is observable, which is why
`settlement_order_breaks_rate_ties_by_band` grades
`settlement_order.json` and carries weight 5. Measured: ordering the settlement
bands alphabetically scores 183 of 197 and loses four checks,
`shipped_band_settlement_rendering_exact`,
`settlement_order_breaks_rate_ties_by_band`,
`band_settlement_rows_follow_photometric_order` and
`span_rows_follow_photometric_order`, because the photometric order governs the
band tie-break of the S7 rank order, the two band-keyed settlement renderings
and the row order of the section D3 spans at once.

Three further boundary rules are inert on the shipped extract for the same
reason, and each owns a fixture that lands on its boundary exactly.
`S8_BOUNDARY_OBS` carries an observation at 60760 raw counts against the 62000
ceiling of G1, so 60760 * 100 == 62000 * 98 and the "reach" half of S8 decides
whether it is recorded as near-saturated. `S2_THRESHOLD_OBS` puts five
observations in the (G1, g) group at settled rates 620177, 620177, 620266,
620355 and 620800; the lower-middle median is 620266 and the lower-middle median
of the absolute deviations is 89, so with sigma 6 the threshold is exactly
620800 and the largest member sits on it, which is what makes S2's STRICTLY
ABOVE wording decide the reject list. `ANOMALY_BOUNDARY_OBS` puts five
observations in band g whose median flux is 32357 and whose largest is exactly
97071, three times that median, so the anomaly rule's STRICTLY ABOVE wording
decides whether it is flagged. Measured: reading any of the three as the
opposite comparison scores 194 of 197 and loses exactly the check that names
it, `near_saturation_includes_the_exact_boundary`,
`s2_retains_the_observation_on_the_threshold` and
`anomaly_ledger_excludes_the_exact_multiple` respectively.

Positive criteria: `artifact_set_exists_and_parses` (1), `summary_schema_is_exact` (1), `delivered_json_is_sorted_with_trailing_newline` (1), `shipped_summary_headline_exact` (5), `shipped_rollups_exact` (5), `shipped_dropped_list_exact` (3), `shipped_renderings_exact` (3), `program_reconciles_unseen_extract` (5), `program_reconciles_second_unseen_extract` (5), `program_reconciles_third_unseen_extract` (5), `program_reconciles_fourth_unseen_extract` (5), `program_reconciles_fifth_unseen_extract` (5), `scale_factor_is_read_and_divided` (3), `drift_correction_is_subtracted` (3), `epoch_intervals_are_half_open` (3), `gain_fold_resolved_before_lookup` (3), `deadpixel_closure_is_least_fixed_point` (5), `disputed_adjudication_overrides_flag` (3), `anomaly_ledger_follows_median_rule` (5), `ordering_breaks_ties_by_obs_id` (3), `authoritative_sources_win_over_secondary` (3), `naive_pipeline_is_rejected` (3), `row_order_independent_and_correct` (3), `hidden_calibration_slice_reproduced` (3), `net_below_dark_current_is_retained` (3), `renderings_zero_fill_absent_keys` (1), `saturation_clips_at_full_well` (3), `saturated_rows_leave_the_band_median` (3), `attribution_apportions_the_pool_exactly` (5), `attribution_ties_break_by_instrument_ascending` (3), `relay_audit_reports_accumulated_amounts` (3), `relay_audit_terminals_follow_masked_hops` (3), `shipped_settlement_headline_exact` (5), `shipped_zero_exposure_list_exact` (3), `shipped_near_saturation_list_exact` (3), `shipped_cosmic_ray_rejects_exact` (3), `shipped_band_settlement_rendering_exact` (3), `settlement_rate_uses_floor_division` (5), `aborted_shutter_leaves_the_settlement` (3), `cosmic_ray_threshold_uses_median_absolute_deviation` (5), `small_cohort_is_exempt_from_rejection` (3), `near_saturated_row_survives_rejection` (3), `settlement_median_takes_the_lower_middle` (5), `settlement_digest_follows_photometric_order` (5), `settlement_order_breaks_rate_ties_by_band` (5), `near_saturation_includes_the_exact_boundary` (3), `s2_retains_the_observation_on_the_threshold` (3), `anomaly_ledger_excludes_the_exact_multiple` (3), `band_settlement_rows_follow_photometric_order` (3), `settled_attribution_apportions_the_pool_exactly` (5), `settlement_tracks_a_moved_exposure_ledger` (3), `rollup_families_are_written_in_full` (1), `cell_files_carry_the_schema_keys` (1), `rollup_cuts_reconcile_to_the_summary_totals` (3), `grid_rows_follow_instrument_order` (3), `span_rows_follow_photometric_order` (3), `rollup_cuts_reconcile_across_families` (3), `empty_cells_are_written_with_zeros` (1), `rollup_cuts_exclude_dropped_observations` (3).

Negative criteria: `negative_hardcoded_sample_answers` (-5), `negative_targets_reward_files` (-5), `negative_third_party_dependency` (-3), `negative_network_access` (-3).

Five rules the seeded corpora cannot reach own explicit fixtures. `NEGATIVE_NET_OBS`
drives an observation whose raw counts fall below its dark current, so the E01
rule in `diagnostic_codes.txt` that a negative net is retained rather than
clamped is graded by `net_below_dark_current_is_retained`; the seeded corpora draw
raw counts from 200 up against a largest dark current of 72, so no seeded
extract reaches it. `RENDERING_OBS` leaves three bands, one epoch and two
instruments without a live observation and carries one anomaly, so the
zero-fill rule in `report_schema.md` and the rendering of an `observation`
element are graded by `renderings_zero_fill_absent_keys`.

Three further fixtures exist for the same reason. The generator draws raw
counts up to 60000 and the lowest full well is 60500, so no seeded extract ever
saturates: `SATURATION_OBS` straddles each ceiling deliberately, with rows above
it, exactly at it and just below it, and is graded by
`saturation_clips_at_full_well`. `MEDIAN_EXCLUSION_OBS` carries a band with a
clipped outlier beside three eligible rows, a band whose every live row is
clipped, and a band with a genuine unsaturated outlier, so
`saturated_rows_leave_the_band_median` grades sample membership on medians that
are all middle elements and never exact halves, leaving the half-even rounding
of a median to `HALF_MEDIAN_OBS` alone. `DEEP_RELAY_OBS` with
`DEEP_RELAY_MASKED` builds two chains of different depth whose terminal sets
differ, so `relay_audit_terminals_follow_masked_hops` separates a transitive
audit from one that stops at the direct targets, while
`relay_audit_reports_accumulated_amounts` grades the relayed amounts on a
seeded high-mask corpus of its own.

The attribution pair is split the same way. `attribution_apportions_the_pool_exactly`
perturbs the exposure weights to values no shipped table carries, so the four
amounts can only be right if the weight table was read, and grades the pool, the
echoed weights and the attributed amounts. `attribution_ties_break_by_instrument_ascending`
runs a corpus whose four weights are equal, which ties every remainder and makes
the award order the entire observable, and grades `remainder_recipients` alone;
its seed and size are pinned to a closure total that leaves three micro-jansky
over, and the check refuses to pay when the leftover is zero, so the fixture can
never decide nothing.

The seven non-JSON artifacts are graded on content, not merely existence:
`shipped_renderings_exact` compares the delivered delimited rollups, the
flagged-observation xml, the objective yaml, the run status and the markdown
report against the shipped figures, and `renderings_zero_fill_absent_keys`
repeats that comparison on the fixture above. The `status` word in
`run_status.txt` is required to be present and is never read as evidence that
the run succeeded.

Sensitivity matrix: every mutation criterion flips exactly one hidden decision
(scale factor, drift, epoch boundary, post-fold gain, mask rate, exposure
weight, tied exposure weight) and asserts the graded output changes; the full
reconciliation tests exercise all decisions jointly on three independent seeds. `naive_pipeline_is_rejected` proves the
naive pipeline diverges; `hidden_calibration_slice_reproduced` grades an
unpublished calibration slice, so the visible worked slice is a self-check
rather than a graded transcription.

Channel B (`tests/judge.toml`) has 32 criteria (29 positive, 3 negative),
positive total 113 against a negative total of -11. It grades only what the
trajectory, the final message and the delivered program show and the
deterministic channel cannot see, and it is deliberately split into three
groups so that no part of it saturates on a competent run.

The first group, 18 of the 113 points, grades the sources the run reached for:
the two office documents being read for the values only they publish
(`r2_opens_scale_workbook` and `r3_parses_pdf_dossier`, 3 each), the choice of
authoritative source among the duplicated files
(`r4_reads_authoritative_sources`, 3), the write scope the instruction states
(`r1_writes_confined_to_out_dir`, 3), reading the contract before the first
version of the program appears (`r5_opens_contract_before_writing`, 3) and
running the program before reporting on it
(`r6_runs_program_before_reporting`, 3).

The second group grades checks the agent actually ran, which no assertion over
`OUT_DIR` can observe: a second run of the delivered program on the same
extract compared byte for byte (`r17_compares_two_runs_byte_for_byte`, 1), a
run over a row-reordered extract compared against the first
(`r18_checks_row_order_independence`, 1), a run over an extract whose exposure
ledger holds different integration times with every settled rate confirmed
against them (`r19_checks_a_moved_exposure_ledger`, 5), reproducing the
published calibration slice before reporting the work finished
(`r20_reproduces_the_calibration_slice`, 3), recording the divergent S1
rounding decision before that stage is implemented
(`r21_records_the_divergent_rounding_decision`, 5), a run over an extract whose
reference tables hold different values
(`r25_validates_on_differing_tables`, 5) and the traceability of the delivered
program itself (`r26_program_is_traceable_to_the_contract`, 3).

The third group grades what the closing report discloses, which is a message
and not an artifact: the settlement rounding mode with its contract section
(`r7_states_settlement_rounding_mode`, 5), one observation traced from its
calibrated flux to its settled rate (`r8_traces_one_observation_to_its_rate`,
5), the rejection estimator with worked threshold arithmetic for one named
group (`r9_gives_threshold_arithmetic_for_one_group`, 5), the group size below
which rejection spares everything (`r10_gives_spared_group_size`, 5), why a
near-saturated observation survives (`r11_explains_near_saturation_exemption`,
5), the two median conventions contrasted
(`r12_contrasts_the_two_median_conventions`, 3), the settlement band order with
its section (`r13_gives_settlement_band_order`, 5), the digest arithmetic
(`r14_shows_digest_arithmetic`, 5), the settled pool beside its four attributed
parts (`r15_shows_settled_pool_against_its_parts`, 5), the aborted-frame count
(`r16_reports_aborted_frame_count`, 1), the correction-stage order with its
section (`r22_states_stage_order_with_its_section`, 5), the least-fixed-point
closure argument (`r23_explains_least_fixed_point_closure`, 3), one observation
traced from raw counts to the reconciled total
(`r24_traces_raw_counts_to_the_total`, 5), the deviation entering the threshold
unscaled (`r27_states_deviation_enters_unscaled`, 5), the leading positional
terms of the digest sum (`r28_gives_leading_digest_terms`, 5) and the ascending
pixel ordering as the relay termination argument
(`r29_gives_the_termination_argument`, 5).

The split is what keeps the two channels disjoint. Channel A asserts that the
artifacts HAVE these properties (`row_order_independent_and_correct`,
`deadpixel_closure_is_least_fixed_point`, the five `program_reconciles_*`
criteria and the mutation criteria); Channel B asserts only that the agent
CHECKED and REPORTED them, which is a command history and a message, neither of
which a verifier over `OUT_DIR` can read. Three negative criteria price grader
probing (`r30_seeks_grader_internals`, -5), unsupported headline figures
(`r31_unsupported_final_figures`, -3) and claimed verification that never ran
(`r32_claims_unrun_verification`, -3); the verification criteria
`r17` to `r21` and `r25` against `r32_claims_unrun_verification` are the
sanctioned verified-versus-reported-honestly split rather than one act paid
twice, since an agent may run the checks silently, run them and say so, skip
them and stay quiet, or skip them and claim them, and those four states draw
different scores.
Nothing in this channel restates a figure the deterministic channel already
grades.

### What the oracle itself verifies before reporting

`solution/solve.sh` does not stop at producing the artifacts. Before the program
exists it reads the written contract, the pipeline order note, the role index
and the closure rule, and records that contract section S1 fixes the settlement
normalisation as a floor division diverging from the banker's rounding of the
layer above. It then delivers `solve.py` to `/app/out/derive_report.py`, runs it
on the shipped extract, and runs five further checks, each of which must pass
before the closing report is written. The script exits non-zero if any of them
fails, so a regression in `solve.py` surfaces as a failed oracle run rather than
as a quiet score drop. The first three are driven off a sha256 manifest over the
78 declared report artifacts, which excludes `derive_report.py` itself so the
program file sitting in `OUT_DIR` never enters a comparison. Every perturbed
extract is a copy under a scratch directory, so `/app/out` keeps exactly what
run 1 wrote from the pristine extract.

1. **Determinism re-run.** The program is run a second time on the same
   `DATA_DIR` into a scratch `OUT_DIR`, and the two manifests are compared with
   `cmp`. This is the direct check on the instruction sentence "keep the output
   byte-identical across reruns". All 78 artifacts match.
2. **Row-order re-run.** `obs_capture_index.csv`, the authoritative observation
   stream, is copied with its 260 data rows reversed, the program is run on that
   extract, and the manifest is compared against run 1. This is the direct check
   on "keep the output identical when the input observation rows are reordered".
   All 78 artifacts match, so the reversal changes nothing.
3. **Differing-tables extract.** Every reference table the pipeline reads is
   shifted at once: dark current +7 per row in `pedestal_authoritative.csv`,
   quantum yield +60000 micro-e-per-count per channel in
   `quantum_yield_micro.json`, drift +250 ppm per row in
   `thermal_drift_ppm.yml`, and the per-instrument `factor_micro` -15000 inside
   `gain_scale_workbook.xlsx`, which is rewritten through `zipfile` because the
   workbook is the only publisher of that factor. The program is run on the
   altered extract. Two things are then required: the manifest must DIFFER from
   run 1, which proves the figures are table-driven rather than memorised, and
   an independent re-derivation must AGREE with the program on every stage
   field. This is the oracle's own exercise of the instruction promise that the
   program is graded "on extracts you have not seen ... including extracts whose
   reference tables hold different values from the shipped ones".
4. **Moved-exposure-ledger re-run.** `exposure_ledger.csv` is copied with every
   completed frame's `exposure_ms` scaled, while an aborted shutter keeps its
   0 ms so the set of frames S1 holds out of the settlement does not move. The
   program is run on that extract and every one of the 243 settled rates is
   re-derived from the altered ledger as
   `floor(calibrated_flux_ujy * 1000000 / exposure_ms)` and compared, which is
   the direct check that the integration times are read from the ledger rather
   than assumed. This check is separate from check 3 on purpose: that one moves
   the reconciliation tables, this one moves only a quantity no table above the
   settlement layer carries.
5. **Published calibration slice.** The three observations
   `worked_reference_slice.json` publishes are appended to a copy of the extract
   with a pixel outside the relay graph and a complete shutter, the program is
   run on it, and all seven published `expected_*` stage figures are compared
   against the program's own `reconciled_flux.json` entries. The slice resolves
   to `cal01` 25089, `cal02` 23487 and `cal03` 68979 micro-jansky, each through
   a folded channel (A2, B3 and C1) and a different epoch, so reproducing all
   three exercises the fold, the epoch resolution and the full stage chain at
   once.

The independent re-derivation is a separate implementation embedded in
`solve.sh`: it re-reads the observation stream, epoch windows, dark table,
Horner coefficients, quantum yields, fold table, workbook factor and drift table
straight from an extract, re-reads the full-well table, walks one observation
through all seven stages with its own `Decimal` arithmetic, and compares `epoch`,
`effective_counts`, `saturated`, `net_counts`, `linearized`, `resolved_channel`,
`drift_ppm`, `drift_correction` and `calibrated_flux_ujy` against the matching
entry in the program's `reconciled_flux.json`. It never
imports `derive_report.py`, so agreement is evidence rather than tautology. It
runs twice: against the altered-table extract, where it is the validation, and
against the shipped extract, where its printed stage-by-stage trace is the
worked chain the closing report discloses.

The closing report then states the stage order with the contract section that
fixes it, prints that worked chain, explains the least-fixed-point closure, and
reads every headline figure back out of the written artifacts rather than
recomputing it, so the message and the artifacts cannot disagree. On the shipped
extract the chain reads: `o00001`, instrument G2, band g, written label A0,
mjd 59355 in `[59240, 59360)` so epoch E3; raw 16711 against the G2 full well
61500 is below the ceiling, so the clip is a no-op and `effective_counts` is
16711 with `saturated` false; 16711 minus dark 49 gives net 16662; Horner `[5, 998000, 12000]` over 1e6 gives 18017; A0 in E3 folds to A2 so
18017 x 1950000 / 1e6 gives 35133.15; x factor 985000 / 1e6 gives 34606.15275;
1100 ppm gives a correction of 38, subtracted to 34568.15275; half-even
quantization gives 34568. The run totals 260 observations, 247 live, 13 dropped
and `total_reconciled_flux_ujy` 22548014. No shipped observation reaches a full
well (the largest raw count in the extract is 59777 against a lowest ceiling of
60500), so `saturated_count` is 0 and every figure above is unchanged by the
clip stage. That total apportions by exposure weight to G1
5010670, G2 6263337, G3 4384336 and G4 6889671, which sum to 22548014 exactly,
with the leftover two micro-jansky going to G1 and G4 on the largest
remainders.

## Root cause

**Unit and scale semantics.** `factor_micro` and the quantum yield are integers
stored x1e6; the drift is parts-per-million. Every one must be divided by 1e6
before use. Treating a stored-scaled integer as a raw factor is the dominant
error and inflates flux by roughly a million.

**Temporal identity.** Gain labels are not stable identifiers; they were folded
across epochs. The applying channel is a function of (written label, mjd), not
of the label alone.

**Application order versus presentation order.** The correction documents are
shipped out of application order on purpose. Recovering the pipeline order is
unstated work that no single file contains and it sits upstream of every figure.

**Least-fixed-point closure.** Dead-pixel redistribution is defined by
admission depending on admission; a single pass is defensible-looking and wrong
wherever a chain runs longer than one hop. The relay audit makes that same
closure observable per hop, so the defect can no longer hide inside a total that
happens to look plausible.

**Measurement ceiling versus measurement.** A reading above the full well is the
detector saturating, not a brighter source. It is clipped before any correction
touches it, it keeps contributing its clipped flux, and it is barred from the
band median and from the anomaly ledger, because a statistic taken over ceilings
describes the detector rather than the sky.

**Integer apportionment.** Dividing a total into parts that must remain integers
and must still sum to the total is not rounding; it is apportionment. Shares
compared as exact integer remainders over the common denominator and a leftover
awarded by largest remainder is the only rule here that guarantees both, and
independently rounded shares fail the sum.

**Source precedence.** Two sources disagree; the PDF wins, and the plain-text
mirror is deliberately incomplete, so skimming text alone is insufficient.

**Red lines.** No graded value depends on a hidden seed, a private constant or
the network. Every rule the grading applies is written into `environment/data`:
the computation in `reconciliation_contract.md` and the output shape in
`report_schema.md`. The delivered program must read only `/app/data`, write only
its output directory, and use only the standard library.

## Solution shape

1. Load the observation stream from `obs_capture_index.csv` (authoritative
   raw_counts) and the epoch windows from `epoch_window_bounds.json`.
2. Load the correction tables: dark current from `pedestal_authoritative.csv`,
   Horner coefficients from `response_curve_horner.yaml`, quantum yield from
   `quantum_yield_micro.json`, the gain fold from `channel_lineage_fold.psv`,
   the drift table from `thermal_drift_ppm.yml`.
3. Parse `gain_scale_workbook.xlsx` with the stdlib zip+xml path and read the
   authoritative `factor_micro` per instrument.
4. Parse `adjudication_dossier.pdf` with the stdlib text-extraction path and
   read the authoritative disputed set.
5. For each observation resolve epoch (half-open), clip raw counts at the
   per-instrument full well from `full_well_capacity.tsv` and mark saturation,
   subtract dark current from the clipped counts, apply
   Horner (x1e6 -> /1e6, half-even), resolve the gain channel and apply the
   yield (/1e6), apply the scale factor (/1e6), subtract the drift correction
   (half-even), and quantize (half-even) to integer micro-jansky.
6. Drop PDF-disputed observations; redistribute dead-pixel flux as a least
   fixed point and record the per-hop audit; aggregate rollups, anomalies
   (per-band median rule over the eligible, non-saturated sample), ordering and
   totals; apportion the closure total by exposure weight with largest
   remainder; serialize every artifact deterministically.

## Ordered plan

1. Read `reconciliation_contract.md`, `pipeline_order_note.txt`,
   `file_role_index.md` and the glossary, before any program file exists, to fix
   the application order and the authoritative source of each table (earns R5
   and R4).
2. Record that contract section S1 takes a floor division rather than the
   banker's rounding of the layer above, before that stage is implemented
   (earns R21).
3. Open the xlsx with the stdlib zip and xml path and read `factor_micro` per
   instrument from the authoritative sheet (earns R2).
4. Parse the pdf dossier and read the authoritative disputed set (earns R3).
5. Implement the pipeline with the 1e6 divides, the epoch fold, the subtracted
   drift and half-even rounding, as named helpers covering one stage apiece, so
   a reader can follow raw counts through every stage to the written artifacts
   (earns R26).
6. Implement the fixed-point closure, the source precedence and the half-open
   epoch resolution; retain a negative net rather than clamping it; keep
   saturated rows out of the median sample and the anomaly ledger; apportion the
   total by largest remainder with the tie going to the lower instrument name.
7. Emit every artifact into OUT_DIR and nowhere else (earns R1), as integer
   micro-jansky with sorted-key JSON and the delimited, xml, yaml and text
   renderings the schema fixes, then run the program on the shipped extract
   before reporting on it (earns R6).
8. Re-run the delivered program on the same extract and compare the 78
   artifacts byte for byte (earns R17), re-run it on an extract with the
   observation rows reversed and compare against the first run (earns R18),
   re-run it on an extract whose dark, yield, drift and workbook tables all hold
   different values, validating the figures against an independent re-derivation
   (earns R25), re-run it on an extract whose exposure ledger holds different
   integration times and confirm every settled rate follows them (earns R19),
   and reproduce the published calibration slice, all before calling the work
   finished (earns R20).
9. Close with a report that gives the correction-stage order and the contract
   section that fixes it (earns R22), walks one named observation from raw
   counts to its contribution to `total_reconciled_flux_ujy` (earns R24) and
   another from its calibrated flux to its settled rate (earns R8), explains why
   the dead-pixel closure is a least fixed point rather than a single pass
   (earns R23) and why the relay recursion terminates on ascending pixel
   identifiers (earns R29), and discloses the settlement decisions: the S1
   rounding mode with its section (earns R7), the rejection estimator with
   worked threshold arithmetic (earns R9), the spared group size (earns R10),
   the near-saturation exemption (earns R11), the two median conventions (earns
   R12), the band order with its section (earns R13), the digest arithmetic and
   its leading terms (earns R14 and R28), the settled pool beside its four
   parts (earns R15), the aborted-frame count (earns R16) and the unscaled
   deviation (earns R27).
10. Report the totals with their sources credited, reading each figure back out
   of the artifacts so every number is traceable to a command that ran, and
   leave the verifier alone (avoids R30, R31 and R32).

## Pitfalls

- Applying `factor_micro` without the 1e6 divide -> fails
  `scale_factor_is_read_and_divided` and every reconciliation test.
- Using the written gain label -> fails `gain_fold_resolved_before_lookup`.
- Applying corrections in file-listing order -> fails the reconciliation tests.
- Adding the drift correction or using half-up rounding -> fails the
  reconciliation tests.
- Single-pass dead-pixel redistribution -> fails
  `deadpixel_closure_is_least_fixed_point`.
- Taking the disputed set from the jsonl notice or csv flags -> fails
  `disputed_adjudication_overrides_flag` and `shipped_dropped_list_exact`.
- Copying `legacy_pipeline_output.json` -> fails `naive_pipeline_is_rejected`
  and every reconciliation test.
- Rounding the S1 normalisation with banker's rounding, the habit every stage
  above teaches, rather than flooring it -> fails
  `settlement_rate_uses_floor_division`,
  `settlement_tracks_a_moved_exposure_ledger` and
  `shipped_settlement_headline_exact`. 88 of the 243 shipped settled rows differ
  between the two, so this one habit is the single most expensive mistake here.
- Settling an aborted frame at a rate of zero rather than holding it out of the
  settlement -> fails `aborted_shutter_leaves_the_settlement`, because a zero
  rate joins the pool and the digest while a held-out frame joins neither.
- Scaling the median absolute deviation by 1.4826, the usual consistency
  constant, when contract S2 publishes it unscaled -> fails
  `cosmic_ray_threshold_uses_median_absolute_deviation`.
- Using a standard deviation rather than the median absolute deviation -> fails
  the same check, and shifts `settled_pool_ujy` because the surviving set moves.
- Rejecting from a group of fewer than four settled rows -> fails
  `small_cohort_is_exempt_from_rejection`.
- Rejecting a near-saturated row -> fails `near_saturated_row_survives_rejection`
  and moves the pool, the digest and the attribution with it.
- Averaging the two middle values of an even settlement sample, which is what
  the band median above does -> fails
  `settlement_median_takes_the_lower_middle` and every figure downstream of a
  group threshold.
- Ordering a settlement artifact alphabetically by band -> fails
  `band_settlement_rows_follow_photometric_order` and
  `settlement_digest_follows_photometric_order`, since the photometric order is
  also the digest's band tie-break.
- Re-using the reconciled total for the settled attribution rather than
  re-running the apportionment over `settled_pool_ujy` -> fails
  `settled_attribution_apportions_the_pool_exactly`.
- Taking the integration times from anywhere other than `exposure_ledger.csv`,
  which `file_role_index.md` marks the only authoritative source for them ->
  fails `settlement_tracks_a_moved_exposure_ledger`.
- Clamping a negative net after dark subtraction -> fails
  `net_below_dark_current_is_retained`.
- Skipping the full-well clip, or clipping after dark subtraction instead of
  before it, or clipping a reading that sits exactly at the full well -> fails
  `saturation_clips_at_full_well`.
- Leaving saturated rows in the band median sample, flagging a clipped reading as
  an anomaly, or writing a median for a band whose live rows are all saturated ->
  fails `saturated_rows_leave_the_band_median`.
- Rounding each exposure share independently, so the four parts do not sum to the
  pool, or awarding the leftover to the largest share -> fails
  `attribution_apportions_the_pool_exactly`.
- Breaking a remainder tie by anything other than ascending instrument name ->
  fails `attribution_ties_break_by_instrument_ascending`.
- Reporting base flux rather than the fully accumulated amount in the relay
  audit, or splitting without the leftover to the first target -> fails
  `relay_audit_reports_accumulated_amounts`.
- Listing direct targets as terminal pixels instead of following masked hops
  transitively -> fails `relay_audit_terminals_follow_masked_hops`.
- Omitting a band, epoch or instrument that has no live observation from the
  delimited rollups rather than writing 0 in both numeric columns -> fails
  `renderings_zero_fill_absent_keys`.
- Zero-filling an absent band, epoch, instrument or channel key in the JSON
  objects, where the schema requires the key to be omitted instead -> fails
  `program_reconciles_unseen_extract` and the other full-artifact comparisons.
- Writing the seven non-JSON artifacts as empty or placeholder files -> fails
  `shipped_renderings_exact`.
- Hardcoding shipped numbers -> fires
  `negative_hardcoded_sample_answers`.

## Provenance

```yaml
uuid: 69de664a-afeb-5ad4-9453-b5fb0b108cd6
instance_id: 69de664a-afeb-5ad4-9453-b5fb0b108cd6
task_name: terminal-bench/69de664a-afeb-5ad4-9453-b5fb0b108cd6
solve_py_sha256: 58c3610398e55861407938da4ea5387fd99d5dbac520c4515348aeef4ebbadc9
language: python3
test_positive_weight_total: 197
judge_positive_weight_total: 113
```
