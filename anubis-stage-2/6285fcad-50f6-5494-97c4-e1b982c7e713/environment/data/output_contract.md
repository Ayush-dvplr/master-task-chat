# Output contract

Every report is UTF-8 with LF line endings and a final newline. Delimited reports carry exactly the header named here, in this order.
Numbers carry the decimals stated here and are compared by value; negative numbers carry a leading minus sign and no number
carries a plus sign. Significant-figure values are written as plain decimals without exponent. JSON reports are one document;
JSON Lines reports hold one object per line. Empty cells and null stand for values that do not apply. Rows of delimited reports
and JSON Lines objects compare as sets, as do the objects of JSON arrays, except the files array of source_lineage.json, whose
order is the processing order, and the points arrays, whose order is stated. `manifest.json` lists the other reports in the
order of this contract: one JSON object whose only key `files` holds an array of objects name, bytes, sha256.

| report | format | column or key | content |
|---|---|---|---|
| unit_values.csv | csv | (rows) | one row per selected reading in the record window; sorted by site, time_lst |
| unit_values.csv | csv | site | station id |
| unit_values.csv | csv | time_lst | YYYY-MM-DD HH:MM |
| unit_values.csv | csv | sensor | P or B |
| unit_values.csv | csv | gh_ft | corrected gage height, 2 decimals |
| unit_values.csv | csv | shift_ft | s(t), 2 decimals |
| unit_values.csv | csv | gh_eff_ft | 2 decimals |
| unit_values.csv | csv | q_open_cfs | R(gh_eff), 4 significant figures |
| unit_values.csv | csv | k_factor | K(t), 3 decimals, empty outside ice periods |
| unit_values.csv | csv | q_cfs | 4 significant figures |
| unit_values.csv | csv | flags | B, I, > in that order with no separator (for example BI), or empty |
| gh_corrections.tsv | tsv | (rows) | one row per correction segment of every site; sorted by site, from_lst |
| gh_corrections.tsv | tsv | site | station id |
| gh_corrections.tsv | tsv | from_lst | time of the used visit that opens the segment |
| gh_corrections.tsv | tsv | to_lst | time of the next used visit, empty for the last segment |
| gh_corrections.tsv | tsv | start_ft | ak, 2 decimals |
| gh_corrections.tsv | tsv | end_ft | bk+1, 2 decimals; the last segment repeats ak |
| visit_errors.psv | psv | (rows) | one row per visit of an in-scope site after the amendments, voided ones included; sorted by site, time_lst, visit_id |
| visit_errors.psv | psv | site | station id |
| visit_errors.psv | psv | visit_id | integer |
| visit_errors.psv | psv | time_lst | visit time |
| visit_errors.psv | psv | method | reference method used |
| visit_errors.psv | psv | reference_ft | 2 decimals |
| visit_errors.psv | psv | logger_ft | 2 decimals |
| visit_errors.psv | psv | error_ft | reference minus logger, 2 decimals |
| visit_errors.psv | psv | applied_ft | 2 decimals, empty unless USED |
| visit_errors.psv | psv | action | RESET or NONE |
| visit_errors.psv | psv | status | USED, DISREGARDED or VOID |
| measurement_eval.csv | csv | (rows) | one row per measurement of an in-scope site; sorted by meas_no |
| measurement_eval.csv | csv | meas_no | integer |
| measurement_eval.csv | csv | site | station id |
| measurement_eval.csv | csv | instant_lst | H11 instant |
| measurement_eval.csv | csv | grade | final grade |
| measurement_eval.csv | csv | verdict | ACCEPT, REJECT or REGRADE |
| measurement_eval.csv | csv | cover | as recorded |
| measurement_eval.csv | csv | gh_ft | record gage height, 2 decimals, empty when none |
| measurement_eval.csv | csv | rating_id | version in force, empty for REJECTED and NO_RECORD |
| measurement_eval.csv | csv | shift_in_use_ft | 2 decimals, empty for REJECTED and NO_RECORD |
| measurement_eval.csv | csv | rated_q_cfs | 4 significant figures, empty for REJECTED and NO_RECORD |
| measurement_eval.csv | csv | measured_q_cfs | cfs, 2 decimals |
| measurement_eval.csv | csv | deviation_pct | 1 decimal, open water only |
| measurement_eval.csv | csv | tolerance_pct | 1 decimal, open water grades E, G, F only |
| measurement_eval.csv | csv | decision | SHIFT, CHECK, ICE, REJECTED or NO_RECORD |
| measurement_eval.csv | csv | shift_ft | 2 decimals, SHIFT only |
| measurement_eval.csv | csv | k_factor | 3 decimals, ICE only |
| shift_curves.json | json | (rows) | object with key curves: one object per ACTIVE version of an in-scope site, sorted by site then effective instant |
| shift_curves.json | json | site | station id |
| shift_curves.json | json | rating_id | id |
| shift_curves.json | json | effective_lst | effective instant |
| shift_curves.json | json | points | objects time_lst, shift_ft (JSON number, 2 decimals), source (START or the meas_no as a string) in curve order |
| ice_periods.jsonl | jsonl | (rows) | one object per ice period of an in-scope site after the replay; sorted by site, on_lst |
| ice_periods.jsonl | jsonl | site | station id |
| ice_periods.jsonl | jsonl | on_lst | time |
| ice_periods.jsonl | jsonl | off_lst | time or null |
| ice_periods.jsonl | jsonl | on_entry | entry of the ON event |
| ice_periods.jsonl | jsonl | off_entry | entry of the OFF event or null |
| ice_periods.jsonl | jsonl | k_points | objects meas_no, time_lst, k (JSON number, 3 decimals) in instant order |
| ice_periods.jsonl | jsonl | default_k | Table W-1 value when there is no K point, else null |
| ice_periods.jsonl | jsonl | unit_values | number of unit values inside the period |
| rating_tables_used.json | json | (rows) | object with key ratings: one object per ACTIVE version of an in-scope site, sorted by site then effective instant |
| rating_tables_used.json | json | rating_id | id |
| rating_tables_used.json | json | site | station id |
| rating_tables_used.json | json | effective_lst | effective instant |
| rating_tables_used.json | json | points | objects gh_ft, q_cfs, offset_ft (JSON numbers) after the errata, ascending gh |
| rating_tables_used.json | json | errata_applied | objects gh_ft, from_q_cfs, to_q_cfs for each R-2 erratum applied, ascending gh |
| daily_values.csv | csv | (rows) | one row per in-scope site and period day; sorted by site, date |
| daily_values.csv | csv | site | station id |
| daily_values.csv | csv | date | YYYY-MM-DD |
| daily_values.csv | csv | q_mean_cfs | discharge table, empty for INC |
| daily_values.csv | csv | coverage_h | coverage in hours, 2 decimals |
| daily_values.csv | csv | n_readings | integer |
| daily_values.csv | csv | codes | INC;ICE;B;> subset in that order, or empty |
| monthly_summary.xml | xml | (rows) | root monthly_summary with attributes network, period_start, period_end; one month element per in-scope site and month |
| monthly_summary.xml | xml | month@site | station id |
| monthly_summary.xml | xml | month@month | YYYY-MM |
| monthly_summary.xml | xml | month@days | period days in the month |
| monthly_summary.xml | xml | month@complete_days | integer |
| monthly_summary.xml | xml | month@mean_cfs | discharge table or empty |
| monthly_summary.xml | xml | month@min_cfs | or empty |
| monthly_summary.xml | xml | month@max_cfs | or empty |
| monthly_summary.xml | xml | month@volume_af | 1 decimal or empty |
| monthly_summary.xml | xml | month@runoff_in | 2 decimals or empty |
| monthly_summary.xml | xml | month@complete | true or false |
| period_statistics.json | json | (rows) | object with key sites: one object per in-scope site in id order |
| period_statistics.json | json | site | station id |
| period_statistics.json | json | peak_q_cfs | 4 significant figures |
| period_statistics.json | json | peak_time_lst | time |
| period_statistics.json | json | min_7day_cfs | discharge table or null |
| period_statistics.json | json | min_7day_start | first date of the window or null |
| period_statistics.json | json | mean_cfs | discharge table or null |
| period_statistics.json | json | complete_days | integer |
| period_statistics.json | json | inc_days | integer |
| period_statistics.json | json | ice_days | integer |
| period_statistics.json | json | backup_days | integer |
| period_statistics.json | json | above_rating_days | integer |
| period_statistics.json | json | shift_points | integer |
| period_statistics.json | json | ice_measurements | integer |
| alias_resolution.csv | csv | (rows) | one row per normalized token and in-scope station it resolved to on a shard record, when the token differs from the id; sorted by token, site |
| alias_resolution.csv | csv | token | normalized token |
| alias_resolution.csv | csv | site | station id |
| alias_resolution.csv | csv | records | records of read shards carrying the token that resolved to the site |
| dedup_report.json | json | (rows) | one object with integer counters in this order |
| dedup_report.json | json | files_read | listed files present |
| dedup_report.json | json | records_read | records |
| dedup_report.json | json | unknown_site | H4 |
| dedup_report.json | json | out_of_scope | H4 |
| dedup_report.json | json | unrouted | H4 |
| dedup_report.json | json | out_of_window | H4 |
| dedup_report.json | json | admitted | H4 |
| dedup_report.json | json | superseded | H6 |
| dedup_report.json | json | duplicates | H6 |
| dedup_report.json | json | voided | H6 |
| dedup_report.json | json | edits_applied | H7 |
| dedup_report.json | json | edits_ignored | H7 |
| dedup_report.json | json | edit_deleted | H7 |
| dedup_report.json | json | sensor_fault | H8 |
| dedup_report.json | json | backup_unused | H8 |
| dedup_report.json | json | kept | H8 |
| source_lineage.json | json | (rows) | object with key files: one object per read file in processing order |
| source_lineage.json | json | file | file name |
| source_lineage.json | json | layout | layout id |
| source_lineage.json | json | records | integer |
| source_lineage.json | json | unknown_site | integer |
| source_lineage.json | json | out_of_scope | integer |
| source_lineage.json | json | unrouted | integer |
| source_lineage.json | json | out_of_window | integer |
| source_lineage.json | json | admitted | integer |
| reading_exclusions.jsonl | jsonl | (rows) | one object per reading removed after admission; sorted by site, time_lst, sensor |
| reading_exclusions.jsonl | jsonl | site | station id |
| reading_exclusions.jsonl | jsonl | sensor | P or B |
| reading_exclusions.jsonl | jsonl | time_lst | time |
| reading_exclusions.jsonl | jsonl | reason | VOIDED, EDIT_DELETED, SENSOR_FAULT or BACKUP_UNUSED |
| reading_exclusions.jsonl | jsonl | file | file of the winning copy |
| amendment_ledger.psv | psv | (rows) | one row per unit-value edit of an in-scope station; sorted by seq |
| amendment_ledger.psv | psv | seq | integer |
| amendment_ledger.psv | psv | site | station id |
| amendment_ledger.psv | psv | sensor | P or B |
| amendment_ledger.psv | psv | time_lst | time |
| amendment_ledger.psv | psv | op | SET, DELETE or RESTORE |
| amendment_ledger.psv | psv | status | APPLIED or IGNORED |
| parameters_used.yaml | yaml | (rows) | flat key: value lines in this order |
| parameters_used.yaml | yaml | network | profile |
| parameters_used.yaml | yaml | period_start | profile |
| parameters_used.yaml | yaml | period_end | profile |
| parameters_used.yaml | yaml | rating_sheet | profile block |
| parameters_used.yaml | yaml | index_sheet | profile block |
| parameters_used.yaml | yaml | site_sheet | profile block |
| parameters_used.yaml | yaml | max_gap_minutes | profile block |
| parameters_used.yaml | yaml | min_coverage_fraction | 2 decimals |
| parameters_used.yaml | yaml | record_margin_hours | profile block |
| parameters_used.yaml | yaml | drift_tolerance_default_ft | profile block |
| parameters_used.yaml | yaml | tolerance_table | id of the table applied |
| parameters_used.yaml | yaml | tolerance_E_pct | table value |
| parameters_used.yaml | yaml | tolerance_G_pct | table value |
| parameters_used.yaml | yaml | tolerance_F_pct | table value |
| parameters_used.yaml | yaml | winter_table | id |
| parameters_used.yaml | yaml | errata_table | id |
| parameters_used.yaml | yaml | errata_applied | number of errata applied |
| parameters_used.yaml | yaml | date_system | 1900 or 1904 |
| parameters_used.yaml | yaml | clock_standard_offset_minutes | site clock |
| parameters_used.yaml | yaml | dst_rule | site clock |
| parameters_used.yaml | yaml | drift_tolerance_<site> | per in-scope site in id order, followed by max_gap_<site> and winter_k_<site> |
| variance_vs_published.csv | csv | (rows) | one row per site and date published or recomputed with a value; sorted by site, date |
| variance_vs_published.csv | csv | site | station id |
| variance_vs_published.csv | csv | date | YYYY-MM-DD |
| variance_vs_published.csv | csv | published_cfs | or empty |
| variance_vs_published.csv | csv | recomputed_cfs | or empty |
| variance_vs_published.csv | csv | diff_cfs | recomputed minus published or empty |
| variance_vs_published.csv | csv | status | MATCH, DIFF, ONLY_PUBLISHED or ONLY_RECOMPUTED |
| shift_vs_published.csv | csv | (rows) | one row per row of the published shift worksheet; sorted by meas_no |
| shift_vs_published.csv | csv | meas_no | integer |
| shift_vs_published.csv | csv | site | station id |
| shift_vs_published.csv | csv | published_decision | as published |
| shift_vs_published.csv | csv | published_shift_ft | 2 decimals or empty |
| shift_vs_published.csv | csv | recomputed_decision | or empty |
| shift_vs_published.csv | csv | recomputed_shift_ft | 2 decimals or empty |
| shift_vs_published.csv | csv | status | AGREE, DIFFER or NOT_FOUND |
| dashboard_disagreements.tsv | tsv | (rows) | one row per dashboard row of an in-scope site and period day that disagrees; sorted by site, date |
| dashboard_disagreements.tsv | tsv | site | station id |
| dashboard_disagreements.tsv | tsv | date | YYYY-MM-DD |
| dashboard_disagreements.tsv | tsv | dashboard_cfs | or empty |
| dashboard_disagreements.tsv | tsv | recomputed_cfs | or empty |
| dashboard_disagreements.tsv | tsv | dashboard_ice | Y or N |
| dashboard_disagreements.tsv | tsv | recomputed_ice | Y or N |
| dashboard_disagreements.tsv | tsv | q_agrees | Y or N |
| dashboard_disagreements.tsv | tsv | ice_agrees | Y or N |
| cache_divergence.jsonl | jsonl | (rows) | one object per cache entry of an in-scope station; sorted by site, time_lst |
| cache_divergence.jsonl | jsonl | site | station id |
| cache_divergence.jsonl | jsonl | time_lst | time |
| cache_divergence.jsonl | jsonl | cached_cfs | JSON number |
| cache_divergence.jsonl | jsonl | recomputed_cfs | JSON number or null |
| cache_divergence.jsonl | jsonl | status | CURRENT, STALE or MISSING |
| reconciliation.md | md | (rows) | sections Summary, Run settings and Measurement decisions, each one Markdown table |
| reconciliation.md | md | Summary | per in-scope site in id order: site, published_days (published rows with a value), recomputed_days (days with a value), compared (days with both), diff_count (compared days that differ), mean_diff_cfs (mean of recomputed minus published over compared days, 2 decimals) |
| reconciliation.md | md | Run settings | every setting of the compute pack Run settings table in its order: setting, published_run, in_force; in_force is the profile rating_sheet for rating_sheet, T-2 for tolerance_table, R-2 for errata, record_mean, shift_in_use, time_weighted_discharge, local_standard_time, prorated_visit_errors and seq_order for the other settings in the pack order |
| reconciliation.md | md | Measurement decisions | per in-scope site in id order: site, measurements, shift, check, ice, rejected, no_record |

Times are LST (handbook H3). Station ids are canonical ids of the station master.
