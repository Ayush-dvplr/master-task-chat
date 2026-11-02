# Output contract

Every report is UTF-8 with LF line endings and a final newline. Delimited reports carry exactly the header named here, in this order,
unquoted. Negative numbers carry a leading minus sign and no number carries a plus sign.
JSON reports are one document; JSON Lines reports hold one object per line. Numbers carry the decimals stated here and are
compared by value. Empty cells and null stand for values that do not apply. `manifest.json` lists the other reports in the order
of this contract: one JSON object whose only key `files` holds an array of objects name, bytes, sha256. Rows of delimited reports and JSON Lines objects compare as sets, as do the
objects of JSON arrays except the `files` array of source_lineage.json, whose order is the processing order; arrays of plain
values keep their stated order. Session tokens of the QC dashboard and of the published session parameters
resolve under handbook H2 with the profile project.

| report | format | column or key | content |
|---|---|---|---|
| injection_ledger.csv | csv | (rows) | one row per kept injection element of every project session, linearity sessions included; sorted by session, counter_position, profile element order |
| injection_ledger.csv | csv | session | canonical session id |
| injection_ledger.csv | csv | instrument | K1 or K2 |
| injection_ledger.csv | csv | counter_position | integer |
| injection_ledger.csv | csv | tray_position | integer (H5) |
| injection_ledger.csv | csv | material | canonical material |
| injection_ledger.csv | csv | element | N or C |
| injection_ledger.csv | csv | revision | selected revision |
| injection_ledger.csv | csv | area_vs | 4 decimals, Vs |
| injection_ledger.csv | csv | amplitude_mv | integer mV |
| injection_ledger.csv | csv | delta_raw | 3 decimals |
| injection_ledger.csv | csv | utc_time | YYYY-MM-DDTHH:MM:SSZ |
| injection_ledger.csv | csv | run_minutes | 4 decimals (H6) |
| injection_ledger.csv | csv | excluded | RULING:<id>, FLAG:<code> or empty (H7) |
| position_resolution.csv | csv | (rows) | one row per tray of every project session; sorted by session, tray_position |
| position_resolution.csv | csv | session | canonical session id |
| position_resolution.csv | csv | tray_position | integer |
| position_resolution.csv | csv | counter_position | integer, empty when skipped |
| position_resolution.csv | csv | sequence_token | token of sequence_tables.xml, trimmed |
| position_resolution.csv | csv | journal_seq | seq of the SET entry in effect, empty when none |
| position_resolution.csv | csv | material | canonical material |
| position_resolution.csv | csv | material_class | RM, QC, ELM, BLK, COND or SAMPLE |
| position_resolution.csv | csv | capsule_id | as in the sequence table, upper case |
| position_resolution.csv | csv | mass_mg | corrected mass, 4 decimals, empty when the tray has no weighed capsule |
| position_resolution.csv | csv | status | MEASURED, EXCLUDED or SKIPPED |
| alias_resolution.psv | psv | (rows) | one row per distinct kind, normalized token and canonical value where the canonical value differs from the token (a time-gated token can give two rows), seen as a session or instrument token on analyte peak records of active segments of the project, a sequence id or slot token of a project sequence, or a session token or token value of a project journal entry; sorted by kind, token |
| alias_resolution.psv | psv | kind | session, instrument or material |
| alias_resolution.psv | psv | token | trimmed, upper case |
| alias_resolution.psv | psv | canonical | resolved canonical value |
| dedup_report.json | json | (rows) | one object |
| dedup_report.json | json | files_read | integer |
| dedup_report.json | json | records_read | integer |
| dedup_report.json | json | other_project | integer |
| dedup_report.json | json | reference_peaks | integer |
| dedup_report.json | json | inactive_segment | integer |
| dedup_report.json | json | duplicates | integer |
| dedup_report.json | json | revisions_not_admitted | integer |
| dedup_report.json | json | revisions_superseded | integer |
| dedup_report.json | json | voided | integer |
| dedup_report.json | json | kept | integer |
| source_lineage.json | json | (rows) | object with key files: one object per read file in processing order |
| source_lineage.json | json | file | file name |
| source_lineage.json | json | layout | layout id |
| source_lineage.json | json | records | integer |
| source_lineage.json | json | other_project | integer |
| source_lineage.json | json | reference_peaks | integer |
| source_lineage.json | json | inactive_segment | integer |
| source_lineage.json | json | duplicates | integer |
| source_lineage.json | json | unique | records passing every filter |
| linearity_slopes.json | json | (rows) | object with lin_sessions (per linearity session and element, sorted by session then element order) and assignments (per analytical session and element) |
| linearity_slopes.json | json | lin_sessions[].session | canonical id |
| linearity_slopes.json | json | lin_sessions[].instrument | K1 or K2 |
| linearity_slopes.json | json | lin_sessions[].local_date | YYYY-MM-DD session date |
| linearity_slopes.json | json | lin_sessions[].element | N or C |
| linearity_slopes.json | json | lin_sessions[].n_points | integer |
| linearity_slopes.json | json | lin_sessions[].slope | 6 decimals or null |
| linearity_slopes.json | json | assignments[].session | canonical id |
| linearity_slopes.json | json | assignments[].element | N or C |
| linearity_slopes.json | json | assignments[].lin_session | id or null |
| linearity_slopes.json | json | assignments[].lin_slope | 6 decimals or null |
| linearity_slopes.json | json | assignments[].applied_slope | 6 decimals |
| linearity_slopes.json | json | assignments[].status | APPLIED, BELOW_THRESHOLD or NONE |
| drift_fits.tsv | tsv | (rows) | one row per analytical session and element; sorted by session, element order |
| drift_fits.tsv | tsv | session | canonical id |
| drift_fits.tsv | tsv | element | N or C |
| drift_fits.tsv | tsv | drift_material | profile drift material |
| drift_fits.tsv | tsv | n_points | integer |
| drift_fits.tsv | tsv | slope_per_min | 8 decimals |
| drift_fits.tsv | tsv | anchor_min | 4 decimals |
| drift_fits.tsv | tsv | status | FITTED or INSUFFICIENT |
| blank_corrections.psv | psv | (rows) | one row per analytical session and element |
| blank_corrections.psv | psv | session | canonical id |
| blank_corrections.psv | psv | element | N or C |
| blank_corrections.psv | psv | n_blanks | integer |
| blank_corrections.psv | psv | n_rejected | integer |
| blank_corrections.psv | psv | mean_area_vs | 4 decimals |
| blank_corrections.psv | psv | mean_delta | 3 decimals |
| normalization_fits.json | json | (rows) | object with key fits: one object per analytical session and element |
| normalization_fits.json | json | session | canonical id |
| normalization_fits.json | json | element | N or C |
| normalization_fits.json | json | reference_set | list of materials in N-2 order |
| normalization_fits.json | json | n_points | points in the final fit |
| normalization_fits.json | json | fits | integer |
| normalization_fits.json | json | slope | 6 decimals or null |
| normalization_fits.json | json | intercept | 6 decimals or null |
| normalization_fits.json | json | removed | list of objects tray_position, material, residual (certified minus fitted, 4 decimals) in removal order |
| normalization_fits.json | json | status | CONVERGED, LIMIT_STOP, MAX_REJECT or NO_NORMALIZATION |
| corrected_injections.jsonl | jsonl | (rows) | one object per non-excluded RM, QC, ELM or SAMPLE injection element of the analytical sessions; sorted by session, tray_position, element order |
| corrected_injections.jsonl | jsonl | session | canonical id |
| corrected_injections.jsonl | jsonl | tray_position | integer |
| corrected_injections.jsonl | jsonl | material | canonical |
| corrected_injections.jsonl | jsonl | material_class | class |
| corrected_injections.jsonl | jsonl | element | N or C |
| corrected_injections.jsonl | jsonl | d_lin | 4 decimals |
| corrected_injections.jsonl | jsonl | d_drift | 4 decimals |
| corrected_injections.jsonl | jsonl | d_blank | 4 decimals |
| corrected_injections.jsonl | jsonl | d_norm | 3 decimals or null |
| corrected_injections.jsonl | jsonl | pct | 3 decimals or null; null for ELM |
| elemental_factors.tsv | tsv | (rows) | one row per analytical session and element |
| elemental_factors.tsv | tsv | session | canonical id |
| elemental_factors.tsv | tsv | element | N or C |
| elemental_factors.tsv | tsv | n_standards | integer |
| elemental_factors.tsv | tsv | factor_ug_per_vs | 6 decimals or empty |
| session_acceptance.csv | csv | (rows) | one row per analytical session and element |
| session_acceptance.csv | csv | session | canonical id |
| session_acceptance.csv | csv | element | N or C |
| session_acceptance.csv | csv | instrument | K1 or K2 |
| session_acceptance.csv | csv | norm_slope | 6 decimals or empty |
| session_acceptance.csv | csv | slope_ok | Y or N |
| session_acceptance.csv | csv | qc_checks | <material>:<deviation 3 decimals, minus sign only when negative>:<PASS|FAIL> joined by ; in Q-1 order |
| session_acceptance.csv | csv | leak | Y or N |
| session_acceptance.csv | csv | computed | ACCEPT or REJECT |
| session_acceptance.csv | csv | ruling | ruling id or empty |
| session_acceptance.csv | csv | decision | ACCEPT or REJECT |
| session_acceptance.csv | csv | reasons | reasons joined by ; (H13) |
| qc_results.xml | xml | (rows) | root qc_results with attribute project; one check element per checked QC material, session and element |
| qc_results.xml | xml | check@session | canonical id |
| qc_results.xml | xml | check@element | N or C |
| qc_results.xml | xml | check@material | QC material |
| qc_results.xml | xml | check@n | integer |
| qc_results.xml | xml | check@mean | 3 decimals |
| qc_results.xml | xml | check@assigned | 2 decimals |
| qc_results.xml | xml | check@deviation | 3 decimals |
| qc_results.xml | xml | check@tolerance | 2 decimals |
| qc_results.xml | xml | check@result | PASS or FAIL |
| isotope_results.csv | csv | (rows) | one row per sample in scope; sorted by sample_id; empty cells where a value does not apply |
| isotope_results.csv | csv | sample_id | canonical |
| isotope_results.csv | csv | d15N_air | 2 decimals |
| isotope_results.csv | csv | d15N_sd | 2 decimals |
| isotope_results.csv | csv | n_N | integer, 0 for NO_DATA, empty for NOT_REQUESTED |
| isotope_results.csv | csv | pct_N | 2 decimals |
| isotope_results.csv | csv | status_N | REPORTED, SINGLE, NO_DATA or NOT_REQUESTED |
| isotope_results.csv | csv | d13C_vpdb | 2 decimals |
| isotope_results.csv | csv | d13C_sd | 2 decimals |
| isotope_results.csv | csv | n_C | integer, 0 for NO_DATA, empty for NOT_REQUESTED |
| isotope_results.csv | csv | pct_C | 2 decimals |
| isotope_results.csv | csv | status_C | status |
| isotope_results.csv | csv | cn_molar | 2 decimals |
| replicate_screening.jsonl | jsonl | (rows) | one object per in-scope sample and requested element with at least one value; sorted by sample, element order |
| replicate_screening.jsonl | jsonl | sample | canonical |
| replicate_screening.jsonl | jsonl | element | N or C |
| replicate_screening.jsonl | jsonl | initial_n | integer |
| replicate_screening.jsonl | jsonl | values | d_norm values in H14 order, 3 decimals |
| replicate_screening.jsonl | jsonl | removed | objects value (3 decimals), g (4 decimals), g_crit (the G-1 value, 4 decimals), n; value, g and g_crit are JSON numbers |
| replicate_screening.jsonl | jsonl | final_n | integer |
| parameters_used.yaml | yaml | (rows) | flat key: value lines in this order |
| parameters_used.yaml | yaml | project | profile |
| parameters_used.yaml | yaml | rm_sheet | profile |
| parameters_used.yaml | yaml | normalization_table | id of the table applied |
| parameters_used.yaml | yaml | reference_set_<e> | comma list |
| parameters_used.yaml | yaml | reject_limit_<e> | N-2 |
| parameters_used.yaml | yaml | max_reject_<e> | N-2 |
| parameters_used.yaml | yaml | linearity_threshold_<e> | L-1 |
| parameters_used.yaml | yaml | a_ref_<e> | profile |
| parameters_used.yaml | yaml | amplitude_min_<e> | A-1 |
| parameters_used.yaml | yaml | amplitude_max_<e> | A-1 |
| parameters_used.yaml | yaml | blank_area_max_<e> | A-1 |
| parameters_used.yaml | yaml | slope_min | N-2 |
| parameters_used.yaml | yaml | slope_max | N-2 |
| parameters_used.yaml | yaml | linearity_lookback_days | profile |
| parameters_used.yaml | yaml | drift_material | profile |
| parameters_used.yaml | yaml | drift_min_points | profile |
| parameters_used.yaml | yaml | grubbs_table | id of the table applied |
| parameters_used.yaml | yaml | grubbs_alpha | profile |
| parameters_used.yaml | yaml | molar_mass_C | Section AW |
| parameters_used.yaml | yaml | molar_mass_N | Section AW |
| parameters_used.yaml | yaml | date_system | 1904 or 1900 |
| parameters_used.yaml | yaml | clock_base_offset | site clock |
| parameters_used.yaml | yaml | qc_tolerance_<material>_<e> | Q-1, acceptance materials only |
| variance_vs_published.csv | csv | (rows) | one row per sample and element published or recomputed as REPORTED or SINGLE; sorted by sample_id, element order |
| variance_vs_published.csv | csv | sample_id | canonical |
| variance_vs_published.csv | csv | element | N or C |
| variance_vs_published.csv | csv | published | 2 decimals or empty |
| variance_vs_published.csv | csv | recomputed | 2 decimals or empty |
| variance_vs_published.csv | csv | diff | recomputed minus published, 2 decimals |
| variance_vs_published.csv | csv | status | MATCH when the absolute diff is at most 0.05, DIFF, ONLY_PUBLISHED, ONLY_RECOMPUTED |
| session_param_diff.json | json | (rows) | object with key sessions: one object per session and element of the published parameters, sorted by session, element order |
| session_param_diff.json | json | session | id |
| session_param_diff.json | json | element | N or C |
| session_param_diff.json | json | published_slope | 6 decimals |
| session_param_diff.json | json | recomputed_slope | 6 decimals or null |
| session_param_diff.json | json | published_intercept | 6 decimals |
| session_param_diff.json | json | recomputed_intercept | 6 decimals or null |
| session_param_diff.json | json | slope_diff | recomputed minus published or null |
| session_param_diff.json | json | intercept_diff | recomputed minus published or null |
| session_param_diff.json | json | published_points | rm_points of the published session |
| session_param_diff.json | json | recomputed_points | n_points or null |
| dashboard_disagreements.csv | csv | (rows) | one row per session and element present on the dashboard; sorted by session, element order |
| dashboard_disagreements.csv | csv | session | canonical id |
| dashboard_disagreements.csv | csv | element | N or C |
| dashboard_disagreements.csv | csv | dashboard_status | FAIL when any dashboard row of it is FAIL, else PASS |
| dashboard_disagreements.csv | csv | recomputed_decision | ACCEPT or REJECT |
| dashboard_disagreements.csv | csv | agrees | Y when PASS meets ACCEPT or FAIL meets REJECT, else N |
| cache_divergence.jsonl | jsonl | (rows) | one object per cache entry; sorted by sample, element order |
| cache_divergence.jsonl | jsonl | sample | canonical |
| cache_divergence.jsonl | jsonl | element | N or C |
| cache_divergence.jsonl | jsonl | cached | 2 decimals |
| cache_divergence.jsonl | jsonl | recomputed | 2 decimals or null |
| cache_divergence.jsonl | jsonl | status | CURRENT when recomputed exists and differs by at most 0.05, else STALE |
| reconciliation.md | md | (rows) | sections Summary, Session decisions, Run settings, Superseded notices, each one Markdown table |
| reconciliation.md | md | Summary | per element: recomputed_reported (sample elements REPORTED or SINGLE), published_reported (published values), compared (both present), diff_count (absolute diff above 0.05), mean_shift (mean of recomputed minus published over the compared values, 3 decimals); one row per element in profile element order |
| reconciliation.md | md | Session decisions | session elements whose computed or final decision is REJECT or that carry a ruling, sorted by session then element order: session, element, computed, ruling, decision, reasons |
| reconciliation.md | md | Run settings | every setting of the rerun pack Run settings table in its order: setting, published_run, in_force; in_force is the profile rm_sheet, N-2 for normalization_table, the N-2 set joined by commas for reference_set_N and reference_set_C, G-1 for grubbs_table, and otherwise drift_axis run_minutes, linearity_partition instrument_local_day, correction_order linearity,drift,blank,normalization, revision_rule audit_admitted, autosampler_skips applied, session_rulings R-1_in_force, arithmetic exact_decimal_stage_rounding |
| reconciliation.md | md | Superseded notices | noticeboard REFERENCE notices whose value differs from the in-force certified value, sorted by notice: notice, material, lot, element, notice_value, in_force_value (2 decimals) |

Element order is the order of `elements` in the analysis profile. Session order is ascending canonical id.
