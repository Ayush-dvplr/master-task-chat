# Scoring Reconstruction

Audit b118b8c. Source bundles were read only; no task, verifier, Docker image or harness was executed. Paths beginning with a task UUID are relative to `/Users/mac/Desktop/Terminal Bench/anubis-stage-2/`. `HARNESS` below means the local, read-only reference checkout `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/`; its source explains the observed files but does not prove the deployed harness revision.

## Clean Example First

The first scoring example was `69de664a-afeb-5ad4-9453-b5fb0b108cd6` (GLM). Its `tests/reward.toml:3` says `aggregation = "weighted-sum"`; line 4 gives `test_output = 0.0025380710659898475` and `judge = 0.004424778761061947`. These equal `0.5 / 197` and `0.5 / 113`. Its `trajectories/glm-5.3/run_1/verifier/reward-details.json:$.reward.components[0].detail.score` is `42.0` (judge), and component `[1].detail.score` is `197.0` (tests).

Let `T` and `J` be earned signed test and judge weights, and `T+` and `J+` the sums of positive weights. A satisfied positive criterion earns its weight. A triggered negative criterion subtracts its weight; an untriggered negative criterion earns zero, not an extra positive reward. The current bundles normalize each channel to half the combined reward:

```
test_percent   = round(100 * T / T+, 2)
rubric_percent = round(100 * J / J+, 2)
summary_combined = round((test_percent + rubric_percent) / 2, 2)
raw_combined = round(T * reward_weight_test + J * reward_weight_judge, 4)
rescaled_reward = round(100 * raw_combined, 4)
```

The reporting implementation prefers the recorded CTRF weighted percentage for tests (`HARNESS/scripts/judge_trajectory.py:674`, function `compute_test_percentage`; lines 677-678 return the rounded `weighted_percentage`). Rubric normalization uses positive passed weights plus negative weights whose `passed` flag is false, divided by positive total (`HARNESS/scripts/judge_trajectory.py:684`, function `compute_rubric_percentage`; lines 690-694). Negative rubric `passed = true` means the prohibited behavior was **not** observed: the conversion explicitly inverts `satisfied` for negative weights (`HARNESS/scripts/judge_trajectory.py:652`, function `rubric_from_verdicts`; lines 662-664).

`69de.../trajectories/glm-5.3/run_1/verifier/score.json:$.test_weights_percentage = 100.0`, `$.rubric_weights_percentage = 37.17`, and `$.final_reward = 68.59`. The calculation is `(100.00 + 37.17) / 2`, rounded to `68.59`. Its `verifier/reward_raw.json:$.reward = 0.6858`, while `verifier/reward.json:$.reward = 68.58`. This is the expected separate rounding path, **not** a 100-fold error or a meaningful disagreement. The `pass_summary.json:$.average_combined_score = 68.59` uses the reporting path.

## File Relationships And Rounding

- `reward-details.json:$.reward.score`, `reward_raw.json:$.reward`, and `result.json:$.verifier_result.rewards.reward` are the 0-1-scale raw reward in these records. The compact `reward.json` and, when present, `reward.txt` are subsequently rescaled percentage rewards. The reference rescaler multiplies by 100 and rounds to four decimals (`HARNESS/scripts/rescale_rewards.py:63`, function `rescale_reward`), backs up the raw JSON, writes percentage text and replaces numeric JSON rewards (lines 98-111). This is postprocessing, not a second agent attempt.
- `score.json` and `report.json` calculate the final percentage from the separately rounded channel percentages (`HARNESS/scripts/judge_trajectory.py:863` through line 865: `final_reward = round((test_pct + rubric_pct) / 2.0, 2)`). `generate_pass_summary.py:85` through line 87 repeats that calculation for each run; lines 98-108 average the per-run values. All audited summaries contain one run (`main_facts.json:$[task][model].summary.per_run`, one element for each of the 32 records).
- Differences of `0.01` between rescaled raw reward and summary/report are therefore expected and are accepted here. Comparisons use the channel calculation, the raw-weight calculation, and each file's own scale. Missing `reward.txt` is reported separately; available JSON is not assumed missing merely because text is absent.
- CTRF here records rewardkit criteria, not necessarily ordinary pytest function executions. For example, the clean example's `verifier/ctrf.json:$.results.summary` says `tests = 63`, `passed = 59`, `failed = 4`, `weighted_percentage = 100.0`. Failed negative criteria mean no prohibited condition was triggered and can coexist with 100% test credit. `report.json:$.pytest.exit_code` is synthesized from those status counts (`HARNESS/scripts/judge_trajectory.py:625` through line 649); it is **not** independent evidence of an actual pytest process exit status. `test-stdout.txt:1` contains only `reward: 0.6858` in this example, so it cannot establish subprocess success or failure by itself.

## Substantive Exception: dad47963

`dad47963-3ef5-569b-9c83-dcf0fa4ffb57/tests/reward.toml:4` specifies test weight `0.005376344086021506` (`0.5 / 93`) and judge weight `0.02631578947368421` (`0.5 / 19`). The GLM raw record instead has `verifier/reward-details.json:$.reward.components[0].weight = 0.00980392156862745` (`0.5 / 51`) and component `[1].weight = 0.005050505050505051` (`0.5 / 99`). Its earned judge and test scores are `10.0` and `6.0` respectively (`components[0].detail.score`, `components[1].detail.score`).

The recorded weights yield `10 * 0.5 / 51 + 6 * 0.5 / 99 = 0.128342...`, rounded to the recorded `reward_raw.json:$.reward = 0.1283` and rescaled `reward.json:$.reward = 12.83` / `reward.txt:1 = 12.83`. Current normalization yields `52.63` rubric, `6.45` tests, and `29.54` combined (`verifier/score.json:$.rubric_weights_percentage`, `$.test_weights_percentage`, `$.final_reward`; `pass_summary.json:$.average_combined_score`). The discrepancy is **16.71 percentage points**, not rounding. The incorrect raw weights also equal `f357cd96-1afe-50bc-b553-a1be78c907e3/tests/reward.toml:4`; equality does not establish how they were copied or which process caused it. Reaggregate/regrade the recorded criteria with the intended configuration and synchronize all reward files; do not silently compare 12.83 to percentage summaries as if they were the same grading result.

## Interpretation Limits

The formulas establish numerical consistency, not verifier correctness. A false Boolean criterion can hide wrong output, a delivered-program crash, a timeout, or a verifier exception if the source collapses those cases. Such ambiguity is retained as `COULD NOT CHECK` rather than interpreted as a clean run. No score is recomputed by executing task code in this audit.
