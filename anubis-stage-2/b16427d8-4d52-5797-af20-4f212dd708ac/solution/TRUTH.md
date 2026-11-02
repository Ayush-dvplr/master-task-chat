# TRUTH.md - b16427d8-4d52-5797-af20-4f212dd708ac

## Defect

The R7 preference corpus arrives as fifty files that disagree about how the same facts are written. The rules and parameters are published in eight standing documents; the facts are scattered across the registers, the vendor partitions and eight non-authoritative copies. A reading that takes any one export at face value produces a release that looks plausible and reconciles against nothing.

- (focal) Annotator standing is decided by gold agreement against a per vendor floor. corpus_policy.md publishes a floor for each vendor, and the floors and the minimum gold item count change from corpus to corpus, so a builder must read them.
- (focal) A gold item retired at or before a verdict instant leaves that verdict out of the annotator's scorable denominator. The retirement and its instant live only in gold_answers_revised.csv, a non-authoritative copy that field_precedence.html names as the governing source for that one field.
- (focal) Position bias is estimated only over balanced comparisons (harness_events.log marks them). A biased annotator's verdicts stay admissible on balanced comparisons and become inadmissible only on unbalanced ones.
- (focal) Inadmissibility reasons are ordered; the first applicable reason is reported.
- (focal) A void in the errata register is lifted by a restore entry for the same verdict.
- (focal) An adjudication counts only when it post dates the last amendment to either completion, precedes the adjudication cutoff, and review_minutes.docx records it approved. A deferred or unrecorded adjudication falls through to majority.
- (focal) The majority tie-break is the larger summed confidence, then the alphabetically first choice; a majority of tie or both_bad is a resolution.
- (focal) The source mixture is capped by the epoch limit and the remainder redistributed over uncapped sources in proportion to their targets, repeating until no source exceeds its cap.
- (focal) The canonical member of a near duplicate cluster is the member with the earliest effective registration in dedup_clusters.tsv.
- (drift) Contamination has two thresholds: at or above the hard one the prompt is removed; at or above the soft one its family goes to validation first.
- (drift) Both_bad folds into tie for the agreement statistic only.
- (drift) The split is family wise: soft contaminated families first, then families in id order until the validation fraction is reached.
- (drift) Packing never splits a pair; a pair longer than the sequence length is dropped. Optimizer steps floor the sequence count against the global batch; the remainder is the dropped tail.
- (drift) A ratio with a zero denominator is null, so an insufficient comparison carries a null margin.
- (trap) Identifiers arrive case flipped, zero padding stripped, with one Cyrillic look-alike letter, with full-width digits, or wrapped in non-breaking and trailing spaces. All name the registered identifier.
- (trap) A separator followed by exactly three digits is a thousands group; a value with exactly two decimals carries excess precision that rounds half to even.
- (trap) A val column headed val_x1000 carries one thousand times the value, and header bands rename the columns and change mid file.
- (trap) Verdict instants in annotation_store.db can be workstation local time; the zone and clock offset come from workstation_inventory.ini and the zone table in source_conventions.md.
- (trap) Instants also arrive as epoch milliseconds and as spreadsheet serial days since 1899-12-30.
- (trap) Text cells can arrive upper-cased; locale codes resolve against the published mixed-case set.
- (trap) Non-authoritative copies carry -1 and N/A sentinels in their val column.
- (trap) The fixed width exports cut cells to 18 characters and never govern an instant.
- (trap) mixture_targets.xlsx writes each target as a percent.

## Load-bearing work

Twelve stages chain, each feeding the next: gold calibration, position bias, verdict admissibility, comparison resolution, inter annotator agreement, prompt eligibility with near duplicate canonicalisation and contamination screening, pair construction, the family wise split, capped mixture weighting, sequence packing, the step and shard schedule, and the release gates. Every stage reads published parameters, and every stage depends on decoding the exports correctly first.

## Verification

The deterministic channel holds 33 checks: 26 positive and 7 negative, with a positive weight total of 108 and a negative total of 25.

The visible tier grades the first stage (annotator standing), the dedup clusters and the source audit against the release, and grades every later stage on the agent's own upstream artifact recomputed with the published rules. An upstream artifact more than 5 percent away from the release does not unlock the stages that consume it. The hidden tier reruns the builder on a corpus generated from a different seed, with different published parameters, and compares all fifteen release artifacts exactly.

Negative checks, each firing only on the cheat itself: negative_hardcoded_sample_answers, negative_filename_dependent_behaviour, negative_reads_training_corpus_at_runtime, negative_nondeterministic_output, negative_modifies_input_corpus, negative_writes_outside_output_dir, negative_reads_outside_input_argument.

Speed is gated as the median of two builder runs against the median of three runs of a read-and-decode baseline over the same hidden corpus, at most 2.0 times.

The judged channel carries 10 criteria with 16 positive and 8 negative points.

tests/reward.toml divides each channel's weighted sum by its positive total and gives each channel half of the reward. With binary criteria the configured range is -0.366 to +1.000, with no clamp.

## Root cause

The corpus is adversarial but not lossy. Every graded parameter and rule is published in the standing documents, every identifier resolves through its registry, the printed numeric form is self describing at zero reporting places, and the zone and clock offset of every local instant come from the workstation register. Nothing graded depends on information absent from the inputs.

## Solution shape

Read the policy parameters, the convention register, the registry forms, the zone table and the precedence table first, because they decide how every later cell is read. Resolve identifiers to their registered form. Take each field from the source the precedence table names for it. Apply the errata (retire, opt out, void, restore) and the review board approvals before resolution. Then run the twelve stage chain in order, since each stage consumes the previous one.

## Ordered plan

1. Parse corpus_policy.md, source_conventions.md and field_precedence.html for parameters, registry forms, zone offsets and governing sources.
2. Build the prompt, completion, comparison, verdict, annotator, workstation and cluster registries, resolving every identifier to its registered form.
3. Convert every instant to UTC, using the workstation zone and clock offset for local instants.
4. Apply the errata register and the review board minutes.
5. Compute gold agreement per annotator over scorable gold only, and the A-side bias over balanced comparisons only.
6. Decide standing against the vendor floor and the minimum gold item count.
7. Test each verdict for admissibility in the published reason order.
8. Resolve each comparison by approved adjudication, else majority, else not at all.
9. Compute the agreement statistics with both_bad folded into tie.
10. Decide prompt eligibility in the published exclusion order.
11. Construct chosen and rejected pairs from comparisons resolved to left or right on eligible prompts.
12. Assign families to splits, cap the mixture, pack sequences, derive the schedule, then evaluate the release gates and the control totals.

## Pitfalls

Carrying the visible corpus's parameters instead of reading them. Taking a field from a non-authoritative copy that the precedence table does not name for it. Ignoring restore entries or review board approvals. Estimating position bias over all verdicts. Renormalising the mixture proportionally after capping instead of redistributing. Folding locale codes like other text. Reading a scaled column without checking its header band. Treating a sentinel as a real value. Writing zero where the contract asks for null. Rounding at an intermediate step rather than only at the reporting step.

## Provenance

```yaml
uuid: b16427d8-4d52-5797-af20-4f212dd708ac
instance_id: b16427d8-4d52-5797-af20-4f212dd708ac
task_name: terminal-bench/b16427d8-4d52-5797-af20-4f212dd708ac
fix_patch_sha256: 88da893f98cea7a846593257c9f1660fcba0765e06181d142c8eef33bfa35d16  # sha256 of solution/solve.sh
solve_py_sha256: d749558c1b9405698d2080585ba09e5baa502163c5e15114ab1ac53c87abccd6  # sha256 of solution/solve.py
language: python
```
