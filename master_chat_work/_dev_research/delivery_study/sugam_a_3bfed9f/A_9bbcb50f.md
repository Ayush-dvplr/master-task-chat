# A_9bbcb50f: is the test loss genuine?

**Verdict: ARTEFACT** (version skew. The run was graded against an earlier bundle whose contract never stated the tariff epoch rule that the tariff checks grade. The folder now holds a later bundle with different tests, data and contract text.)

Scores: overall 67.69 / tests 58.46 (38/65) / rubric 76.92 (20/26). Genuine test points lost: **0 confirmed**. 3/65 (4.6 pts, `visible_data_quality_exact`) cause unresolved.

## Run health (clean)
- `result.json`: exception_info null. Agent ran 2026-10-22 14:50:38 -> 15:15:02Z (~24 min). 45 steps, final claim at step 44.
- All artifacts present. `artifacts_exist` (w1), `output_serialization_canonical`, `relocated_shuffled_copy_reproduced`, `default_paths_fallback`, `missing_feeds_handled` and `stale_outputs_fully_overwritten` PASS. No negative fired. No traceback, `Permission denied` or path problem. test-stdout prints only the reward.

## Version skew evidence
| item | graded run | current folder |
|---|---|---|
| checks / positive weight | 23 / 65 (reward-details.json) | 28 / 78 (`criteria.*(weight=)` in tests/test_output.py; reward.toml test weight 0.00641 = 0.5/78) |
| check names only in run | hidden_aggregates_exact, hidden_records_exact, missing_feeds_handled, output_serialization_canonical | n/a |
| check names only in current | n/a | hidden_bucket_reports_exact, hidden_record_{amounts,fields,tariffs}_exact, hidden_summary_exact, json_artifacts_sorted_with_newline, jsonl_lines_compact_and_ordered, missing_feeds_{data_quality,ledger}_exact |
| instruction | trajectory step 1 (similarity 0.965 to current) | current adds the sentence "The program writes only inside the output directory it is given ... replaces every artifact in full" |
| reconciliation.csv | step 4: TF-2001 west parts void, TF-1692 void, TF-WILD / TF-WILD-LATE west `*`, TF-HIGHER | TF-2011, TF-0876, TF-1690, TF-1749, TF-1801, TF-1797, TF-2035 |
| schema.md | step 3, 10703 chars | 11614 chars |
| git | n/a | one commit `461ab7c03` 2026-10-24 22:05 "Accept and mask ... cdr-tariff-epoch-rating-ledger", two days after the run |

**The rule the run was graded on, as it read in the graded contract.** Trajectory step 3 is the agent's `cat schema.md`. Its "## Tariff rating" section has only:
- the usable-row filter, ending "Every other row is ignored and counted in `tariff_rows_ignored`.", and
- straight after it: "A rated record carries the governing row's `tariff_id` and `tariff_usd_cents = amount_usd_cents * rate_bp / 10000` ... `ROUND_HALF_UP`".

The section never defines "governing", and says nothing on epoch grouping, revision ties, void groups or wildcard fallback. The current schema.md:104-116 adds all of these: "Usable rows are grouped by (`region`, `category`, `effective_from`) ... the one nearest the top of the file governs. A group whose governing row is `void` defines no epoch at all: it does not fall back to a lower revision, and the epoch that started before it stays in force ... When its category has no such epoch, the epochs for its region with category `*` are searched the same way."

The graded instruction (step 1) still promises the contract covers "how duplicate event ids and tariff revisions are settled". So, in the version the run saw, the epoch selection was a HIDDEN RULE (an IN-15 defect). It was fixed only after the run.

Agent's own rule, from out/transform.py:177-181 docstring: "a region's rows for the category and its `*` rows compete together, the latest `effective_from` wins, then the highest `revision`, then the greatest `tariff_id`". A governing void row means untariffed (:194). This is a defensible reading of the graded text, and it agrees with the graded reconciliation example (TF-2001 void -> 0).

## Failed checks (27 / 65)
| check | w | value/gate | cause |
|---|---|---|---|
| visible_record_tariffs_exact | 5 | wrong VALUE | epoch selection (unstated in graded contract) |
| visible_tariff_ledger_exact | 3 | wrong VALUE | same |
| hidden_tariff_ledger_exact | 5 | wrong VALUE | same |
| hidden_aggregates_exact | 5 | wrong VALUE | INFERRED tariff cascade: the current reference `_bucket` (tests :246-258) carries rated_count/tariff_usd_cents. The graded test code is not in the folder |
| visible_regions_exact | 3 | wrong VALUE | INFERRED tariff cascade (same) |
| visible_segments_exact | 3 | wrong VALUE | INFERRED tariff cascade (same) |
| visible_data_quality_exact | 3 | wrong VALUE | UNRESOLVED. hidden_data_quality_exact PASSED. Possibly a tariff counter on the visible data. The graded expected value is not available |

No gate: record fields/amounts, summary, product summary and hidden records (fields+amounts) all PASS. The losses are confined to the tariff dimension.

## Consequence for Step 2
No C card is written for this task (ARTEFACT). The graded tests are not in the folder, and the lever was a rule missing from the graded contract. GROUP_SUMMARY notes the current version's test design: embedded `_SHIPPED_DATA` zlib blobs; `_compute_expected` reference at test time; `_generate_corpus(root, seed, drop)` seeded generator at :393 with EVAL/MISSING_FEED/FALLBACK seeds; record checks split into fields/amounts/tariffs projections via `_MONEY_KEYS` :822; run as nobody.

Rubric losses: R4 (no cross-check of aggregates against records) and R6 (no two-output-directory determinism run) are both conduct criteria, both genuine.
