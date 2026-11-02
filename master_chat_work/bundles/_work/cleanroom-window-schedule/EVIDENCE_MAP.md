# EVIDENCE_MAP

Every graded rule of this task has its own sentence in `environment/data/contract.md`; no rule is left for the agent to infer from data. The rows below map each lever rule and each master point 4 definition to the sentence that states it, the checks that grade it and the wrong readings the sentence rules out.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| maximum net plan per accepted night | *_plans_optimal, *_summary_matches, *_policy_audit_matches, *_regions_match, *_segments_match, relocated_reordered_reruns_match | environment/data/contract.md:89 | value-density greedy; greedy plus single-swap local search; flow relaxation |
| every reported figure from the maximum-net-value plan | shipped_*, dense_/carry_/wide_book_* except data_quality | environment/data/contract.md:97 | figures from a feasible but suboptimal plan |
| nights run in audit.toml date order | carry_book_*, shipped_summary_matches | environment/data/contract.md:42 | nights in id order or file order |
| previous family = latest-starting earlier job on the bay that night | dense_/carry_/wide_book_plans_legal, *_plans_optimal | environment/data/contract.md:70 | changeover only between touching jobs |
| first job of a night uses the family held at night start | carry_book_*, shipped_summary_matches | environment/data/contract.md:71 | reset to initial_family every night |
| bay that has run no job holds initial_family | *_plans_optimal, shipped_summary_matches | environment/data/contract.md:68 | no charge for a bay's first changeover |
| rejected night leaves every bay's family as it was | carry_book_*, wide_book_* | environment/data/contract.md:55 | rejected night resets bays |
| changeover needs crew window [start - crew_minutes, start) | *_plans_legal, *_plans_optimal | environment/data/contract.md:77 | crew ignored; bay treated as free once its job ends |
| single crew: two crew windows never share a minute | *_plans_legal, *_plans_optimal, *_policy_audit_matches | environment/data/contract.md:79 | per-bay planning; lane-by-lane planning |
| stated time limit per night | dense_book_*, wide_book_* | environment/data/contract.md:19 | exact search over raw end times with no state merging |

## Lessons for the master

- When every rule has a sentence the map is a pointer table, not evidence of an inferred rule | no change: keeps the precheck file:line format.
