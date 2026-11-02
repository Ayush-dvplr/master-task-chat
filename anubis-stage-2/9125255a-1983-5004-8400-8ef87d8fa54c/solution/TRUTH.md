# TRUTH.md - 9125255a-1983-5004-8400-8ef87d8fa54c

## Defect

The Q3 2025 scorecard cannot be read off any single export. Fifty files under `/app/data` describe the same jobs, items and results; forty-two are authoritative for some part of the close and eight are partial or stale copies. Every value in the thirteen outputs is decided by the written rules in `certification_policy.md`, `source_conventions.md`, `metric_definitions.pdf`, `methodology_appendix.pdf`, `field_precedence.html`, `errata_register.docx` and `review_minutes.docx`, and a solver has to apply them in a reusable program that is run again on another quarter.

- (focal) Lineage and job disposition. An alias is certified on the checkpoint named by its latest tag event in `model_tags.yaml` that took effect, meaning an approval mail in `evalops_notifications.mbox` carries its change ticket and the event is not voided. EMA checkpoints exist only in `checkpoint_lineage_snapshot.json` and inherit family, tokenizer and context window from their `ema_of` parent. Each registered job then gets the first matching disposition, in this order: voided (errata register job void), staging_host (host in fleet `s` for that ISO week in `host_inventory.ini`), stale_checkpoint, outside_window (true UTC submission outside 2025-07-01 to 2025-10-01, after the host clock offset for that week), maintenance (inside a host window in `maintenance_windows.ics` with no exemption in the review minutes), superseded (an approved rerun replaces it), rerun_denied, otherwise authoritative.
- (focal) Result reconciliation. Only rows from production sources routed to the job in `source_conventions.md` count. RESTORE jobs read the staging snapshot instead. Each row also has to pass these filters: not voided by row id in its own file, not reversed, not a sentinel or shadow row, on the right shard per the shard map in `metric_definitions.pdf` (Appendix S), emitted no later than the job's seal, and the newest per (source, job, item, sample). When primary and copy both carry a key, `field_precedence.html` picks the winner per suite and field, the bridge class flips that winner, and final reviews in `manual_overrides.xlsx` replace judge verdicts (judge rows only). Per-host locale, scale and timezone conventions, confusable characters, NFKC normalisation and legacy LC codes have to be undone before any comparison.
- (focal) Metrics and gates. Items are ineligible, first reason wins, if retired, a non-canonical dedup member, contaminated (a counted hit at or above the suite threshold, excluded shards ignored) or held out. Gold values are corrected only by upheld grader errata, reached through the dispute ticket map. Metrics are computed in exact arithmetic and rounded once, half to even. pass@k uses the unbiased estimator over ten samples. AUROC counts ties as one half. ECE uses ten equal-count bins sorted by confidence then item id. McNemar is exact two-sided at the policy alpha. Normalisation is chance-corrected, and the leaderboard weights come from the board-adopted column.
- (drift) Each file mixes conventions inside itself: repeated and reordered headers, zero-padded or upper-cased ids, spreadsheet serial dates, comma decimals from the Munich desk, percentages for safety on some hosts, and Latin-1 rows inside UTF-8 files. A parser that handles only the first convention it sees fails on later bands of the same file.
- (trap) The eight partial exports (`eval_store_mirror.db`, `scores_staging.parquet`, `judge_verdicts_rescored.jsonl`, `checkpoint_lineage_snapshot.json`, `run_registry_export.xml`, `locale_codes_legacy.tsv`, `gold_labels_corrected.csv`, `scorecard_prelim.xlsx`) look newer, more complete or more final than the files they copy. Where the policy names a part that remains valid, only that part counts, for example EMA registrations in the snapshot, RESTORE jobs in the staging snapshot, slot presentation order in the rescored export, deprecated language codes, the dispute ticket map and the adopted suite weights. For every other fact these files are wrong on purpose, and the mirror never supplies a certified value.

## Load-bearing work

- `/app/out/certify.py`
- `/app/out/lineage.json`
- `/app/out/job_dispositions.jsonl`
- `/app/out/item_eligibility.jsonl`
- `/app/out/item_scores.jsonl`
- `/app/out/benchmark_metrics.json`
- `/app/out/calibration.json`
- `/app/out/pairwise.json`
- `/app/out/significance.json`
- `/app/out/leaderboard.csv`
- `/app/out/release_gates.json`
- `/app/out/slice_metrics.json`
- `/app/out/source_audit.json`
- `/app/out/control_reconciliation.json`

## Verification

Positive total 184.

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_modifies_input_corpus` (weight -3)
- `negative_writes_outside_output_dir` (weight -1)

The visible tier compares the thirteen files in `/app/out` with the certified close of the shipped corpus. The hidden tier runs `/app/out/certify.py` up to three times on a second corpus from the same family, twice on one copy and once on a copy under a renamed directory, stopping after the first run that fails; every leftover process of a run is killed before the next one starts. It checks lineage, dispositions, eligibility, item scores, leaderboard and gates on that corpus, byte identity between runs, that no input changed and that nothing was written outside the output directory. A different corpus sits at `/app/data` during the hidden runs, so a program that ignores its arguments is caught. Comparison is exact, including JSON types and row sets.

## Root cause

The scorecard is hard because no one source is authoritative for everything. Authority is assigned per fact by written rules spread across prose, tables in PDF and Word documents, HTML tables and spreadsheet sheets. Those rules interact: dispositions depend on lineage, host weeks, clock offsets, maintenance windows and minutes; item scores depend on dispositions, routing, precedence, seals, voids and reviews; metrics depend on eligibility and corrected gold.

**Red lines.** No value may be copied from this quarter into the program. Reading `/app/data` from inside `certify.py` instead of the argument directory, writing outside the output directory, or touching the inputs all cost reward.

## Solution shape

1. A document layer that reads markdown, HTML, docx (zip and XML), xlsx (shared strings and sheets), the text-stream PDFs and the policy prose, and extracts every threshold, alias table, confusable table and precedence rule from them.
2. Canonicalisers for each id family (job, item, host, checkpoint, ticket, row id, legacy code) that apply NFKC, the confusable table, case, padding and prefix rules.
3. A registry layer for errata, hosts and clock offsets, maintenance, lineage, mail approvals, tags, jobs, events and minutes that yields the certified lineage and one disposition per job.
4. An item layer for registry, gold and errata, scoring parameters, manifest, dedup, contamination, scope, tokens, slices, locales and weights that yields eligibility and corrected gold.
5. Result parsers for every result source, then a single reconciliation pass that applies routing, voids, reversals, seals, shard checks, latest-row selection, field precedence, bridge flips and reviews.
6. A metric layer working in `Fraction` and `Decimal` with one final half-to-even rounding.

## Ordered plan

1. Read the policy, conventions, metric definitions and methodology first and list every rule with the file it governs.
2. Build the canonicalisers and the errata void index, since every later step looks rows up through them.
3. Resolve lineage from tag events, approvals and the snapshot EMA entries; then compute host weeks, true submission times and dispositions.
4. Resolve item eligibility and corrected gold.
5. Parse each result source with its own conventions, reconcile, and write `item_scores.jsonl`.
6. Compute metrics, calibration, pairwise, significance, leaderboard, gates and slices.
7. Write the source audit and control reconciliation, and compare them with `control_totals.html` before finishing. On this corpus the totals are 8120 authoritative jobs, 53515 scored items and 115500 expected results.
8. Run the program twice and under a renamed input directory to confirm byte identity and argument handling.

## Pitfalls

- Treating the newest or most complete export as the truth; the eight partial exports are built to reward that mistake.
- Applying a host's clock offset from the wrong ISO week, or using the week of the local timestamp rather than the UTC one.
- Using an erratum that was withdrawn, filed after the close, or not upheld, or mapping tickets to items without the dispute map.
- Letting a review replace a rerun verdict, or forgetting that the presentation order of a preference pair comes only from the rescored export.
- Counting reversal, flush or ledger lines in `result_rows`, or counting rows of ineligible items as used.
- Rounding intermediate values, or comparing floats where the definitions call for exact counts.
- Reading `/app/data` directly inside `certify.py`.

## Provenance

```yaml
uuid: 9125255a-1983-5004-8400-8ef87d8fa54c
instance_id: 9125255a-1983-5004-8400-8ef87d8fa54c
task_name: terminal-bench/9125255a-1983-5004-8400-8ef87d8fa54c
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: f05d25e2a296e36023aed288c884aa45093a2c6b9d73dc5d22608e15944d2ad7  # informational; solve.py is 2038 lines
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured. The expected figures are exactly 1.000 on each of five
  oracle runs and exactly 0.000 on a no-op run, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 46 positive checks worth 184 weight and 6
  negative checks worth -22 weight, so on its own it ranges -22/184 = -0.120
  to +1.000. The judged channel carries 11 criteria worth 17 positive and
  12 negative points, so on its own it ranges -12/17 = -0.706 to +1.000.
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  0.5 * (-0.120) + 0.5 * (-0.706) = -0.413 to +1.000 with no clamp.
```
