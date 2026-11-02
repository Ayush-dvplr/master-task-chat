Aurelis Labs is closing release R7 of its post-training preference corpus, the human preference data that trains the preference model and drives the alignment run for `aurelis-r7-chat`. Four annotation vendors ran for one quarter and their exports disagree. Everything you need is under `/app/data`. Start with `/app/data/corpus_policy.md`, which publishes the release parameters and the release rules in the order they apply, and `/app/data/source_conventions.md`, which says how each source writes identifiers, numbers and instants. `/app/data/field_precedence.html` names the source that governs each field, and the errata register, the review board minutes, the metric definitions and the methodology appendix are part of the same contract. Sources conflict in places.

Deliver the builder at `/app/out/build.py`. It must run as a script:

```bash
python3 /app/out/build.py <DATA_DIR> <OUT_DIR>
```

Run it on `/app/data` writing to `/app/out`. The platform reruns this builder on every release and on corpora it has not seen, so it must be fast as well as exact: on a given corpus its median runtime must stay within twice the median time that a plain read-and-decode pass over the same exports takes with the standard decoders in the image.

## Deliverables

1. `/app/out/build.py` - the reusable builder.
2. `/app/out/annotator_standing.json` - per annotator gold calibration and standing.
3. `/app/out/verdict_admissibility.jsonl` - per verdict admissibility and reason.
4. `/app/out/comparison_resolution.jsonl` - per comparison resolved verdict, route and margin.
5. `/app/out/agreement.json` - agreement statistics overall, per vendor and per domain.
6. `/app/out/prompt_eligibility.jsonl` - per prompt eligibility and exclusion reason.
7. `/app/out/dedup_clusters.json` - near duplicate clusters and their canonical member.
8. `/app/out/preference_pairs.jsonl` - the released chosen and rejected pairs.
9. `/app/out/split_assignment.json` - family to split assignment and counts.
10. `/app/out/mixture_plan.json` - per source allocation after the epoch cap.
11. `/app/out/packing_plan.json` - sequence packing totals.
12. `/app/out/training_schedule.json` - steps, warmup, shards and accumulation.
13. `/app/out/slice_coverage.json` - per slice pair and token counts.
14. `/app/out/source_audit.json` - per export record counts.
15. `/app/out/control_reconciliation.json` - corpus totals.
16. `/app/out/release_gates.json` - the release gate decisions.

## Contract

17. Every ratio is a JSON number quantised to six decimal places, half to even, at the reporting step and at no earlier step.
18. Counts are JSON integers, never strings and never floats.
19. Booleans are JSON booleans.
20. A value that does not exist, including a ratio whose denominator is zero, is JSON null, never zero and never an empty string.
21. Identifiers are written in their registered form, as `source_conventions.md` lists it.
22. `annotator_standing.json` is an object keyed by annotator id, each value carrying `vendor`, `gold_items`, `gold_hits`, `gold_agreement`, `balanced_verdicts`, `a_side_bias`, `biased` and `standing`. `standing` is the string `admitted` or `gated`.
23. `verdict_admissibility.jsonl` carries one object per registered verdict with `verdict_id`, `comparison`, `annotator`, `admissible` and `reason`. `reason` is null when the verdict is admissible, otherwise the first applicable code in this order: `annotator_gated`, `outside_window`, `freeze_window`, `stale_amendment`, `unbalanced_biased`, `voided`.
24. `comparison_resolution.jsonl` carries one object per registered comparison with `comparison_id`, `resolved`, `route`, `votes` and `margin`. `route` is `adjudicated`, `majority` or `insufficient`. `resolved` is `left`, `right`, `tie` or `both_bad`, and is null, like `margin`, when the comparison does not resolve.
25. `agreement.json` carries `overall`, `by_vendor` and `by_domain`, each value giving `observed_agreement`, `kappa`, `rated_units` and `rater_pairs`. `by_vendor` is keyed by vendor name and `by_domain` by domain name.
26. `prompt_eligibility.jsonl` carries one object per registered prompt with `prompt_id`, `eligible`, `reason`, `cluster`, `family` and `source`. `reason` is null when the prompt is eligible, otherwise the first applicable code in this order: `retired`, `opted_out`, `contaminated`, `duplicate`, `over_length`, `no_resolved_pair`. `cluster` is null for a prompt in no cluster.
27. `dedup_clusters.json` is keyed by cluster id, each value giving `canonical`, `members`, `dropped` and `canonical_effective_at`. `members` and `dropped` are sorted ascending, and `canonical_effective_at` is an ISO 8601 UTC instant such as `2025-07-04T16:22:03Z`.
28. `preference_pairs.jsonl` carries one object per released pair with `pair_id`, `comparison`, `prompt`, `family`, `source`, `chosen`, `rejected`, `margin`, `route` and `tokens`. `pair_id` is `PP-` followed by the digits of the comparison id, so `CMR-001234` yields `PP-001234`.
29. `split_assignment.json` carries `families` (family id to `train` or `validation`), `family_counts`, `pair_counts` and `validation_share`; both count objects are keyed by `train` and `validation`.
30. `mixture_plan.json` is keyed by source name with `available_pairs`, `target_weight`, `allocated_pairs`, `effective_weight`, `epochs` and `capped`, plus a `_total` entry carrying `budget_pairs` and `allocated_pairs`.
31. `packing_plan.json` carries `sequence_length`, `packed_pairs`, `dropped_pairs`, `sequences`, `token_capacity`, `tokens_used`, `padding_tokens` and `packing_efficiency`.
32. `training_schedule.json` carries `sequences`, `global_batch`, `micro_batch`, `gradient_accumulation`, `optimizer_steps`, `warmup_steps`, `shards`, `shard_sequences` and `dropped_tail_sequences`.
33. `slice_coverage.json` is keyed by slice with `pairs`, `train`, `validation` and `tokens`. Slice keys are written as `slice_definitions.yaml` writes them, `<dimension>-<value>` over the dimensions `domain`, `difficulty`, `risk`, `locale` and `source`, for example `domain-finance` and `locale-de_DE`; only slices holding at least one pair appear.
34. `source_audit.json` is keyed by file name, naming every file in the data directory exactly once, documents included, with `rows`: the number of records the file carries in the record layout `source_conventions.md` describes (columns `rid`, `par`, `val`, `at`, `fa`, `fb` or their renamed forms), header lines excluded. A file with no records has 0.
35. `control_reconciliation.json` carries `prompts`, `completions`, `comparisons`, `verdicts`, `admissible`, `resolved`, `eligible` and `pairs`, where `resolved` counts comparisons whose `resolved` is not null.
36. `release_gates.json` carries `gates`, `undersized_slices`, `train_contamination_rate` and `total_pairs`. `gates` holds the booleans `min_slice_pairs_met`, `no_family_straddles_split`, `train_contamination_within_limit`, `kappa_above_floor`, `packing_efficiency_reported` and `release_approved`, and `undersized_slices` is sorted ascending.
37. Every JSONL artifact is sorted ascending by its own identifier field, holds no duplicate identifier, and ends with a newline.
38. Every JSON artifact is written with sorted keys and ends with a newline.
39. All artifacts are UTF-8 with LF line endings.
40. The `prompts`, `completions`, `comparisons` and `verdicts` totals in `control_reconciliation.json` must agree with the figures published in `/app/data/control_totals.html`.
41. The pair count in `release_gates.json` must equal the number of rows in `preference_pairs.jsonl`.
42. Every family named in `split_assignment.json` must appear in exactly one split.

## Rules of engagement

43. Use only the Python standard library and the packages already installed in the image.
44. This machine has no internet access; do not attempt to reach it.
45. Read only `<DATA_DIR>`, and never modify anything inside it.
46. Write only inside `<OUT_DIR>`; create nothing anywhere else, temporary files included.
47. The builder must be deterministic: two runs on identical input produce byte identical artifacts.
48. The builder must take its input and output locations from its arguments, and must not depend on the name of the directory it is given.
49. Values are compared exactly, at the documented precision, keys, types and ordering.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
