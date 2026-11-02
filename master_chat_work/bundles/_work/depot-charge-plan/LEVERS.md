# LEVERS.md: one row per check

Levers: M meter convention (rules.md:27), F shared feeder + cabinet limits (rules.md:22-23), T lexicographic order + tie-break (rules.md:33), C coupling sentence (rules.md:34). P = plain stated rules only (no lever). NEG = cheating act.

| check | weight | lever ids |
|---|---|---|
| program_and_reports_present | 1 | existence |
| shipped_policy_audit_exact | 3 | M (East shift), F (shipped derating binds since fix v2) |
| shipped_summary_exact | 3 | M (East shift), F (shipped derating binds since fix v2) |
| shipped_data_quality_exact | 3 | P (rules 3-4, 13, 21; two-condition rows since fix v2) |
| shipped_segment_public_exact | 3 | M (East shift), F (shipped derating binds since fix v2) |
| shipped_region_east_exact | 3 | M (East shift), F (shipped derating binds since fix v2) |
| fresh_h1_policy_audit_exact | 5 | M,F,T,C |
| fresh_h1_region_north_exact | 5 | M,F,T,C |
| fresh_h1_region_south_exact | 5 | M,F,T,C |
| fresh_h1_region_west_exact | 5 | M,F,T,C |
| fresh_h1_region_east_exact | 5 | M,F,T,C |
| fresh_h1_segment_commercial_exact | 5 | M,F,T,C |
| fresh_h1_segment_public_exact | 5 | M,F,T,C |
| fresh_h1_summary_exact | 5 | M,F,T,C |
| fresh_h1_data_quality_exact | 3 | P (rules 3-4, 13, 21) |
| fresh_h2_policy_audit_exact | 5 | M,F,T,C |
| fresh_h2_region_north_exact | 5 | M,F,T,C |
| fresh_h2_region_south_exact | 5 | M,F,T,C |
| fresh_h2_region_west_exact | 5 | M,F,T,C |
| fresh_h2_region_east_exact | 5 | M,F,T,C |
| fresh_h2_segment_commercial_exact | 5 | M,F,T,C |
| fresh_h2_segment_public_exact | 5 | M,F,T,C |
| fresh_h2_summary_exact | 5 | M,F,T,C |
| fresh_h3_policy_audit_exact | 5 | M,F,T,C |
| fresh_h3_region_north_exact | 5 | M,F,T,C |
| fresh_h3_region_south_exact | 5 | M,F,T,C |
| fresh_h3_region_west_exact | 5 | M,F,T,C |
| fresh_h3_region_east_exact | 5 | M,F,T,C |
| fresh_h3_segment_commercial_exact | 5 | M,F,T,C |
| fresh_h3_segment_public_exact | 5 | M,F,T,C |
| fresh_h3_summary_exact | 5 | M,F,T,C |
| fresh_h3_data_quality_exact | 3 | P (rules 3-4, 13, 21) |
| fresh_h4_policy_audit_exact | 5 | M,F,T,C |
| fresh_h4_region_north_exact | 5 | M,F,T,C |
| fresh_h4_region_south_exact | 5 | M,F,T,C |
| fresh_h4_region_west_exact | 5 | M,F,T,C |
| fresh_h4_region_east_exact | 5 | M,F,T,C |
| fresh_h4_segment_commercial_exact | 5 | M,F,T,C |
| fresh_h4_segment_public_exact | 5 | M,F,T,C |
| fresh_h4_summary_exact | 5 | M,F,T,C |
| reordered_copy_policy_audit_exact | 3 | M,F,T,C (mutation G6) |
| relocated_fresh_summary_exact | 3 | M,F,T,C (own seed 47713, graded nowhere else; fix v2 TS-26) |
| default_paths_run_summary_exact | 3 | M,F,T,C (own seed 55109, flagless run; fix v2 AL-2) |
| missing_settlements_stops_naming_file | 3 | P (rule 22) |
| malformed_tariff_stops_naming_file | 3 | P (rule 22, unreadable file; fix v2 JD-5) |
| outside_library_or_network_import | -3 | NEG |
| hardcoded_shipped_answers | -5 | NEG |
| negative_run_writes_outside_output_folder | -1 | NEG (instruction L9 write scope; fix v2 AL-2; a negative because it grades an absence, TS-25) |

Positive weight 197 (fix v2: +3 default paths, +3 malformed input; relocated keeps 3; write scope is a -1 negative).
Hidden held-out lever tier (fresh w5 160 + reordered 3 + relocated 3 + default paths 3) = 169 of 197 = 85.8% of positive test weight.
Since fix v2 the shipped derating binds, so the F lever also costs the 12 lever-marked shipped points; measured per program in OUT/FIX_REPORT.md (lever accounting).

Before fix v2 (positive 191):
Positive weight 191. Per lever weight total (each lever alone fails every one of these checks, measured in COST_TABLE.md):
- M: 166 (86.9% of positive test weight)
- F: 166 (86.9% of positive test weight)
- T: 166 (86.9% of positive test weight)
- Held-out w5 tier: 160 (83.8%)

## Harden r3 (board c5b188a, 1 Nov): lever U, raised feeder limit (rule 11 "replaced by")
- U: on held-out folders u1..u9 the disruption notice lists one feeder derating block whose limit is above `feeder_kwh_per_slot`; rule 11 (docs/charging_rules.md:23) replaces the grid.ini value by the listed limit, so the feeder may carry more than the base value in those slots. A program that takes min(base, listed) (the paid a1 program, derive_report.py:519-523) caps those slots at the base and every plan document differs.
- Generator: WORK/gen_core.py `uplift(seed, out)` (embedded tests/test_output.py:421); render() untouched. Checks tests/test_output.py:4087-4445 (defs), :4526-4597 (registrations); each folder its own memo `_uplifted` (:3517) and `_check_uplift` (:3773); seeds `_UPLIFT` (:45).

| checks | weight each | count | lever |
|---|---|---|---|
| fresh_u<i>_policy_audit_exact, i = 1..9 | 5 | 9 | U,M,F,T,C |
| fresh_u<i>_region_{north,south,west,east}_exact | 5 | 36 | U,M,F,T,C |
| fresh_u<i>_segment_{commercial,public}_exact | 5 | 18 | U,M,F,T,C |
| fresh_u<i>_summary_exact | 5 | 9 | U,M,F,T,C |

data_quality.json is not graded on u-folders (the uplift adds no rejected rows; it would repay fresh_h1/h3_data_quality_exact, TS-26).
Positive weight 557 (120 checks: 117 positive, 3 negatives -3, -5, -1). Lever U tier 360 of 557 = 64.6%; held-out tier 169 + 360 = 529 of 557 = 95.0%.
