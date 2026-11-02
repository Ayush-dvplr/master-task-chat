# Output contract

Every report, and manifest.json, is UTF-8 with LF line endings and a final newline. Delimited
reports start with the header of their column list and quote nothing. Numbers are plain decimals with the stated number of decimals, never a
negative zero. JSON numbers are written as decimals; JSON keys appear in the order listed. Empty fields are empty strings
in delimited files and attribute values, null in JSON.

manifest.json lists every report below in this order as objects name, bytes and sha256 under a `files` key.

## setup_ledger.csv

- format: CSV
- rows: one row per kept setup of every VALID run, sorted by run_id then seq

| field | content |
| --- | --- |
| run_id | run id R-26-dddd |
| seq | setup number |
| instant_utc | setup instant, ISO 8601 UTC with a Z suffix, whole seconds |
| back_rod | serial of the back rod (H7) |
| fore_rod | serial of the fore rod (H7) |
| back_m | decoded back reading in metres after half-centimetre decoding, 5 decimals |
| fore_m | decoded fore reading, 5 decimals |
| back_dist_m | back sight distance, 1 decimal |
| fore_dist_m | fore sight distance, 1 decimal |
| temp_c | rod temperature used (H11), 1 decimal |
| temp_source | FIELD, MET or FALLBACK |
| dh_raw_m | back_m - fore_m, 5 decimals |
| dh_m | reduced setup height difference (H12), 5 decimals |

## run_summaries.tsv

- format: TSV
- rows: one row per run of the campaign in the run register, sorted by run_id

| field | content |
| --- | --- |
| run_id | run id |
| section_id | matched section, empty when not matched |
| direction | F or B, empty when not matched |
| start_mark | resolved start mark, empty when unresolved or not reached |
| end_mark | resolved end mark, empty when unresolved or not reached |
| run_date | run date (H8), empty for VOID and NO_SETUPS |
| setups | number of kept setups of the run |
| length_m | run length, 1 decimal, VALID runs only |
| dh_m | run height difference, 5 decimals, VALID runs only |
| test_id | effective two-peg test id when one was found |
| collimation_mm_per_100m | c of that test, 3 decimals |
| status | status of H9 |

## section_pairs.psv

- format: PSV
- rows: one row per ACTIVE section of the section register, sorted by section_id

| field | content |
| --- | --- |
| section_id | section id |
| from_mark | register from mark |
| to_mark | register to mark |
| line_id | line |
| class | effective line class (H14) |
| forward_run | selected forward run, ACCEPTED only |
| backward_run | selected backward run, ACCEPTED only |
| dh_forward_m | 5 decimals, ACCEPTED only |
| dh_backward_m | 5 decimals, ACCEPTED only |
| discrepancy_mm | 1000 x d, 2 decimals, ACCEPTED only |
| length_km | K, 5 decimals, ACCEPTED only |
| tolerance_mm | t x sqrt(K), 2 decimals, ACCEPTED only |
| candidates | number of candidate pairs |
| status | status of H14 |
| value_m | section value, 5 decimals, ACCEPTED only |

## benchmark_resolution.csv

- format: CSV
- rows: one row per distinct (context, token, resolve_date) that was resolved, sorted by context, token, resolve_date

| field | content |
| --- | --- |
| context | run, control, loop or epoch |
| token | the token as written |
| resolve_date | ISO date of the resolution |
| mark | resolved mark, empty when unresolved |
| hops | number of alias rows followed |
| status | RESOLVED or UNRESOLVED |

## control_points.json

- format: JSON
- rows: keys campaign, reference_date, table (C-2), controls

| field | content |
| --- | --- |
| controls | every profile control point in profile order |
| token | token as written in the profile |
| mark | resolved mark or an empty string |
| status | status of H16 |
| height_m | Table C-2 height after errata, 5 decimals; null for UNRESOLVED and NOT_IN_TABLE |

## adjustment_iterations.jsonl

- format: JSON Lines
- rows: one object per adjustment of every constrained component, in component then iteration order

| field | content |
| --- | --- |
| component | component name |
| iteration | 1, 2, ... |
| observations | observations in that adjustment |
| unknowns | unknown heights |
| redundancy | observations - unknowns |
| vtpv | 4 decimals |
| max_w | sqrt of the largest tested w^2, 2 decimals, null when nothing is testable |
| max_w_section | its section, null when nothing is testable |
| action | REMOVE, STOP_CLEAN, STOP_BUDGET or STOP_REDUNDANCY |

## adjusted_heights.csv

- format: CSV
- rows: one row per mark of every constrained component, sorted by mark

| field | content |
| --- | --- |
| mark | mark id |
| component | component name |
| height_m | 5 decimals |
| sigma_mm | sqrt(qxx), 2 decimals |
| status | FIXED or ADJUSTED |

## residuals.tsv

- format: TSV
- rows: one row per ACCEPTED section, sorted by section_id

| field | content |
| --- | --- |
| section_id | section |
| component | component name |
| v_mm | residual from the final adjustment, 2 decimals; empty for UNCONSTRAINED |
| qvv_mm2 | 4 decimals; empty for REMOVED and UNCONSTRAINED |
| w | v / sqrt(qvv), 2 decimals, USED only |
| status | USED, UNTESTABLE, REMOVED or UNCONSTRAINED |

## network_summary.json

- format: JSON
- rows: keys campaign, components (sorted by component name)

| field | content |
| --- | --- |
| component | name |
| marks | marks of the component |
| observations | observations of the final adjustment (all accepted sections when UNCONSTRAINED) |
| unknowns | unknowns of the final adjustment |
| redundancy | redundancy of the final adjustment |
| fixed | sorted FIXED marks |
| status | status of H17 |
| removed | removed sections in removal order |
| vtpv | 4 decimals |
| s0 | 3 decimals, null when r = 0 |
| chi2_lower | Table X-2 lower bound, 3 decimals, null when r = 0 |
| chi2_upper | Table X-2 upper bound, 3 decimals, null when r = 0 |
| global_test | PASS, FAIL, NO_REDUNDANCY or UNCONSTRAINED |
| UNCONSTRAINED components | unknowns, redundancy, vtpv, s0, chi2_lower and chi2_upper are null; fixed and removed are empty lists |

## loop_closures.xml

- format: XML
- rows: root element loops with attribute campaign, one loop element per register loop sorted by id

| field | content |
| --- | --- |
| id | loop id |
| class | loop class |
| marks | number of marks |
| misclosure_mm | 2 decimals |
| length_km | sum of K, 5 decimals |
| tolerance_mm | t x sqrt(K), 2 decimals |
| status | PASS, FAIL or INCOMPLETE; the three numbers are empty strings for INCOMPLETE |

## subsidence_rates.csv

- format: CSV
- rows: one row per mark with an adjusted height, sorted by mark

| field | content |
| --- | --- |
| mark | mark id |
| height_2024_m | prior height, 5 decimals; empty for CONTROL, DISTURBED and NEW |
| height_2026_m | reported height, 5 decimals |
| rate_mm_per_yr | 2 decimals for ALERT, SUBSIDING, UPLIFT, STABLE |
| sigma_rate_mm_per_yr | 2 decimals for the same classes |
| class | class of H20 |

## excluded_records.jsonl

- format: JSON Lines
- rows: sorted by kind, id, reason

| field | content |
| --- | --- |
| kind | setup, run or section |
| id | setup as run#seq, run id or section id |
| reason | VOID_SETUP for a dropped setup, the H9 status of a run that is not VALID, the H14 status of a section that is not ACCEPTED, SNOOPED for a section removed by data snooping |

## dedup_report.json

- format: JSON
- rows: one object with these keys in order

| field | content |
| --- | --- |
| records_read | records read from the read shards |
| setup_keys | distinct setups |
| superseded_revisions | records below the highest revision |
| duplicates | duplicates of H5 |
| conflicts | lost conflicts of H5 |
| void_setups | setups dropped by a void winner |
| kept_setups | setups kept |
| files_read | number of shards read |
| files_ignored | sorted names of the setup shards present but not read |

## source_lineage.json

- format: JSON
- rows: key files: the read shards in catalog precedence order, then the ignored setup shards sorted by name

| field | content |
| --- | --- |
| file | file name |
| status | READ, RETIRED (listed RETIRED in the catalog) or UNCATALOGUED |
| records | records read |
| kept | winning records kept |
| superseded | records below the highest revision |
| void_selected | void winners |
| duplicates | duplicate records |
| conflicts_lost | records that lost a conflict; an ignored shard reports zeros |

## rod_certificates_used.tsv

- format: TSV
- rows: one row per (rod, certificate) used by a reading of a VALID run, sorted by rod_serial then certificate

| field | content |
| --- | --- |
| rod_serial | serial |
| rod_type | type |
| graduation | Table A-1 graduation |
| certificate | certificate id |
| scale_ppm | 1 decimal |
| t0_c | 1 decimal |
| valid_from | ISO date |
| valid_to | ISO date |
| readings | back and fore readings using it |

## parameters_used.yaml

- format: YAML
- rows: flat key: value lines in this order

| field | content |
| --- | --- |
| campaign, reference_date, epoch_reference | profile values |
| rod_certificate_sheet, fallback_temp_c, met_max_gap_min | effective values after the overlay |
| refraction_coefficient, earth_radius_m, collimation_limit_mm_per_100m | Table I-1 and the quick reference card |
| critical_w, min_redundancy, max_removals, alert_rate_mm_per_yr, k_rate | Tables K-1 and R-1 |
| tolerance_section_<class>_mm, tolerance_loop_<class>_mm, sigma_<class>_mm_per_sqrt_km | for classes I, II, III in that order, after errata |
| graduation_<type>, alpha_<type>_ppm_per_c | for each rod type of Table A-1 in sorted order |

## variance_vs_published.csv

- format: CSV
- rows: one row per mark in the published heights or the adjusted heights, sorted by mark

| field | content |
| --- | --- |
| mark | mark id |
| published_m | published height, 5 decimals |
| recomputed_m | reported height, 5 decimals |
| diff_mm | recomputed - published, 2 decimals, when both exist |
| status | MATCH, DIFFERENT, MISSING_PUBLISHED or MISSING_RECOMPUTED |

## rate_vs_published.psv

- format: PSV
- rows: one row per mark in the published rates or subsidence_rates.csv, sorted by mark

| field | content |
| --- | --- |
| mark | mark id |
| published_rate | 2 decimals |
| recomputed_rate | 2 decimals |
| published_class | published class |
| recomputed_class | class of H20 |
| status | first of MISSING_PUBLISHED, MISSING_RECOMPUTED, CLASS_DIFFERS, RATE_DIFFERS, MATCH |

## dashboard_disagreements.csv

- format: CSV
- rows: one row per section whose dashboard status differs from its recomputed status, sorted by section_id

| field | content |
| --- | --- |
| section_id | section |
| dashboard_status | dashboard value |
| recomputed_status | the section_pairs status, or SNOOPED for a section removed by data snooping |

## cache_divergence.jsonl

- format: JSON Lines
- rows: sorted by mark then cache_token

| field | content |
| --- | --- |
| mark | mark the cache token resolves to at the reference date |
| cache_token | token as cached |
| cache_m | cached height |
| in_force_m | Table C-2 height after errata |
| diff_mm | cache - in force, 2 decimals; only VDH-2025 rows of marks with a different Table C-2 height |

## reconciliation.md

- format: Markdown
- rows: title line # <campaign> recomputation summary, then three sections

| field | content |
| --- | --- |
| ## Counts | a table with columns item and value and these rows in this order |
| runs_valid, runs_rejected | run_summaries.tsv rows with status VALID, and with any other status |
| sections_accepted, sections_not_accepted | section_pairs.psv rows with status ACCEPTED, and with any other status |
| components, components_unconstrained | network_summary.json components, and those with status UNCONSTRAINED |
| sections_snooped | sections removed by data snooping over all components |
| marks_adjusted | rows of adjusted_heights.csv, FIXED and ADJUSTED together |
| marks_alert, loops_failing | subsidence_rates.csv rows of class ALERT, and loop_closures.xml loops with status FAIL |
| ## Run pack settings | a table with columns setting, pack and used, one row for each of the twelve settings of the run pack settings block in its order |
| used values | control_table C-2, snooping_variance A_PRIORI, pair_selection MIN_DISCREPANCY, run_date_source FIRST_SETUP_INSTANT, rod_scale_applied_to EACH_READING, thermal_correction APPLIED; every other setting takes its governing value |
| ## Largest height differences | a table with columns mark, published_m, recomputed_m and diff_mm for the ten marks of largest absolute difference, ties to the smaller mark |

