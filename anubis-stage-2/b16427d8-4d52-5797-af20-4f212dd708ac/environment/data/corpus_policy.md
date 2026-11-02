# Preference corpus release policy R7

This policy governs release R7 of the post-training preference corpus. The rules below apply in the order they are written. Where sources disagree, field_precedence.html names the source that governs each field.
## Release parameters

| parameter | value |
|---|---|
| collection_window_start | 2025-07-01T00:00:00Z |
| collection_window_end | 2025-10-01T00:00:00Z |
| adjudication_cutoff | 2025-10-03T18:00:00Z |
| gold_min_items | 13 |
| gold_floor.calder | 0.76 |
| gold_floor.northwind | 0.72 |
| gold_floor.orbit | 0.69 |
| gold_floor.tessel | 0.72 |
| bias_limit | 0.12 |
| min_votes | 2 |
| max_prompt_tokens | 768 |
| max_pair_tokens | 1600 |
| contamination_hard | 95 |
| contamination_soft | 80 |
| validation_fraction | 0.14 |
| epoch_cap | 2 |
| sequence_length | 1536 |
| global_batch | 16 |
| micro_batch | 4 |
| warmup_fraction | 0.03 |
| shard_sequences | 128 |
| min_slice_pairs | 40 |
| max_train_contamination_rate | 0.02 |
| min_kappa | 0.40 |

The collection window includes its start instant and excludes its end instant. The adjudication cutoff is exclusive.
## Annotator standing

A verdict counts toward its annotator's gold calibration when its comparison has a gold answer in gold_set.tsv, unless that gold item was retired at or before the verdict instant. gold_items is the number of such verdicts and gold_hits the number whose chosen side (left or right) names the gold completion; tie and both_bad never hit.

An annotator is admitted when gold_items is at least gold_min_items and gold_agreement reaches the floor published above for the annotator's vendor; otherwise the annotator is gated. An annotator is biased when the absolute A-side bias exceeds bias_limit.
## Verdict admissibility

Every registered verdict is tested against these reasons in this order and reports the first that applies: annotator_gated (its annotator is gated); outside_window (its instant is outside the collection window); freeze_window (its workstation was frozen at that instant, a freeze covering its start instant up to but excluding its end); stale_amendment (its instant is at or before the latest amendment of either completion in the comparison); unbalanced_biased (its annotator is biased and the comparison is not balanced); voided (the errata register voids it and no restore entry names it). A verdict with no applicable reason is admissible.
## Comparison resolution

An adjudication is valid when its instant is after the latest amendment of either completion, before the adjudication cutoff, and the review board minutes record it approved. A comparison with a valid adjudication resolves to the adjudicated choice on route adjudicated with margin 1.

Otherwise a comparison with fewer admissible verdicts than min_votes does not resolve: route insufficient, resolved null, margin null. Otherwise it resolves on route majority to the choice (left, right, tie or both_bad) with the most admissible verdicts. Equal counts are settled by the larger summed confidence, then by the alphabetically first choice. Its margin is the winning count minus the largest count among the other choices, divided by the number of admissible verdicts. A majority of tie or both_bad is a resolution. votes is always the number of admissible verdicts.
## Prompt eligibility

Every registered prompt is tested against these reasons in this order and reports the first that applies: retired and opted_out (from the errata register); contaminated (its highest screened similarity is at least contamination_hard); duplicate (it belongs to a near duplicate cluster and is not the cluster's canonical member, which is the member with the earliest effective registration, ties going to the lowest prompt id); over_length (its tokens exceed max_prompt_tokens); no_resolved_pair (none of its comparisons resolved to left or right). A prompt with no applicable reason is eligible.
## Preference pairs

Every comparison resolved to left or right whose prompt is eligible yields a pair: chosen is the completion on the resolved side and rejected the other. tokens is the prompt's tokens plus both completions' tokens; a pair whose tokens exceed max_pair_tokens is not released. margin and route are the comparison's.
## Split

Splits are assigned per prompt family over the families that have released pairs. A prompt is soft contaminated when its highest screened similarity is at least contamination_soft and below contamination_hard. Every family holding a soft contaminated prompt goes to validation first. The remaining families, in ascending family id, go to validation while the validation pair count is below validation_fraction times the total released pairs, and to train after that.
## Mixture, packing and schedule

The mixture runs over train pairs only, with the targets in mixture_targets.xlsx and the capping procedure in methodology_appendix.pdf. Packing takes train pairs in ascending pair id: a pair longer than sequence_length is dropped; otherwise it joins the current sequence when it fits and starts a new sequence when it does not. Optimizer steps are the sequence count divided by global_batch, rounded down; the remainder is the dropped tail. Warmup steps are warmup_fraction times the optimizer steps, rounded to the nearest integer with halves to even. Shards are the sequence count divided by shard_sequences, rounded up.
## Release gates

min_slice_pairs_met holds when no slice has fewer than min_slice_pairs pairs; no_family_straddles_split holds when every family's pairs sit in one split; train_contamination_within_limit holds when train pairs on soft or hard contaminated prompts, divided by all released pairs, is at most max_train_contamination_rate; kappa_above_floor holds when the reported overall kappa is at least min_kappa; packing_efficiency_reported holds when packing produced at least one sequence. release_approved holds when all five hold.
