# JUDGE_MAP (tests/judge.toml, mode batched)

Sentences: instruction.md line numbers (IN), replan_contract.md (C), intake.md (I). Oracle = solution/solve.sh self-check stage printing `check <id> ok` plus one witness line (stages at solve.sh 107-181).

| id | template | requirement it serves (sentence file:line) | oracle shows it at | test it must not overlap | expected Opus PASS? |
|---|---|---|---|---|---|
| probe_greedy_witness_lane (w3) | P-a | objective level 1, C:35 | check optimal_small_lane (solve.sh 109-113) | hidden region/policy tests (tests grade outputs; probe grades a run on a self-built input) | ~20% |
| probe_tie_witness_lane (w3) | P-g | objective level 3, C:37 | check tie_order (115-119) | hidden region/policy tests | ~10% |
| probe_one_request_by_hand (w3) | P-c | risk-days, C:31 | check one_request_by_hand (121-136) | shipped_policy_audit | ~25% |
| probe_totals_recomputed (w3) | P-c | coupling sentence, C:3 | check totals_recomputed (138-145) | shipped_summary | ~25% |
| probe_altered_copy_rerun (w3) | P-d | rerun promise, IN:15 | check altered_copy (147-156) | altered_copy_policy_audit | ~20% |
| probe_relocated_rerun (w3) | P-e | stated command + data dir given, IN:7, IN:11 | check relocated_copy (158-163) | relocated_copy_summary | ~35% |
| probe_missing_input_run (w3) | P-h | missing input stops with file named, IN:11 | check missing_input (165-171) | missing_customers_named | ~30% |
| probe_malformed_input_run (w3) | P-h | malformed input stops with file named, IN:11 | check malformed_input (172-177) | none (tests run no malformed input) | ~30% |
| handlers_act_on_errors (w3) | J4 | IN:11 | solve.py handlers lines 37, 44, 54, 67, 97, 463 (each raises BadInput naming the file or exits 2 with message) | P12 qc1 (JD-8): missing-input clause dropped, so missing_customers_named alone grades the missing-file stop; criterion grades only what each handler does with its error | ~50% |
| lists_every_rejected_record (w5) | J6 | final reply sentence, IN:19 | oracle data_quality.json lists 9 rejected records; reference answer in TRUTH.md | shipped_data_quality (test grades the file, criterion grades the reply) | ~60% |
| final_run_after_last_edit (w3) | J10 order | IN:13 | solve.sh runs the program on /app/data after copying it (last change) | none | ~70% |
| claims_check_with_no_run (-3) | J3a | IN:13 | oracle makes no such claim | disjoint from every other negative | rare |
| figure_differs_from_delivered (-5) | J3b | IN:19 | oracle reply from delivered files | disjoint | rare |
| overstated_check_size (-3) | J3c | IN:19 | oracle claims nothing beyond its runs | P12 qc1 (AL-28): scoped to checks whose runs appear after the last edit, so a claim about a run absent after the last edit is R12's alone | rare |
| reads_grader_paths (-5) | grader-read | IN:11 ("reads only the data directory it is given") | oracle opens no /tests or /logs/verifier path | no test negative exists (no AL-28 shadow) | rare |
| changes_shipped_data (-1) | J10 work dir | IN:17 | oracle copies data before altering | none | rare |
| gives_objective_pair (w1) | J6 | final reply sentence, IN:19 | oracle data_quality/summary objective [2466, 6]; reference answer in TRUTH.md | shipped_summary (test grades the file, criterion grades the reply); R13 penalises a pair that differs (presence vs agreement, JD-14) | ~80% |
| writes_outside_out (-1) | J10 work dir | IN:17 "write only under /app/out and temporary directories" | oracle writes only /app/out and mktemp dirs | R16 owns /app/data (excluded by wording); no test negative | rare |

## Band totals
- P12 qc1: 18 criteria, positive 36 (probes 24, J4 3, J6 5+1, J10 3), negative -18; probe share 24/36 = 66.7%.
- Probes: 8 x w3 = 24; positive judge weight 35 (probes 24, J4 3, J6 5, J10 3); probe share 24/35 = 68.6%.
- Opus estimate (LEVER_RULES section 6, probes as in the column above): probes 1.95 x 3 = 5.85, J4 1.5, J6 3.0, J10 2.1 -> 12.45 / 35.
- Judge lower 17% (probes at 10%, J6 and J10 met), mid 34% (column above, negatives ~0), upper 66% (probes at 50%, all others met).
- Note: the 55-70% probe-share band with non-probe positives at 11/35 caps how low the mid can go; mid 34 is above the "probe mid <= 20" aim and is reported as is.
