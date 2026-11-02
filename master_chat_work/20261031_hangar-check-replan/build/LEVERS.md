# LEVERS: hangar-check-replan

Lever ids: **L1 settlement** (S1 payment order class/due/id fleet-wide; S2 used not granted, credit subtracted, left = granted minus used; S3 report only). **R1** shared pool, **R2** moved third term + tie vector, **R3** deferral reasons (plan exactness, carried by every hidden check through the coupling sentence). **U** fixed universe (empty base and segment). **X1** duplicate counts read rows only. **N** notice overrides (revised availability, notice closures). Non-lever: plain program run, shipped checks.

| check | weight | levers | tier |
|---|---|---|---|
| program_runs_on_shipped_data | 1 | none | shipped |
| shipped_plan_rows_and_rejections | 3 | R1 R2 R3 N (shipped degenerate) | shipped |
| shipped_group_reports | 3 | R1 R2 | shipped |
| shipped_settlement | 3 | L1 (slack: never binds) | shipped |
| h1..h6 _plan_fields (6 checks) | 6 x 3 = 18 | R1 R2 R3 N; X1 on h3 h5; U on h1 h2 | hidden |
| h1..h6 _settlement_per_check (6) | 6 x 5 = 30 | L1 (S1 S2) + plan coupling | hidden |
| h1..h6 _settlement_by_base_and_segment (6) | 6 x 5 = 30 | L1 (S2 fleet-wide, per-base sums) | hidden |
| h1..h6 _settlement_summary (6) | 6 x 5 = 30 | L1 (S2 granted/used/left) | hidden |
| h1, h2 _base_and_segment_with_no_requests | 2 x 1 = 2 | U | hidden |
| h1_data_quality | 3 | X1-free screening, Q1 | hidden |
| changed_allowance_grants (m1) | 3 | L1 (mutation, plain hidden exact) | mutation |
| revised_availability_removed (m2) | 3 | N (mutation) | mutation |
| negative_hardcoded_sample_answers | -5 | cheating act | negative |
| negative_reads_check_files | -5 | cheating act | negative |

## Totals

- Positive 129: shipped 10 (7.8%), hidden 113 (87.6%), mutation 6 (4.7%).
- Settlement lever L1 (hidden settlement 90 + m1 3) = 93 of 129 = **72%**; with held-out w5 checks 90/129 = 70%.
- Plan levers (hidden plan 18 + m2 3) = 21 (16%); U 2 (1.6%); data quality 3 (2.3%).
- Lever share (all hidden + mutation) = 119/129 = 92%.
- Checks 35 (33 positive, 2 negative); A3 warning band is above 35: at the edge, none printed (record in BUILD_REPORT).
