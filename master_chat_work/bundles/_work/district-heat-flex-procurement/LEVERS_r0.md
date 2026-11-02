# LEVERS - district-heat-flex-procurement (round 0, bundle as built 19 Oct)

Source: `tests/test_output.py` registrations (identical to `_work/test_output.src.py` apart from
the `_SHIPPED_DATA` block, checked 21 Oct 12:20 IST). DESIGN.md section 8 weights are stale; the
weights below are the registered ones. "none" = the check is designed to agree under every lazy
reading (visible data is inert to H1..H5; the ordinary extract is accepted only when
`expected(folder) == expected(folder, ALL_LAZY)`).

| # | Check | Lever | W | Observable read |
|---|---|---|---|---|
| 1 | artifact_set_exists_and_parses | none | 1 | 10 files exist under /app/out, 9 JSON parse as objects |
| 2 | canonical_serialization_and_integer_units | none | 1 | bytes of 9 JSON files: sorted keys, trailing newline, no float/bool |
| 3 | region_north_selected_offers_match | none | 5 | region_North events[]: candidate_offer_count, selected_offer_ids |
| 4 | region_south_selected_offers_match | none | 5 | same, South |
| 5 | region_west_selected_offers_match | none | 5 | same, West |
| 6 | region_east_selected_offers_match | none | 5 | same, East |
| 7 | region_interval_quantities_match | none | 5 | events[].intervals in 4 region files |
| 8 | procurement_cost_and_credit_totals_match | none | 5 | events[].bid_cost_cents, credit_cents and totals block, 4 files |
| 9 | region_grant_allocations_match | none | 3 | events[] pool, allocated, unallocated, grants |
| 10 | segment_commercial_attribution_match | none | 3 | whole segment_commercial.json |
| 11 | segment_public_attribution_match | none | 3 | whole segment_public.json |
| 12 | summary_rollups_match | none | 3 | whole summary.json |
| 13 | data_quality_counts_match | none | 3 | whole data_quality.json |
| 14 | policy_audit_labels_match | none | 3 | whole policy_audit.json + events[].compliance_counts |
| 15 | hidden_ordinary_extract_portfolios_match | none | 5 | rerun on seeded extract: candidate count, selected ids, intervals |
| 16 | hidden_ordinary_extract_settlement_match | none | 3 | rerun on seeded extract: bid cost, credit, grant fields |
| 17 | waiver_precedence_case | H1 | 5 | case `waiver`: label of S-WAIVE |
| 18 | safety_hold_over_waiver_case | H1 (flag H1order) | 3 | case `waiver_ranked`: 7 labels |
| 19 | tie_break_greatest_tuple_case | H2 | 5 | case `tie`: North events[0].selected_offer_ids |
| 20 | tie_break_reversed_input_case | H2 | 3 | case `tie_reversed`: same field, rows reversed |
| 21 | cap_after_uplift_case | H3 | 5 | case `cap`: North events[0].credit_cents |
| 22 | cap_with_base_above_cap_case | H3 | 3 | case `cap_low`: same field |
| 23 | residual_ties_descending_id_case | H4 | 5 | case `residual`: North events[0].grants |
| 24 | residual_ties_mixed_weights_case | H4 | 3 | case `residual_mixed`: same field |
| 25 | per_value_tick_quantisation_case | H5 (flag H5t) | 5 | case `ticks`: North events[0].intervals[0].relief_ticks |
| 26 | per_site_credit_rounding_case | H5 (flag H5c) | 3 | case `site_cents`: North events[0].credit_cents |
| 27 | negative_hardcoded_sample_answers | neg | -5 | summary.json of the ordinary rerun equals the shipped one |
| 28 | negative_reads_tests_or_reward_files | neg | -5 | program source tokens |
| 29 | negative_external_dependency_or_network | neg | -3 | program imports (ast) |
| 30 | negative_missing_substantive_sections | neg | -3 | summary.json top-level keys |

## Weight per lever

| Lever | Registry id | Checks | Weight | Share of 98 |
|---|---|---|---|---|
| none (visible) | - | 1..14 | 50 | 0.510 |
| none (hidden ordinary) | - | 15, 16 | 8 | 0.082 |
| H1 waiver precedence | LV-H01 | 17, 18 | 8 | 0.082 |
| H2 greatest tuple tie | LV-H02 | 19, 20 | 8 | 0.082 |
| H3 cap after uplift | LV-H03 | 21, 22 | 8 | 0.082 |
| H4 descending-id residual | LV-H04 | 23, 24 | 8 | 0.082 |
| H5 quantise when derived | LV-H05 | 25, 26 | 8 | 0.082 |
| negatives | - | 27..30 | -16 | - |

Lever-neutral weight 58/98 = 0.592, which is exactly the measured all-lazy score. Composition
share (checks needing two or more levers right at once): 0/98.

Underivability (P3 mechanical, 21 Oct): `reference(visible)` vs `reference(visible, {flag})` for
H1, H1order, H2, H3, H4, H5t, H5c and ALL_LAZY: identical on all 9 reports. Every lever is
HIDDEN-ONLY; the leak is not from the data.
