# LEVERS: hangar-check-replan (harden_r1, 2 Nov 2026)

Lever ids: **W** Word table markup (harden_r1 primary, family 4a L2 held-out, route1 R0.1 kind a): data_conventions.md:20-23 says the two Word files are WordprocessingML packages as ECMA-376 defines them, tables read from the main part, found by header row. ECMA-376 Part 1 CT_Tbl content is `tr | customXml | sdt`, so a table row may sit inside a row-level content control (Word repeating section) or a row-level customXml element; Part 3 markup compatibility keeps exactly one of `mc:Choice` / `mc:Fallback`. **W-sdt**, **W-cxml**, **W-alt** are the three forms. **L1** settlement (S1 order, S2 used/credit/left, S3 report only), **R1** shared pool, **R2** moved + tie vector, **R3** deferral reasons, **U** fixed universe, **X1** duplicate counts read rows, **N** notice overrides. Older levers stay registered at lower weight; a1 beat all of them.

| check | weight | levers | tier |
|---|---|---|---|
| program_runs_on_shipped_data, program_stops_on_a_missing_input | 1 + 1 | none | shipped |
| shipped_plan_rows / shipped_data_quality / shipped_group_reports / shipped_settlement | 3 + 1 + 3 + 3 | R1 R2 R3 N / X1 / R1 R2 / L1 | shipped |
| h1..h6 plan_rows | 6 x 3 = 18 | R1 R2 R3 N; X1 on h3 h5 | hidden |
| h1..h6 plan_group_totals | 6 x 1 = 6 | R1 R2 | hidden |
| h1..h6 settlement_per_check, _by_base_and_segment, _summary | 18 x 1 = 18 | L1 | hidden |
| h1, h2 base_and_segment_with_no_requests | 2 x 1 = 2 | U | hidden |
| h1_data_quality | 3 | X1 | hidden |
| changed_allowance_grants (m1), revised_availability_removed (m2) | 3 + 3 | L1 / N | mutation |
| h7 (sdt), h8 (cxml), h9 (alt) allowance table: settlement_per_check, _by_base_and_segment, _summary | 9 x 5 = 45 | W + L1 (grants, overtime_policy.md:14-24) | hidden lever |
| h10 (sdt), h11 (cxml), h12 (alt) closure table: plan_rows, plan_group_totals, settlement_per_check, settlement_summary | 12 x 5 = 60 | W + N closures (data_conventions.md:54-55) | hidden lever |
| h13 (sdt), h14 (cxml), h15 (alt) availability table: same four checks | 12 x 5 = 60 | W + N availability (data_conventions.md:51-53) | hidden lever |
| negative_hardcoded_sample_answers / negative_reads_check_files / negative_writes_outside_out_dir | -5 / -5 / -3 | cheating acts | negative |

## Totals
- Positive 230 over 77 tests (74 positive, 3 negative). Old checks 65, W lever checks 165 = **71.7%** (route1 R0.1 bar 40%).
- a1 program (paid run 1): every old check EXACT (65), every W check WRONG (0 of 165) -> tests 65/230 = 28.3% (score0, Docker).
- Only the allowance, closure and availability tables carry a form: those are the tables whose rows are optional data. Item and class tables stay plain (a row missed there is a crash, not a WRONG output, Law 1).
- Tests > 44: stated in OUT/DESIGN.md.
