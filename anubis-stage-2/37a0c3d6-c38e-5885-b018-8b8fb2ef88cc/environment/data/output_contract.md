# Output contract

The program writes every file below into its output directory. Columns appear in the listed order;
JSON keys are listed as paths. Rules H1 to H22 are in `be_analysis_handbook.md`; number formats follow H21 and H22.

| file | position | column or key | note |
|---|---|---|---|
| calibration_fits.json | 1 | study_id | object: study_id, nominal_sheet, runs (one per analysed run, sorted by run_id) |
| calibration_fits.json | 2 | nominal_sheet |  |
| calibration_fits.json | 3 | runs[].run_id |  |
| calibration_fits.json | 4 | runs[].analyte |  |
| calibration_fits.json | 5 | runs[].model |  |
| calibration_fits.json | 6 | runs[].weighting |  |
| calibration_fits.json | 7 | runs[].cal_lot |  |
| calibration_fits.json | 8 | runs[].coefficients.a / .b / .c (c null for linear; object null without curve) |  |
| calibration_fits.json | 9 | runs[].n_standards |  |
| calibration_fits.json | 10 | runs[].n_assignable |  |
| calibration_fits.json | 11 | runs[].n_retained |  |
| calibration_fits.json | 12 | runs[].removed (injection ids in removal order) |  |
| calibration_fits.json | 13 | runs[].iterations (fits performed) |  |
| calibration_fits.json | 14 | runs[].lloq |  |
| calibration_fits.json | 15 | runs[].uloq |  |
| standard_backcalc.tsv | 1 | run_id | one row per effective standard injection of an analysed run, sorted by run_id then seq |
| standard_backcalc.tsv | 2 | injection_id |  |
| standard_backcalc.tsv | 3 | level |  |
| standard_backcalc.tsv | 4 | nominal |  |
| standard_backcalc.tsv | 5 | response |  |
| standard_backcalc.tsv | 6 | back_calculated |  |
| standard_backcalc.tsv | 7 | deviation_pct |  |
| standard_backcalc.tsv | 8 | status |  |
| qc_results.csv | 1 | run_id | one row per effective QC and DQC injection of an analysed run, sorted by run_id then seq |
| qc_results.csv | 2 | injection_id |  |
| qc_results.csv | 3 | qc_level |  |
| qc_results.csv | 4 | nominal |  |
| qc_results.csv | 5 | dilution_factor |  |
| qc_results.csv | 6 | back_calculated |  |
| qc_results.csv | 7 | deviation_pct |  |
| qc_results.csv | 8 | pass |  |
| run_acceptance.csv | 1 | run_id | one row per analysed run, sorted by run_id |
| run_acceptance.csv | 2 | analyte |  |
| run_acceptance.csv | 3 | run_type |  |
| run_acceptance.csv | 4 | analysis_date |  |
| run_acceptance.csv | 5 | n_std_total |  |
| run_acceptance.csv | 6 | n_std_retained |  |
| run_acceptance.csv | 7 | n_levels_retained |  |
| run_acceptance.csv | 8 | qc_total |  |
| run_acceptance.csv | 9 | qc_pass |  |
| run_acceptance.csv | 10 | status |  |
| run_acceptance.csv | 11 | reason |  |
| run_acceptance.csv | 12 | dqc_status |  |
| run_acceptance.csv | 13 | lab_status |  |
| run_acceptance.csv | 14 | agrees |  |
| tube_results.psv | 1 | run_id | one row per effective injection of an in-scope study tube, sorted by tube, analyte, run order, seq |
| tube_results.psv | 2 | injection_id |  |
| tube_results.psv | 3 | tube |  |
| tube_results.psv | 4 | analyte |  |
| tube_results.psv | 5 | reason |  |
| tube_results.psv | 6 | dilution_factor |  |
| tube_results.psv | 7 | response |  |
| tube_results.psv | 8 | back_calculated |  |
| tube_results.psv | 9 | concentration |  |
| tube_results.psv | 10 | flag |  |
| tube_results.psv | 11 | used |  |
| reported_concentrations.csv | 1 | subject_id | one row per scheduled tube of an in-scope subject and analysed analyte, sorted by subject_id, period, analyte (profile order), nominal_h |
| reported_concentrations.csv | 2 | period |  |
| reported_concentrations.csv | 3 | formulation |  |
| reported_concentrations.csv | 4 | analyte |  |
| reported_concentrations.csv | 5 | nominal_h |  |
| reported_concentrations.csv | 6 | tube |  |
| reported_concentrations.csv | 7 | actual_h |  |
| reported_concentrations.csv | 8 | concentration |  |
| reported_concentrations.csv | 9 | status |  |
| reported_concentrations.csv | 10 | rule |  |
| reported_concentrations.csv | 11 | source_run |  |
| sampling_times.xml | 1 | tube@id | root <sampling_times study=...>, one <tube/> per scheduled tube of an in-scope subject, in subject, period, nominal, tube order; empty attributes for missing instants |
| sampling_times.xml | 2 | tube@subject |  |
| sampling_times.xml | 3 | tube@period |  |
| sampling_times.xml | 4 | tube@nominal_h |  |
| sampling_times.xml | 5 | tube@dose_utc |  |
| sampling_times.xml | 6 | tube@drawn_utc |  |
| sampling_times.xml | 7 | tube@elapsed_h |  |
| isr_assessment.json | 1 | limit_pct | object: limit_pct, analytes keyed by analyte |
| isr_assessment.json | 2 | analytes.<A>.pairs[] (tube, run_id, reported, repeat, diff_pct, within) sorted by tube |  |
| isr_assessment.json | 3 | analytes.<A>.n_pairs |  |
| isr_assessment.json | 4 | analytes.<A>.n_within |  |
| isr_assessment.json | 5 | analytes.<A>.pct_within |  |
| isr_assessment.json | 6 | analytes.<A>.pass |  |
| nca_parameters.csv | 1 | subject_id | one row per in-scope subject, dosed period and analysed analyte, sorted by subject_id, period, analyte (profile order) |
| nca_parameters.csv | 2 | period |  |
| nca_parameters.csv | 3 | formulation |  |
| nca_parameters.csv | 4 | analyte |  |
| nca_parameters.csv | 5 | n_points |  |
| nca_parameters.csv | 6 | cmax |  |
| nca_parameters.csv | 7 | tmax |  |
| nca_parameters.csv | 8 | clast |  |
| nca_parameters.csv | 9 | tlast |  |
| nca_parameters.csv | 10 | auc_last |  |
| nca_parameters.csv | 11 | lambda_z |  |
| nca_parameters.csv | 12 | lz_points |  |
| nca_parameters.csv | 13 | lz_adj_r2 |  |
| nca_parameters.csv | 14 | half_life |  |
| nca_parameters.csv | 15 | clast_pred |  |
| nca_parameters.csv | 16 | auc_inf |  |
| nca_parameters.csv | 17 | auc_extrap_pct |  |
| nca_parameters.csv | 18 | flag |  |
| lambda_z_selection.jsonl | 1 | subject_id | one object per row of nca_parameters.csv in the same order |
| lambda_z_selection.jsonl | 2 | period |  |
| lambda_z_selection.jsonl | 3 | analyte |  |
| lambda_z_selection.jsonl | 4 | candidates[] (n, slope, intercept, adj_r2, eligible) by ascending n |  |
| lambda_z_selection.jsonl | 5 | chosen_n |  |
| be_statistics.json | 1 | analytes.<A>.role (PIVOTAL or SUPPORTIVE) | object: study_id, alpha, ci_level_pct, limits_pct [lower, upper], analytes keyed by analyte |
| be_statistics.json | 2 | analytes.<A>.conclusion |  |
| be_statistics.json | 3 | analytes.<A>.parameters.<P>.n_TR / n_RT / df / t_quantile |  |
| be_statistics.json | 4 | estimate_log / se_log / mse / cv_intra_pct |  |
| be_statistics.json | 5 | lsmean_T / lsmean_R (geometric) |  |
| be_statistics.json | 6 | ratio_pct / ci_lower_pct / ci_upper_pct |  |
| be_statistics.json | 7 | ratio_pct_r / ci_lower_r / ci_upper_r (rounded) |  |
| be_statistics.json | 8 | result (PASS, FAIL, INFO or NOT_ESTIMABLE) |  |
| be_summary.md | 1 | analyte | title `# <study_id> bioequivalence summary`, then a pipe table in analyte (profile order) and parameter (profile order) order |
| be_summary.md | 2 | parameter |  |
| be_summary.md | 3 | n |  |
| be_summary.md | 4 | ratio_pct |  |
| be_summary.md | 5 | ci_lower |  |
| be_summary.md | 6 | ci_upper |  |
| be_summary.md | 7 | cv_intra_pct |  |
| be_summary.md | 8 | result |  |
| analysis_populations.csv | 1 | subject_id | one row per randomized subject, analysed analyte and parameter, sorted by subject_id, analyte, parameter (profile orders) |
| analysis_populations.csv | 2 | analyte |  |
| analysis_populations.csv | 3 | parameter |  |
| analysis_populations.csv | 4 | included |  |
| analysis_populations.csv | 5 | reason |  |
| excluded_subjects.jsonl | 1 | subject_id | one object per in-scope subject and analyte with a subject-level reason (H16 2-7), sorted by subject_id then analyte |
| excluded_subjects.jsonl | 2 | analyte |  |
| excluded_subjects.jsonl | 3 | reason |  |
| excluded_subjects.jsonl | 4 | period |  |
| excluded_subjects.jsonl | 5 | value |  |
| mean_profiles.csv | 1 | analyte | one row per analysed analyte (profile order), formulation (R then T) and nominal time (ascending) with n at least 1 |
| mean_profiles.csv | 2 | formulation |  |
| mean_profiles.csv | 3 | nominal_h |  |
| mean_profiles.csv | 4 | n |  |
| mean_profiles.csv | 5 | mean |  |
| mean_profiles.csv | 6 | sd |  |
| dedup_report.json | 1 | rows_read | object of counters (H3, H5, H11) |
| dedup_report.json | 2 | duplicate_copies |  |
| dedup_report.json | 3 | superseded |  |
| dedup_report.json | 4 | inadmissible_manual |  |
| dedup_report.json | 5 | voided |  |
| dedup_report.json | 6 | effective_injections |  |
| dedup_report.json | 7 | standards |  |
| dedup_report.json | 8 | qcs |  |
| dedup_report.json | 9 | blank_zero |  |
| dedup_report.json | 10 | study_sample_injections |  |
| dedup_report.json | 11 | foreign_injections |  |
| source_lineage.json | 1 | shards[].file | object: shards (catalog order, active only), inactive (file names) |
| source_lineage.json | 2 | shards[].layout |  |
| source_lineage.json | 3 | shards[].rows |  |
| source_lineage.json | 4 | shards[].effective |  |
| source_lineage.json | 5 | inactive |  |
| alias_resolution.csv | 1 | kind | one row per distinct (kind, upper-case token, canonical) observed and resolved, sorted by kind, token |
| alias_resolution.csv | 2 | token |  |
| alias_resolution.csv | 3 | canonical |  |
| parameters_used.yaml | 1 | key | flat `key: value` lines, one per governing setting |
| parameters_used.yaml | 2 | value |  |
| variance_vs_published.csv | 1 | subject_id | one row per subject, period, analyte, parameter of either side (H20), sorted by subject_id, period, analyte (text order), parameter (Cmax, AUClast, AUCinf) |
| variance_vs_published.csv | 2 | period |  |
| variance_vs_published.csv | 3 | analyte |  |
| variance_vs_published.csv | 4 | parameter |  |
| variance_vs_published.csv | 5 | published |  |
| variance_vs_published.csv | 6 | recomputed |  |
| variance_vs_published.csv | 7 | diff_pct |  |
| variance_vs_published.csv | 8 | status |  |
| reconciliation.md | 1 | analyte | title `# <study_id> published versus recomputed`, then a pipe table in analyte and parameter order |
| reconciliation.md | 2 | parameter |  |
| reconciliation.md | 3 | published_ratio |  |
| reconciliation.md | 4 | published_lower |  |
| reconciliation.md | 5 | published_upper |  |
| reconciliation.md | 6 | published_result |  |
| reconciliation.md | 7 | recomputed_ratio |  |
| reconciliation.md | 8 | recomputed_lower |  |
| reconciliation.md | 9 | recomputed_upper |  |
| reconciliation.md | 10 | recomputed_result |  |
| manifest.json | 1 | files[].name | object files: list of {name, bytes, sha256} for every other output in this contract order |
| manifest.json | 2 | files[].bytes |  |
| manifest.json | 3 | files[].sha256 |  |

## Value vocabularies and details

| field | values or rule |
|---|---|
| status (standard_backcalc) | RETAINED, REMOVED, ASSIGNABLE, NO_CURVE |
| back_calculated (standard_backcalc, qc_results) | reading from the final curve (x dilution factor for DQC); empty without a reading |
| status (run_acceptance) | ACCEPTED, REJECTED; reason is the H9 reason or empty |
| dqc_status | PASS, FAIL, NA |
| lab_status, agrees | lab status from run_status_dashboard.csv (empty when absent); agrees is Y when it equals status |
| analysis_date | YYYY-MM-DD |
| reason (tube_results) | ORIGINAL, RUN_FAIL, ALQ, PK_REPEAT, ISR |
| flag (tube_results) | RUN_REJECTED, DQC_FAIL, BLQ, ALQ, OK |
| used (tube_results) | Y when the result is the base, the dilution result or a median member that produced the reported value of an OK or BLQ tube |
| status (reported_concentrations) | OK, BLQ, NR, EXCL, NOT_COLLECTED |
| rule (reported_concentrations) | ORIGINAL, RUN_FAIL, ALQ_DILUTION, ALQ_NO_DILUTION, PK_REPEAT_MEDIAN, RULING, NONE |
| source_run | run of the base result (of the dilution result for ALQ_DILUTION); empty for NR without base, EXCL and NOT_COLLECTED |
| actual_h | elapsed hours (H13); empty for NO_TIME and NOT_COLLECTED |
| nominal_h | as a number (0 for PRE) |
| tube (outputs) | the original barcode (relabels resolved) |
| flag (nca_parameters) | OK, NOT_EVALUABLE, NO_LAMBDA_Z, EXTRAP_GT_LIMIT; parameters that do not exist are empty |
| reason (analysis_populations) | NOT_IN_SCOPE, RULING, WITHDRAWN, INCOMPLETE, EMESIS, NOT_EVALUABLE, CARRYOVER, PARAM_NA, EXTRAP; empty when included |
| period, value (excluded_subjects) | EMESIS: period and onset elapsed hours of the first qualifying event in the settled pass (period order, then onset); CARRYOVER: first period and 100 x pre-dose / Cmax; NOT_EVALUABLE: first such period, null; INCOMPLETE: first period without a dose, null; RULING, WITHDRAWN: null, null |
| rounded fields (be_statistics *_r, be_summary ratio_pct, ci_lower, ci_upper, cv_intra_pct, reconciliation recomputed_*) | two decimals, half away from zero |
| other numbers | H21 and H22: stage values (coefficients, concentrations, elapsed hours) as rounded at their stage; every other non-integer value rounded half away from zero to six significant digits |
| emesis_reference_mean_tmax_h, emesis_window_h | the mean Tmax and window of the pass the analysis settles on (H16) |
| emesis_passes, emesis_settlement | number of passes computed up to and including the stopping pass; CONVERGED or CYCLE (H16) |
| kind (alias_resolution) | run (tokens in active shards, requests, reassay log and Table R-1), subject (tokens in manifests, dose logs, draw logs, AE rows of this study, disposition log and Table R-1 rows of this study), tube (tokens in active shards, the reassay log and Table R-1 rows of this study that resolve through an ACTIVE relabel) |
| parameters_used.yaml keys | study_id, nominal_sheet, alpha, ci_level_pct, be_lower_pct, be_upper_pct, t_quantile_p, lambda_z_min_points, lambda_z_adj_r2_tolerance, extrap_limit_pct, carryover_limit_pct, emesis_window_factor, emesis_reference_mean_tmax_h, emesis_window_h, emesis_passes, emesis_settlement, isr_limit_pct, then per analysed analyte <analyte>.model, <analyte>.weighting, <analyte>.std_limit_pct, <analyte>.lloq_std_limit_pct, <analyte>.qc_limit_pct, then conventions_table, method_table, t_table |
| dedup counters | rows_read: records read; duplicate_copies: extra copies (H3); superseded: admissible records that lost to a higher revision; inadmissible_manual: MANUAL records that are not admissible; voided: injections removed; the remaining counters split the effective injections |
| shards[].effective | rows of the shard whose record is the effective record of a kept injection (copies in several shards each count) |
| published | value from be_report_published.csv; recomputed from nca_parameters.csv (AUCinf only when included-eligible values exist: flag OK) |
