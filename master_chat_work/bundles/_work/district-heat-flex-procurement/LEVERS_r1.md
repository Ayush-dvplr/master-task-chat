# LEVERS - district-heat-flex-procurement

Round 0 table (bundle as built 19 Oct, 30 checks, positive 98): `LEVERS_r0.md`.

## Round 1 (21 Oct 2026): 41 checks, positive total 139, negative -16

Lever ids: old levers keep their registry ids LV-H01..LV-H05; new levers are LV-DH-1..LV-DH-5.
"Needs" lists every lever whose wrong reading the check's guard proves changes the observable;
the check is lost by a solver wrong on any one of them.

| # | Check | Needs | W | Observable read |
|---|---|---|---|---|
| 1 | artifact_set_exists_and_parses | none | 1 | 10 files in /app/out, 9 JSON objects |
| 2 | canonical_serialization_and_integer_units | none | 1 | bytes of the 9 shipped-data reports |
| 3 | report_keys_match_schema | none | 1 | key set at every object path of 8 reports |
| 4 | report_arrays_in_schema_order | none | 1 | array lengths and order in the shipped-data reports |
| 5 | ordinary_extract_portfolios_match | none | 5 | seeded extract: candidate count, selected ids, intervals |
| 6 | ordinary_extract_segment_files_match | none | 3 | seeded extract: both segment files |
| 7 | waiver_precedence_case | LV-H01 | 3 | label of S-WAIVE, both compliance count tables |
| 8 | tie_break_greatest_tuple_case | LV-H02 | 3 | selected ids |
| 9 | cap_after_uplift_case | LV-H03 | 3 | credit cents, cap_binding_count |
| 10 | residual_ties_descending_id_case | LV-H04 | 3 | grants, residual cents, residual-tie count |
| 11 | per_value_tick_quantisation_case | LV-H05 (H5t) | 3 | segment relief ticks |
| 12 | large_20_site_portfolio_case | LV-DH-1 | 5 | selected ids, 20 sites |
| 13 | large_20_site_interval_quantities_case | LV-DH-1 | 3 | intervals, 20 sites |
| 14 | large_22_site_portfolio_case | LV-DH-1 | 5 | selected ids, 22 sites |
| 15 | large_22_site_interval_quantities_case | LV-DH-1 | 3 | intervals, 22 sites |
| 16 | large_tie_count_case | LV-DH-1 | 5 | tie_decisions (count 4) |
| 17 | large_tie_greatest_tuple_shuffled_case | LV-DH-1, LV-H02 | 5 | selected ids, shuffled rows |
| 18 | tick_feasibility_case | LV-DH-2 | 5 | selected ids |
| 19 | tick_shortfall_order_case | LV-DH-2 | 5 | selected ids |
| 20 | tick_created_tie_case | LV-DH-2, LV-H02 | 5 | selected ids, tie_decisions |
| 21 | tick_floor_deficit_case | LV-DH-2 | 5 | selected ids |
| 22 | tick_recovery_ceiling_case | LV-DH-2 | 5 | selected ids |
| 23 | funded_pool_case | LV-DH-3 | 5 | funded, allocated, unallocated, grants (North, South) |
| 24 | funded_pool_after_capped_credit_case | LV-DH-3, LV-H03 | 5 | same fields |
| 25 | funded_pool_residual_tie_case | LV-DH-3, LV-H04 | 5 | same fields |
| 26 | funded_pool_after_site_rounding_case | LV-DH-3, LV-H05 (H5c) | 3 | same fields |
| 27 | ordinary_extract_summary_and_totals_match | LV-DH-3 | 3 | seeded extract: summary.json and 4 totals blocks |
| 28 | funded_pool_waived_weight_case | LV-DH-3, LV-DH-5 (none) | 5 | grant fields |
| 29 | held_waiver_weight_case | LV-DH-5, LV-H01 (order) | 5 | grant fields |
| 30 | cooldown_waiver_weight_case | LV-DH-5, LV-H01 (order) | 3 | grant fields |
| 31 | duplicate_profile_row_portfolio_case | LV-DH-4 | 5 | selected ids |
| 32 | duplicate_profile_row_count_case | LV-DH-4 | 3 | duplicate_profile_rows |
| 33 | out_of_range_interval_portfolio_case | LV-DH-4 | 5 | selected ids |
| 34 | out_of_range_interval_count_case | LV-DH-4 | 3 | out_of_range_profile_rows |
| 35 | unknown_region_site_row_count_case | LV-DH-4 | 3 | unknown, orphan offer, orphan profile counts |
| 36 | unknown_region_site_row_report_case | LV-DH-4 | 5 | site_count, site_labels |
| 37 | mixed_rejection_counts_case | LV-DH-4 | 3 | whole data_quality.json |
| 38-41 | four negatives (unchanged) | - | -5, -5, -3, -3 | as round 0 |

## Weight per lever (a check counts for every lever it needs)

| Lever | Family | Weight needing it | Share of 139 | Visible data (P3 diff) |
|---|---|---|---|---|
| none | - | 12 | 0.086 | - |
| LV-H01 waiver precedence | old | 3 + 5 + 3 = 11 | 0.079 | HIDDEN-ONLY |
| LV-H02 greatest tuple | old | 3 + 5 + 5 = 13 | 0.094 | HIDDEN-ONLY |
| LV-H03 cap after uplift | old | 3 + 5 = 8 | 0.058 | HIDDEN-ONLY |
| LV-H04 descending-id cents | old | 3 + 5 = 8 | 0.058 | DERIVABLE (funded pools tie in 1,054 shipped event-regions; no shipped value is graded) |
| LV-H05 quantise when derived | old | 3 + 3 = 6 | 0.043 | HIDDEN-ONLY |
| LV-DH-1 exact search at scale | D | 26 | 0.187 | HIDDEN-ONLY (shipped groups have at most 5 sites) |
| LV-DH-2 per-value ticks in the search | A | 25 | 0.180 | HIDDEN-ONLY |
| LV-DH-3 funded pool | B | 26 | 0.187 | DERIVABLE (counted through its compositions) |
| LV-DH-4 rejected rows | F | 27 | 0.194 | HIDDEN-ONLY |
| LV-DH-5 waived recipient weight | A | 13 | 0.094 | HIDDEN-ONLY |

Composition share (checks needing two or more levers right): checks 17, 20, 24, 25, 26, 28, 29,
30 = 38/139 = 0.273.
