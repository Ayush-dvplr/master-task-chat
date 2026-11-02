# RULE_COVERAGE (G11), hangar-check-replan

Mutants are `solution/solve.py` with one reading changed (`WORK/wrong/make_wrong.py`), scored in Docker with the built tests (logs `_runs/20261101/hangar-check-replan/wrong2-20261101T1215/logs/wrong.log` and `wrong3-*`). Doc paths are under `environment/data/docs/`. Tests failed counts positive checks only; negatives stayed silent on every mutant.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| allowance payment order: class, then due_date, then request_id | overtime_policy.md:16-19 | s_unordered (request_id order) | 16: h2-h6 settlement x3, changed_allowance_grants |
| same, due_date key | overtime_policy.md:17-18 | s_start_key (start day key) | 10: h3, h4, h6 settlement x3, h5_settlement_per_check |
| one fleet allowance, whichever base | overtime_policy.md:14-15, 19 | s_per_base_cap | 19: h1-h6 settlement x3, changed_allowance_grants |
| each check takes the smaller of its shifts and what is left | overtime_policy.md:19 | s_whole_only | 16: h2-h6 settlement x3, changed_allowance_grants |
| settled = overtime_cost - allowance_credit | overtime_policy.md:21-24 | s_cap_not_subtracted | 21: shipped_settlement, h1-h6 settlement x3, both mutation checks |
| allowance_used is the sum of allowance_shifts (used, not granted) | output_schema.md:45; overtime_policy.md:21-24 | s_granted_not_used | 17: shipped_settlement, h1-h6 group and summary settlement, h1/h2 empty axis, both mutation checks |
| one fleet overtime pool | overtime_policy.md:9-10 | p_pool_per_base | 31: every positive check but program_runs and h1_data_quality |
| moved counts a start other than published_start; published start may be kept | planning_policy.md:30-31 | p_earliest_only | 13 |
| tie: start-day list then finish-day list | planning_policy.md:36-38 | p_first_found_tie | 12: h1, h2, h6 plan + settlement |
| any open request may be deferred; reason by empty-line test | deferral_policy.md:3-9 | p_defer_no_slot_only | 21 |
| notice availability wins over the csv value | data_conventions.md:51-53 | p_no_revised | 27 (shipped plan and reports too) |
| every base and segment always has a report and a summary row | output_schema.md:5-8 | u_from_records | 11: h1, h2 plan + settlement, empty axis checks, h1_data_quality |
| duplicate_request counts only earlier read rows | data_conventions.md:31-36 | x_ids_from_ignored | 6: h3 x4, h5 plan + per check |
| rejected row line is its csv line number, header line 1 | data_conventions.md:45-46 | q_line_from_one | 2: shipped_plan_rows_and_rejections, h1_data_quality |

Not counted as covered: the clip of an available day before `season_start` to day 1 (data_conventions.md:51-53). Mutant `c_no_clip` scored 129/129: a line is free from day 1 and a check can only start on a season day, so an earlier available day gives the same plan. The sentence stays in the docs as a plain statement; no check claims it.
