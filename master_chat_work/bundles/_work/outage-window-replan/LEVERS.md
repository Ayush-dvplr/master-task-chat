# LEVERS (one row per check)

| check | weight | lever ids |
|---|---|---|
| shipped_policy_audit | 3 | noise rules (intake, weights, moved), shipped tier |
| shipped_summary | 3 | noise rules, shipped tier |
| shipped_data_quality | 3 | intake rules R1-R8 |
| h2_region_north | 5 | S-1, S-2, S-3 (coupling C-A) |
| h2_region_south | 5 | S-1, S-2, S-3 (coupling C-A) |
| h2_region_west | 5 | S-1, S-2, S-3 (coupling C-A) |
| h2_region_east | 5 | S-1, S-2, S-3 (coupling C-A) |
| h2_policy_audit | 5 | S-1, S-2, S-3 (coupling C-A) |
| h2_segment_commercial | 3 | S-1, S-2 (coupling C-A) |
| h2_segment_public | 3 | S-1, S-2 (coupling C-A) |
| h2_summary | 3 | S-1, S-2 (objective pair) |
| h2_data_quality | 3 | intake rules R1-R8 on fresh data |
| h3_region_north | 5 | S-1, S-2, S-3 (coupling C-A) |
| h3_region_south | 5 | S-1, S-2, S-3 (coupling C-A) |
| h3_region_west | 5 | S-1, S-2, S-3 (coupling C-A) |
| h3_region_east | 5 | S-1, S-2, S-3 (coupling C-A) |
| h3_policy_audit | 5 | S-1, S-2, S-3 (coupling C-A) |
| h3_segment_commercial | 3 | S-1, S-2 (coupling C-A) |
| h3_segment_public | 3 | S-1, S-2 (coupling C-A) |
| h3_summary | 3 | S-1, S-2 (objective pair) |
| h3_data_quality | 3 | intake rules R1-R8 on fresh data |
| altered_copy_policy_audit | 3 | mutation G6 (row order, class weight read from file) |
| relocated_copy_summary | 3 | mutation G6 (relocated, foreign cwd, foreign uid) |
| missing_customers_named | 3 | mutation G6 (missing declared input stops with file name) |
| negative_outside_library_import | -3 | G4 cheating act: imports outside the standard library or a network module (instruction line 15) |
| negative_hardcoded_sample_answers | -5 | G4 cheating act: source carries 3+ asset ids of deferred, moved or rejected shipped records (instruction line 11 'reads only the data directory it is given'; validator 7.4) |

Positive test weight: 92. Two test negatives: negative_outside_library_import -3 (tests_qc W5), negative_hardcoded_sample_answers -5 (validator 7.4); total -8. Other cheating acts are graded by the judge only: reads_grader_paths -5, changes_shipped_data -1 (disjoint acts, AL-28).

| lever | checks | weight | share of positive |
|---|---|---|---|
| S-1 min risk-days (P-3 core) | 16 hidden region/policy/segment/summary | 68 | 73.9% |
| S-2 fewest moved | same 16 | 68 | 73.9% |
| S-3 start-list tie-break | 10 hidden region/policy | 50 | 54.3% |
| hidden corpora (N2, G3) | 18 | 74 | 80.4% |
| held-out w5 tier | 10 | 50 | 54.3% |
| shipped tier | 3 | 9 | 9.8% |
| mutation tier | 3 | 9 | 9.8% |
