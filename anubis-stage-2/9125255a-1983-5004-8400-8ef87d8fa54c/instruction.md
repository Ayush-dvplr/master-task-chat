# Heron Q3 2025 evaluation certification close

The evaluation office has to certify the Q3 2025 scorecard of seven Heron candidate models against the production baseline. Everything the office has is under `/app/data`: runner logs, result exports from several stores, registries, a calendar, a mailbox, review sheets, and the written certification policy, source conventions, metric definitions and methodology. The sources overlap and contradict each other. The shipped documents define which source is authoritative, how amendments, seals, voids and conventions apply, what is in scope and which source wins a conflict, and those written rules decide every value. Some shipped values are wrong, stale or superseded on purpose, so a value is never right just because it is newer, more complete or labelled final.

Write a reusable program that produces the certified close, run it on `/app/data`, and leave the program and its outputs in `/app/out`. The program will also be run on another quarter's corpus built the same way (same file names and conventions, different contents), so it has to apply the rules rather than repeat this quarter's numbers. It may use the Python 3.12 standard library and the preinstalled pyarrow, PyYAML, openpyxl, python-docx and pypdf packages, has to work offline, and should finish within 20 minutes on a corpus of this size.

## Deliverables

- `/app/out/certify.py`: the program.
- `/app/out/lineage.json`: the certified checkpoint of each model alias.
- `/app/out/job_dispositions.jsonl`: the disposition of every registered evaluation job.
- `/app/out/item_eligibility.jsonl`: the eligibility of every registered item.
- `/app/out/item_scores.jsonl`: the certified per-item results of the candidates.
- `/app/out/benchmark_metrics.json`: suite metrics per model.
- `/app/out/calibration.json`: calibration of the multiple-choice suite.
- `/app/out/pairwise.json`: preference judgments against the baseline.
- `/app/out/significance.json`: paired significance against the baseline.
- `/app/out/leaderboard.csv`: normalised suite scores and the ranking.
- `/app/out/release_gates.json`: the release decision of each candidate.
- `/app/out/slice_metrics.json`: slice accuracies.
- `/app/out/source_audit.json`: an account of the result records in each result source.
- `/app/out/control_reconciliation.json`: totals to reconcile with the published control figures.

Conventions for every output: UTF-8, LF line endings and a trailing newline. Rates, scores and metrics are JSON numbers computed from exact values and rounded once, at the end, to 6 decimals with round half to even, unless an item says otherwise. Counts are JSON integers, flags are JSON booleans, and a value that does not apply is null. Model aliases, suite keys (arith, code, intent, safety, mcq, pref, longctx, multiling), job ids, item ids, checkpoint ids, host names and tickets are written in the canonical forms the policy defines. Values are compared exactly, including types, keys and row sets.

## The program

1. Leave the program at `/app/out/certify.py` and, next to it in `/app/out`, the thirteen outputs it writes for `/app/data`; every output must exist and parse in the format described here.
2. `python3 /app/out/certify.py <data_dir> <out_dir>` reads its input only from `<data_dir>`, never from a fixed location such as `/app/data`.
3. It writes the thirteen outputs into `<out_dir>`, creating it if needed, and writes nothing anywhere else.
4. It must not create, change or delete anything inside `<data_dir>`.
5. Two runs on the same input produce byte-identical outputs.
6. The outputs do not depend on the name or path of the input directory.
7. Everything is derived from the corpus the program is given; it carries no answers from this quarter.
8. On another corpus built the same way, its `lineage.json` follows the same rules.
9. On that corpus its `job_dispositions.jsonl` follows the same rules.
10. On that corpus its `item_eligibility.jsonl` follows the same rules.
11. On that corpus its `item_scores.jsonl` follows the same rules.
12. On that corpus its `leaderboard.csv` follows the same rules.
13. On that corpus its `release_gates.json` follows the same rules.

## Lineage and jobs

14. `lineage.json` is an object keyed by model alias, covering the seven candidates and the baseline; `checkpoint` is the full canonical id of the checkpoint the alias is certified on at the close.
15. `effective_from` is the UTC instant, written YYYY-MM-DDTHH:MM:SSZ, at which that certification took effect, and `approval_ref` is the change ticket that made it effective.
16. `voided_promotions` is the number of the alias's tag events that never took effect.
17. `job_dispositions.jsonl` has one object per registered job with the keys `job_id`, `model`, `benchmark`, `shard`, `checkpoint`, `host`, `submitted_at` and `disposition`, where `disposition` is one of voided, staging_host, stale_checkpoint, outside_window, maintenance, superseded, rerun_denied or authoritative.
18. `submitted_at` is the job's true submission instant in UTC, written YYYY-MM-DDTHH:MM:SSZ.
19. `model`, `benchmark`, `checkpoint` and `host` are canonical, and `shard` is the 0-based shard index as an integer.

## Items

20. `item_eligibility.jsonl` has one object per registered item with `item_id`, `benchmark`, `eligible` (boolean) and `reason`.
21. `reason` is null for an eligible item and otherwise the first applicable of retired, duplicate, contaminated or out_of_scope.
22. `item_scores.jsonl` has one object per candidate and eligible item with `model`, `item_id`, `benchmark`, `value`, `confidence` and `correct`; `confidence` is null outside mcq. For arith, `value` is the certified answer as a string with exactly two decimals, or null for an abstention, and `correct` is 1 or 0 under the item's tolerance.
23. For code, `value` is the integer number of the job's ten samples that pass every test, and `correct` is null.
24. For intent, `value` is the resolved class in taxonomy v2 names and `correct` is 1 or 0.
25. For safety, `value` is the certified score and `correct` is null.
26. For mcq, `value` is the certified option letter and `correct` is 1 or 0.
27. For mcq, `confidence` is the certified confidence.
28. For pref, `value` is win, tie or loss for the candidate and `correct` is null.
29. For longctx, `value` is the answer normalised as the metric definitions describe and `correct` is 1 or 0.
30. For multiling, `value` is the answer normalised under the profile that applies to the job and `correct` is 1 or 0.
31. The three JSONL files are sorted by `job_id`, by `item_id`, and by `model` then `item_id` respectively, with one object per line and no duplicate keys.

## Metrics

32. `benchmark_metrics.json` is keyed by model (candidates and baseline) and then by suite (every suite except pref); every suite object holds `n`, the number of eligible items, and arith, mcq and longctx hold `accuracy`.
33. code holds `pass@1`, `pass@5` and `n`.
34. intent holds `macro_f1` and `n`.
35. safety holds `auroc` and `n`.
36. multiling holds `macro_accuracy`, `n` and `languages`, the number of languages in the average.
37. `calibration.json` is keyed by candidate; `ece` is its expected calibration error on mcq.
38. `bins` lists the ten bins in order, each with `count`, `mean_confidence` and `accuracy` (null for an empty bin).
39. `pairwise.json` is keyed by candidate with integer `wins`, `ties`, `losses` and the `win_rate`.
40. `significance.json` is keyed by candidate and then by gated suite (arith, mcq, longctx, multiling); `b` and `c` are the integer discordant counts.
41. `p_value` is the test's p value and `decision` is improved, regressed or no_change.
42. `leaderboard.csv` has one row per model, candidates and baseline; `aggregate` and the eight suite columns hold the normalised scores.
43. Rows are ordered by `rank`, starting at 1, as the methodology orders them.
44. The header is exactly `rank,model,aggregate,arith,code,intent,safety,mcq,pref,longctx,multiling`; every number after `model` is written with exactly 6 decimals.
45. `release_gates.json` is keyed by candidate with the booleans `aggregate_vs_baseline`, `no_regression`, `ece_within_cap`, `safety_floor` and `release`.
46. `slice_metrics.json` is keyed by candidate, then gated suite, then slice name, with the slice accuracy or null.

## Reconciliation

47. `source_audit.json` has one entry per source file whose records are model outputs for a job and an item, including staged, replicated and rescored exports but not review sheets or the baseline reference; `result_rows` counts every record line in the file, including verbatim repeats and records that end up void or superseded, but not reversal lines, flush lines or ledger rows.
48. `used` counts the records that supply at least one certified field of a scored item, and `discarded` is `result_rows` minus `used`.
49. `control_reconciliation.json` is keyed by candidate plus `_total`, each with `authoritative_jobs`, `scored_items` and `expected_results`, the sum of the published expected result counts of those jobs.

## How to work

50. Treat the certification policy and the source conventions as the authority, and read them before deciding how to resolve conflicting rows.
51. Before you finish, compare your reconstruction with the control figures the sources publish.
52. When the data contradicts a rule you assumed, drop the rule and find the documented one.
53. Where two sources disagree, resolve the conflict with the documented precedence rather than a blanket choice of one source.
54. Some exports are only partly authoritative; use them only for the part the policy says remains valid.
55. Keep `certify.py` maintainable: named functions for parsing, rule resolution and metrics, and explicit error handling.
56. In your final message, say which outputs, if any, you could not reconcile with the published control figures.
57. Work only from `/app/data` and this brief; do not look for or open any other task material.
58. Leave every file under `/app/data` as it is; do not edit, move or delete anything there.
59. If a command fails, change something before running it again.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
